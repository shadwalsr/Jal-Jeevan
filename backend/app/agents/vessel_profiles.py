"""
Vessel Class Registry — the single source of truth for "what kind of boat
is asking?", extending this system beyond its original single archetype (a
generic 8m fishing boat) to the sailors and traders who share the same
water.

Why this exists as data, not code: every risk threshold in risk_agent.py is
already expressed relative to the vessel (wave height vs. the vessel's safe
threshold, distance vs. its operational range). Before this file there was
exactly one vessel, so those thresholds were effectively constants. A 300m
container ship and an 8m open fishing boat experience the same 3m sea
completely differently — one is routine, the other is a capsize. Making the
vessel a real parameter is what makes the same deterministic risk pipeline
correct for all three user groups, rather than needing three pipelines.

PROVENANCE / HONESTY: these are representative class averages compiled from
public vessel-type characteristics, NOT a certified vessel database and NOT
a substitute for a specific ship's stability booklet or a skipper's own
judgement. They are starting defaults — every field can be overridden
per-request. Block coefficients (`block_coefficient`) are the standard
published ranges by hull type and are used ONLY for the Barrass squat
approximation in risk_agent.py. Where a number is a genuine rule of thumb
rather than a measurement, the comment says so.

Consistent with the project's core philosophy: no LLM picks these numbers
and no LLM interpolates between classes. `resolve_vessel` is a dictionary
lookup with deterministic aliasing.
"""
from app.models.schemas import VesselProfile

# Public, stable class keys. The API, the chat parser and the frontend all
# speak these exact strings — don't rename one without updating
# rule_based.py's alias table and the frontend selector together.
VESSEL_CLASSES: dict[str, VesselProfile] = {
    # ---------------- Fishing ----------------
    "fishing_small": VesselProfile(
        vessel_class="fishing_small",
        vessel_name="Small fishing boat (8m)",
        user_group="fisherman",
        propulsion="motor",
        length_m=8.0,
        draft_m=0.6,
        block_coefficient=0.45,
        max_safe_wave_m=1.5,
        wind_threshold_ms=12.0,
        operational_range_km=40.0,
        cruise_speed_kn=7.0,
    ),
    "fishing_mechanized": VesselProfile(
        vessel_class="fishing_mechanized",
        vessel_name="Mechanized trawler (18m)",
        user_group="fisherman",
        propulsion="motor",
        length_m=18.0,
        draft_m=2.0,
        block_coefficient=0.55,
        max_safe_wave_m=3.0,
        wind_threshold_ms=17.0,
        operational_range_km=300.0,
        cruise_speed_kn=9.0,
    ),
    # ---------------- Sailing ----------------
    # Sailing vessels are the reason `propulsion` exists. For them wind is a
    # RESOURCE as well as a hazard — too little wind is its own failure mode
    # (becalmed, no steerage, drifting with the current), which a
    # motor-vessel risk model scores as "perfect conditions".
    "sailing_yacht": VesselProfile(
        vessel_class="sailing_yacht",
        vessel_name="Cruising sailing yacht (12m)",
        user_group="sailor",
        propulsion="sail",
        length_m=12.0,
        draft_m=1.9,  # fin keel — deeper than most motor boats of the same length
        block_coefficient=0.40,
        max_safe_wave_m=3.5,
        wind_threshold_ms=21.0,  # ~Force 8; a well-found yacht heaves to rather than sinks
        min_working_wind_ms=2.5,  # below this there is no useful drive from sail
        no_go_angle_deg=40.0,  # cannot sail closer than ~40 deg to the true wind
        operational_range_km=3000.0,
        cruise_speed_kn=6.0,
    ),
    "sailing_yacht_aux": VesselProfile(
        vessel_class="sailing_yacht_aux",
        vessel_name="Sailing yacht with auxiliary engine (12m)",
        user_group="sailor",
        propulsion="motor_sail",
        length_m=12.0,
        draft_m=1.9,
        block_coefficient=0.40,
        max_safe_wave_m=3.5,
        wind_threshold_ms=21.0,
        min_working_wind_ms=2.5,
        no_go_angle_deg=40.0,
        operational_range_km=3000.0,
        cruise_speed_kn=6.5,
    ),
    # A traditional Indian Ocean sailing trader — the historical dhow trade
    # is still live cargo work, and sits squarely between "sailor" and
    # "trader" rather than in either box.
    "dhow": VesselProfile(
        vessel_class="dhow",
        vessel_name="Sailing dhow / country craft (20m)",
        user_group="trader",
        propulsion="motor_sail",
        length_m=20.0,
        draft_m=2.2,
        block_coefficient=0.55,
        max_safe_wave_m=3.0,
        wind_threshold_ms=18.0,
        min_working_wind_ms=3.0,
        no_go_angle_deg=55.0,  # a lateen rig points far worse than a bermudan yacht
        operational_range_km=2000.0,
        cruise_speed_kn=7.0,
    ),
    # ---------------- Trade / commercial ----------------
    "coastal_trader": VesselProfile(
        vessel_class="coastal_trader",
        vessel_name="Coastal cargo vessel (40m)",
        user_group="trader",
        propulsion="motor",
        length_m=40.0,
        draft_m=3.5,
        block_coefficient=0.72,
        max_safe_wave_m=4.0,
        wind_threshold_ms=20.0,
        operational_range_km=1500.0,
        cruise_speed_kn=9.0,
        commercial=True,
    ),
    "general_cargo": VesselProfile(
        vessel_class="general_cargo",
        vessel_name="General cargo ship (120m)",
        user_group="trader",
        propulsion="motor",
        length_m=120.0,
        draft_m=8.0,
        block_coefficient=0.78,
        max_safe_wave_m=6.0,
        wind_threshold_ms=25.0,
        operational_range_km=10000.0,
        cruise_speed_kn=13.0,
        commercial=True,
    ),
    "bulk_carrier": VesselProfile(
        vessel_class="bulk_carrier",
        vessel_name="Bulk carrier (200m)",
        user_group="trader",
        propulsion="motor",
        length_m=200.0,
        draft_m=12.5,
        block_coefficient=0.85,  # full-form hull — squats hard in shallow water
        max_safe_wave_m=8.0,
        wind_threshold_ms=28.0,
        operational_range_km=20000.0,
        cruise_speed_kn=14.0,
        commercial=True,
    ),
    "tanker": VesselProfile(
        vessel_class="tanker",
        vessel_name="Product tanker (250m)",
        user_group="trader",
        propulsion="motor",
        length_m=250.0,
        draft_m=14.0,
        block_coefficient=0.82,
        max_safe_wave_m=8.0,
        wind_threshold_ms=28.0,
        operational_range_km=20000.0,
        cruise_speed_kn=14.0,
        commercial=True,
    ),
    "container_ship": VesselProfile(
        vessel_class="container_ship",
        vessel_name="Container ship (300m)",
        user_group="trader",
        propulsion="motor",
        length_m=300.0,
        draft_m=14.5,
        block_coefficient=0.65,  # finer hull, but very high windage from the box stacks
        max_safe_wave_m=9.0,
        wind_threshold_ms=30.0,
        operational_range_km=25000.0,
        cruise_speed_kn=20.0,
        commercial=True,
    ),
    "passenger_ferry": VesselProfile(
        vessel_class="passenger_ferry",
        vessel_name="Passenger ferry (60m)",
        user_group="trader",
        propulsion="motor",
        length_m=60.0,
        draft_m=3.0,
        block_coefficient=0.60,
        # Deliberately conservative relative to hull capability: a ferry's
        # real limit is unsecured standing passengers, not ship stability.
        max_safe_wave_m=3.0,
        wind_threshold_ms=20.0,
        operational_range_km=500.0,
        cruise_speed_kn=18.0,
        commercial=True,
    ),
}

