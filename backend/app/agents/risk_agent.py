"""
Risk Agent — deterministic two-stage decision pipeline (constraint-hierarchy
design, 26 Aug 2026):

  Stage 1 — HARD CONSTRAINTS: things that veto a candidate outright,
  independent of how good everything else looks. A vetoed candidate is
  REJECTED, never scored — a location with an excellent wind/wave picture
  still gets rejected if it's inside a protected area.

  Stage 2 — SOFT SCORING: only runs on candidates that survive Stage 1.
  Every point is individually explainable (factor_breakdown), so a judge
  can click "why 63?" and get an answer, not a black box.

Before 26 Aug 2026 this was a single flat additive score where an MPA
violation contributed +20 points instead of vetoing — meaning a spot
inside a protected area could still come back "LOW risk" if enough other
factors stayed low. That was a real correctness bug, not a style choice;
this file's structure is the fix. `route_agent.py` calls `check_hard_constraints`
directly too, so both the single-point and multi-candidate paths use the
exact same veto logic — no duplicated, divergent rules.

Only vetoes backed by real data the system actually has are implemented —
see the constraint-taxonomy audit for what's still missing (legal boundary
crossing, restricted/naval zones, bathymetry/draft) and therefore NOT
enforced as a hard veto yet; adding a fake veto for something we can't
actually check would be worse than not checking it.

Never LLM math: this is plain arithmetic over already-fetched, already-
provenance-tagged data. The LLM (planner/explainer) is only allowed to
phrase the output in natural language, never compute it.
"""
from app.models.schemas import GeoState, HardConstraintResult, OceanState, RiskAssessment, VesselProfile, WeatherState

# If this many (or more) of the three core Stage-2 inputs (wave height,
# wind speed, distance from port) are missing, refuse to score confidently
# (PRD principle #13: "make the system capable of saying I don't know").
# BUG HISTORY (26 Aug 2026, caught by tests/test_risk_agent.py): this used
# to be 3 compared with `>`, which is mathematically unreachable — there
# are only 3 possible entries that ever get added to missing_inputs, so
# "more than 3" can never be true and INSUFFICIENT_DATA could never fire no
# matter how much was missing. Kept the threshold reachable now: 2 or more
# of the 3 core inputs missing is already too little to score honestly.
MAX_ACCEPTABLE_MISSING_FACTORS = 2

# A pressure drop steeper than this over 3 hours is a real storm precursor,
# independent of what the wind/wave numbers say right now.
PRESSURE_DROP_WARNING_HPA_3H = -2.0

# A wave height at or beyond this multiple of the vessel's stated safe
# threshold isn't "high risk" — it's "don't go," a distinct category.
CERTAIN_CAPSIZE_WAVE_RATIO = 2.0

# GEBCO's 15 arc-second grid (~450m cells) is coarse enough, and tide state
# uncertain enough, that a thin margin over draft alone isn't safe — this is
# on top of the vessel's own draft, not instead of it.
DEPTH_SAFETY_MARGIN_M = 1.0

# Commercial deep-draft vessels are held to a proportional under-keel
# clearance instead of the small-boat fixed margin: a 14m-draft tanker with
# 1m under the keel is not "1m safe" the way a 0.6m-draft fishing boat with
# 1m under the keel is. 10% of static draft is the widely used open-water
# planning figure in PIANC/port approach practice; the absolute floor stops
# it going below the small-boat rule for a shallow-draft commercial vessel.
COMMERCIAL_UKC_FRACTION_OF_DRAFT = 0.10
COMMERCIAL_UKC_FLOOR_M = 0.6

# A sailing vessel that must beat to windward covers roughly 1.4x the
# straight-line distance (two 45-degree tacks instead of one direct leg) and
# spends that whole time heeled and slamming. That is a real cost to rank
# on, not a veto — plenty of passages are made to windward on purpose.
UPWIND_DISTANCE_PENALTY_FACTOR = 1.4