DEFAULT_VESSEL_CLASS = "fishing_small"

# Free-text -> class key. Used by the rule-based intent parser (and to
# sanity-clamp whatever string the LLM produces, so an LLM hallucinating
# "big_boat" degrades to the documented default instead of crashing or, far
# worse, silently scoring a cargo ship against an 8m boat's thresholds).
CLASS_ALIASES: dict[str, str] = {
    "fishing": "fishing_small",
    "fishing boat": "fishing_small",
    "small boat": "fishing_small",
    "canoe": "fishing_small",
    "catamaran": "fishing_small",
    "trawler": "fishing_mechanized",
    "mechanized": "fishing_mechanized",
    "mechanised": "fishing_mechanized",
    "sail": "sailing_yacht",
    "sailing": "sailing_yacht",
    "sailboat": "sailing_yacht",
    "sailing boat": "sailing_yacht",
    "yacht": "sailing_yacht",
    "sloop": "sailing_yacht",
    "ketch": "sailing_yacht",
    "dhow": "dhow",
    "country craft": "dhow",
    "coaster": "coastal_trader",
    "coastal": "coastal_trader",
    "barge": "coastal_trader",
    "cargo": "general_cargo",
    "cargo ship": "general_cargo",
    "freighter": "general_cargo",
    "merchant": "general_cargo",
    "bulker": "bulk_carrier",
    "bulk": "bulk_carrier",
    "bulk carrier": "bulk_carrier",
    "tanker": "tanker",
    "oil tanker": "tanker",
    "container": "container_ship",
    "container ship": "container_ship",
    "boxship": "container_ship",
    "ferry": "passenger_ferry",
    "passenger": "passenger_ferry",
}


def resolve_vessel(
    vessel_class: str | None = None,
    length_m: float | None = None,
    **overrides,
) -> VesselProfile:
    """
    Deterministic lookup. An unknown/None class falls back to
    DEFAULT_VESSEL_CLASS rather than raising — this is called on the chat
    path where the input is natural language, and refusing to answer
    because someone typed an unrecognised boat name is worse than answering
    for the documented default and saying which default was used
    (`vessel_class` is echoed back in every response).

    `length_m` is NOT used to reshape the class (a 15m yacht is not scaled
    from a 12m one by any honest formula this system has) — it is recorded
    as the user's stated length and used only where length genuinely enters
    a calculation, i.e. squat. Overriding draft/wave/wind thresholds is an
    explicit per-field override, never an inference.
    """
    key = (vessel_class or "").strip().lower().replace("-", "_").replace(" ", "_")
    profile = VESSEL_CLASSES.get(key)

    if profile is None:
        alias_key = (vessel_class or "").strip().lower()
        aliased = CLASS_ALIASES.get(alias_key)
        profile = VESSEL_CLASSES.get(aliased) if aliased else None

    if profile is None:
        profile = VESSEL_CLASSES[DEFAULT_VESSEL_CLASS]

    data = profile.model_dump()
    if length_m is not None and length_m > 0:
        data["length_m"] = length_m
    for field, value in overrides.items():
        if value is not None and field in data:
            data[field] = value

    return VesselProfile(**data)


def classes_for_group(user_group: str) -> list[VesselProfile]:
    """Everything a fisherman / sailor / trader would plausibly pick from."""
    return [v for v in VESSEL_CLASSES.values() if v.user_group == user_group]