def _angular_difference_deg(a: float, b: float) -> float:
    """Smallest angle between two compass bearings, 0-180."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def squat_m(vessel: VesselProfile) -> float:
    """
    Dynamic squat — how much deeper a moving hull actually sits than its
    static draft. Barrass's open-water approximation: S = Cb * V^2 / 100,
    with V in knots. Deliberately the open-water form, not the confined-
    channel one, because this system reasons about open sea and approaches,
    and has no channel blockage factor to feed the confined form honestly.

    This matters almost entirely for traders: a full-form bulk carrier at
    14 knots squats ~1.7m, which is the difference between clearing a bank
    and grounding on it. For an 8m fishing boat it is ~0.2m and changes
    nothing — but it is applied uniformly rather than special-cased, so
    there is one depth rule in this system, not two.
    """
    return vessel.block_coefficient * (vessel.cruise_speed_kn ** 2) / 100.0


def required_under_keel_m(vessel: VesselProfile) -> float:
    """Clearance required BELOW the keel, over and above draft and squat."""
    if vessel.commercial:
        return max(COMMERCIAL_UKC_FRACTION_OF_DRAFT * vessel.draft_m, COMMERCIAL_UKC_FLOOR_M)
    return DEPTH_SAFETY_MARGIN_M


def available_depth_m(ocean: OceanState, geo: GeoState) -> float | None:
    """
    Charted depth corrected for the astronomical tide actually predicted at
    this point. Tide is only added when EOT20 gave us a real value — never
    assumed to be zero-and-therefore-favourable, and never assumed helpful
    when absent. A falling tide legitimately makes a passage unsafe that
    would be safe two hours earlier, and for a deep-draft trader that is
    frequently the whole decision.
    """
    if geo.depth_m is None:
        return None
    if ocean.tide_height_m is None:
        return geo.depth_m
    return geo.depth_m + ocean.tide_height_m


def check_hard_constraints(
    weather: WeatherState,
    ocean: OceanState,
    geo: GeoState,
    vessel: VesselProfile,
    course_bearing_deg: float | None = None,
) -> HardConstraintResult:
    """
    Stage 1. Called standalone by route_agent.py's candidate scan and
    route_optimizer.py's graph build too.

    `course_bearing_deg` is the direction the vessel would be travelling
    through this point. It is optional and unused by the veto rules — no
    heading makes an MPA legal or a shoal deep — but it is threaded through
    the same signature as assess_risk so callers have one calling
    convention, and so a future veto that genuinely depends on heading
    (a lee shore with no sea room, say) has somewhere to live.
    """
    reasons = []

    if geo.inside_mpa:
        reasons.append(f"Inside protected area ({geo.mpa_name}) — activity prohibited regardless of conditions")

    if ocean.significant_wave_height_m is not None and vessel.max_safe_wave_m > 0:
        if ocean.significant_wave_height_m >= vessel.max_safe_wave_m * CERTAIN_CAPSIZE_WAVE_RATIO:
            reasons.append(
                f"Wave height {ocean.significant_wave_height_m:.2f}m is "
                f"{ocean.significant_wave_height_m / vessel.max_safe_wave_m:.1f}x {vessel.vessel_name}'s "
                f"safe threshold ({vessel.max_safe_wave_m:.1f}m) — not survivable, not just risky"
            )

    if geo.nearest_port_distance_km is not None and vessel.operational_range_km > 0:
        if geo.nearest_port_distance_km > vessel.operational_range_km:
            reasons.append(
                f"{geo.nearest_port_distance_km:.1f}km from nearest port exceeds "
                f"{vessel.vessel_name}'s {vessel.operational_range_km:.0f}km operational range outright"
            )

    if geo.is_land:
        reasons.append("This point is on land, not water, per GEBCO bathymetry")
    else:
        available = available_depth_m(ocean, geo)
        if available is not None:
            squat = squat_m(vessel)
            margin = required_under_keel_m(vessel)
            required_depth = vessel.draft_m + squat + margin
            if available < required_depth:
                tide_note = (
                    f" (charted {geo.depth_m:.1f}m {ocean.tide_height_m:+.2f}m tide)"
                    if ocean.tide_height_m is not None
                    else ""
                )
                reasons.append(
                    f"Water depth {available:.1f}m{tide_note} is less than {vessel.vessel_name}'s "
                    f"draft ({vessel.draft_m:.1f}m) plus {squat:.2f}m squat at "
                    f"{vessel.cruise_speed_kn:.0f}kn plus a {margin:.1f}m under-keel margin "
                    f"({required_depth:.1f}m needed) — grounding risk"
                )

    return HardConstraintResult(vetoed=bool(reasons), reasons=reasons)


def assess_risk(
    weather: WeatherState,
    ocean: OceanState,
    geo: GeoState,
    vessel: VesselProfile,
    course_bearing_deg: float | None = None,
) -> RiskAssessment:
    """
    `course_bearing_deg` (the direction of travel through this point) is
    optional and only ever ADDS sail-specific ranking factors — a motor
    vessel, or any call that doesn't know its heading, scores exactly as it
    did before this parameter existed.
    """
    # --- Stage 1: hard constraints. A vetoed candidate is never scored. ---
    hard = check_hard_constraints(weather, ocean, geo, vessel, course_bearing_deg)
    if hard.vetoed:
        return RiskAssessment(
            risk_score=100,
            risk_level="REJECTED",
            factor_breakdown={},
            explanation=list(hard.reasons),
            hard_constraints=hard,
            insufficient_confidence=False,
            confidence_reason=None,
        )

    # --- Stage 2: soft scoring, only reached if Stage 1 passed. ---
    missing_inputs = []
    breakdown: dict[str, int] = {}
    explanation: list[str] = []

    # --- Wave height vs vessel safe threshold ---
    if ocean.significant_wave_height_m is None:
        missing_inputs.append("wave height")
        breakdown["wave_height"] = 0
    else:
        ratio = ocean.significant_wave_height_m / vessel.max_safe_wave_m
        pts = _scale(ratio, low=0.5, high=1.5, max_points=30)
        breakdown["wave_height"] = pts
        explanation.append(
            f"Wave height {ocean.significant_wave_height_m:.2f}m vs {vessel.vessel_name}'s "
            f"safe threshold {vessel.max_safe_wave_m:.1f}m -> +{pts}"
        )

    # --- Cross-swell: a distinct, more dangerous sea state than either
    # wave train alone, and invisible in the combined wave-height number ---
    breakdown["cross_swell"] = 8 if ocean.cross_swell else 0
    if ocean.cross_swell:
        explanation.append(
            f"Swell ({ocean.swell_height_m:.1f}m from {ocean.swell_direction_deg:.0f} deg) crossing "
            f"wind-wave ({ocean.wind_wave_height_m:.1f}m from {ocean.wind_wave_direction_deg:.0f} deg) -> +8"
        )

    # --- Tide: reported for situational awareness only, not scored. Real
    # bar-crossing / shallow-water risk needs bathymetry (harbour bar depth
    # vs. tide height) which isn't wired in yet — see readiness audit. ---
    if ocean.tide_state is not None:
        explanation.append(
            f"Tide {ocean.tide_state} ({ocean.tide_height_m:+.2f}m) — informational only, "
            f"not yet scored (needs bathymetry for bar-crossing risk)"
        )

    # --- Wind: sustained speed AND gusts scored separately — a boat can
    # look safe on sustained wind alone while gusts are what capsizes it ---
    if weather.wind_speed_ms is None:
        missing_inputs.append("wind speed")
        breakdown["wind_speed"] = 0
    else:
        ratio = weather.wind_speed_ms / vessel.wind_threshold_ms
        pts = _scale(ratio, low=0.5, high=1.5, max_points=18)
        breakdown["wind_speed"] = pts
        explanation.append(
            f"Wind speed {weather.wind_speed_ms:.1f} m/s vs threshold "
            f"{vessel.wind_threshold_ms:.1f} m/s -> +{pts}"
        )

    if weather.wind_gust_ms is not None:
        gust_ratio = weather.wind_gust_ms / vessel.wind_threshold_ms
        gust_pts = _scale(gust_ratio, low=0.7, high=1.6, max_points=12)
        breakdown["wind_gust"] = gust_pts
        if gust_pts > 0:
            explanation.append(
                f"Gusts to {weather.wind_gust_ms:.1f} m/s vs threshold "
                f"{vessel.wind_threshold_ms:.1f} m/s -> +{gust_pts}"
            )
    else:
        breakdown["wind_gust"] = 0

    # --- SAIL ONLY: wind is a resource, not only a hazard ---------------
    # A motor vessel in 1 m/s of wind is having a perfect day. A sailing
    # vessel in 1 m/s of wind has no drive, no steerage, and is going
    # wherever the current takes it — which near a shipping lane or a lee
    # shore is a genuine hazard, not merely a slow passage. Scored, never
    # vetoed: being becalmed is uncomfortable and delaying, not fatal.
    becalmed_pts = 0
    if vessel.min_working_wind_ms is not None and weather.wind_speed_ms is not None:
        if weather.wind_speed_ms < vessel.min_working_wind_ms:
            deficit_ratio = 1.0 - (weather.wind_speed_ms / vessel.min_working_wind_ms)
            # Halved for motor-sailers: an auxiliary engine turns being
            # becalmed from a hazard into a fuel bill.
            ceiling = 12 if vessel.propulsion == "sail" else 6
            becalmed_pts = max(1, round(ceiling * deficit_ratio))
            explanation.append(
                f"Wind {weather.wind_speed_ms:.1f} m/s is below {vessel.vessel_name}'s "
                f"{vessel.min_working_wind_ms:.1f} m/s working minimum — becalmed, "
                f"{'no auxiliary propulsion' if vessel.propulsion == 'sail' else 'auxiliary engine available'} -> +{becalmed_pts}"
            )
    breakdown["becalmed"] = becalmed_pts

    # --- SAIL ONLY: point of sail. Needs a course to mean anything, so it
    # only fires on the routing paths (passage legs, route candidates) that
    # actually know which way the vessel is heading. ---
    upwind_pts = 0
    if (
        vessel.no_go_angle_deg is not None
        and course_bearing_deg is not None
        and weather.wind_direction_deg is not None
    ):
        # wind_direction_deg is meteorological — the direction the wind is
        # coming FROM — which is already the same convention as the bearing
        # a vessel would have to point to sail directly into it.
        angle_off_wind = _angular_difference_deg(course_bearing_deg, weather.wind_direction_deg)
        if angle_off_wind < vessel.no_go_angle_deg:
            upwind_pts = 14
            explanation.append(
                f"Course {course_bearing_deg:.0f} deg is {angle_off_wind:.0f} deg off a wind from "
                f"{weather.wind_direction_deg:.0f} deg — inside {vessel.vessel_name}'s "
                f"{vessel.no_go_angle_deg:.0f} deg no-go zone, cannot be sailed direct; "
                f"tacking costs about {UPWIND_DISTANCE_PENALTY_FACTOR:.1f}x the distance -> +{upwind_pts}"
            )
        elif angle_off_wind < vessel.no_go_angle_deg + 15:
            upwind_pts = 7
            explanation.append(
                f"Course {course_bearing_deg:.0f} deg is a hard beat at {angle_off_wind:.0f} deg "
                f"off the wind — sailable but slow, wet and heeled -> +{upwind_pts}"
            )
        elif angle_off_wind > 170:
            # Dead downwind: rolling, and a real accidental-gybe risk.
            upwind_pts = 4
            explanation.append(
                f"Course {course_bearing_deg:.0f} deg is dead downwind ({angle_off_wind:.0f} deg off) "
                f"— rolling and accidental-gybe risk -> +{upwind_pts}"
            )
    breakdown["point_of_sail"] = upwind_pts

    # --- Thin under-keel clearance that has NOT triggered the Stage 1 veto.
    # Passing the veto means there is legally enough water; it does not mean
    # there is comfortably enough. This is the factor that makes a deep-draft
    # trader prefer the deeper of two otherwise-equal routes. ---
    clearance_pts = 0
    available = available_depth_m(ocean, geo)
    if available is not None and not geo.is_land:
        needed = vessel.draft_m + squat_m(vessel) + required_under_keel_m(vessel)
        if needed > 0:
            clearance_ratio = available / needed
            # Inverted ramp: 1.0x needed (right at the legal limit) is worst,
            # 2.0x needed or deeper scores nothing.
            clearance_pts = _scale(2.0 - min(clearance_ratio, 2.0), low=0.0, high=1.0, max_points=10)
            if clearance_pts > 0:
                explanation.append(
                    f"Under-keel clearance is thin: {available:.1f}m of water against "
                    f"{needed:.1f}m needed ({clearance_ratio:.2f}x) -> +{clearance_pts}"
                )
    breakdown["under_keel_clearance"] = clearance_pts

    # --- Pressure trend: a falling barometer is an early storm precursor
    # independent of today's wind/wave readings ---
    if weather.pressure_trend_hpa_3h is not None and weather.pressure_trend_hpa_3h <= PRESSURE_DROP_WARNING_HPA_3H:
        pressure_pts = min(10, round(abs(weather.pressure_trend_hpa_3h) * 2.5))
        breakdown["pressure_trend"] = pressure_pts
        explanation.append(
            f"Pressure falling {weather.pressure_trend_hpa_3h:.1f} hPa over 3h -> +{pressure_pts} (storm precursor)"
        )
    else:
        breakdown["pressure_trend"] = 0

    # --- Fog / visibility ---
    breakdown["fog_risk"] = 6 if weather.fog_risk else 0
    if weather.fog_risk:
        explanation.append("Temperature/dew-point spread indicates fog risk -> +6")

    # --- Harmful algal bloom proxy (chlorophyll spike) — a health hazard
    # for crew and catch, not just an ecological signal (readiness audit) ---
    breakdown["hab_risk"] = 5 if ocean.hab_risk else 0
    if ocean.hab_risk:
        explanation.append(
            f"Chlorophyll {ocean.chlorophyll_mg_m3:.1f} mg/m3 above bloom-indicator threshold -> +5 (HAB proxy, not a diagnosis)"
        )

    # --- Cyclone ---
    breakdown["cyclone"] = 25 if weather.cyclone_active else 0
    if weather.cyclone_active:
        explanation.append("Active cyclone in the area -> +25")

    # --- Distance from port vs vessel operational range (already confirmed
    # NOT to exceed range outright in Stage 1 — this scores how close to
    # the limit it is, not whether it's exceeded) ---
    if geo.nearest_port_distance_km is None:
        missing_inputs.append("distance from port")
        breakdown["distance_from_port"] = 0
    else:
        ratio = geo.nearest_port_distance_km / vessel.operational_range_km
        pts = _scale(ratio, low=0.5, high=1.0, max_points=12)
        breakdown["distance_from_port"] = pts
        explanation.append(
            f"{geo.nearest_port_distance_km:.1f}km from nearest port ({geo.nearest_port_name}) "
            f"vs {vessel.vessel_name}'s {vessel.operational_range_km:.0f}km range -> +{pts}"
        )

    # --- Data uncertainty penalty (disagreement between SST sources etc.) ---
    uncertainty_pts = 0
    if ocean.sst_disagreement and ocean.sst_disagreement > 1.0:
        uncertainty_pts += 5
        explanation.append(f"SST sources disagree by {ocean.sst_disagreement:.1f}C -> +5 (uncertainty)")
    breakdown["data_uncertainty"] = uncertainty_pts

    total_missing = len(missing_inputs) + len(weather.missing) + len(ocean.missing) + len(geo.missing)

    if len(missing_inputs) >= MAX_ACCEPTABLE_MISSING_FACTORS:
        return RiskAssessment(
            risk_score=0,
            risk_level="INSUFFICIENT_DATA",
            factor_breakdown=breakdown,
            explanation=explanation,
            hard_constraints=hard,
            insufficient_confidence=True,
            confidence_reason=f"Missing critical inputs: {', '.join(missing_inputs)}. Cannot produce a safe recommendation.",
        )

    score = min(100, sum(breakdown.values()))
    level = _risk_level(score)

    return RiskAssessment(
        risk_score=score,
        risk_level=level,
        factor_breakdown=breakdown,
        explanation=explanation,
        hard_constraints=hard,
        insufficient_confidence=False,
        confidence_reason=(
            f"{total_missing} data point(s) missing — treat with extra caution" if total_missing else None
        ),
    )


def _scale(ratio: float, low: float, high: float, max_points: int) -> int:
    """Linear ramp: ratio<=low -> 0 points, ratio>=high -> max_points."""
    if ratio <= low:
        return 0
    if ratio >= high:
        return max_points
    return round(max_points * (ratio - low) / (high - low))


def _risk_level(score: int) -> str:
    if score < 25:
        return "LOW"
    if score < 50:
        return "MODERATE"
    if score < 75:
        return "HIGH"
    return "EXTREME"
