"""
Validation / Critic Agent (PRD Section 8, "safety net" role — see the
constraint-hierarchy design's final stage: VALIDATION before RECOMMENDATION).

Runs AFTER Risk Agent scoring, as a last check before a result reaches the
user. Catches two categories of problem the scoring pipeline itself can't
see, because it trusts its inputs by construction:

  1. Physically implausible readings — a value outside any real-world
     bound means a source glitched (bad sensor, unit-conversion bug,
     corrupted response), not that reality is actually that extreme.
  2. Internal contradictions — states the code should never be able to
     produce if every upstream agent is behaving, so seeing one means
     something upstream broke in a way individual agents didn't catch.

Deterministic, no LLM (same principle as everything else): this is a list
of bound checks and cross-field assertions, not a judgment call.

On a genuine problem, marks the assessment INVALID and demands replanning
rather than silently returning a number that might be garbage — the same
"say I don't know rather than guess" principle as Risk Agent's
INSUFFICIENT_DATA path, applied to catching upstream bugs instead of
upstream data gaps.
"""
from app.models.schemas import GeoState, OceanState, RiskAssessment, ValidationResult, WeatherState

# Real-world plausibility bounds — generous on purpose (this is a sanity
# check for glitched data, not a scientific accuracy claim).
BOUNDS = {
    "sst_c": (-2.0, 40.0),
    "wave_height_m": (0.0, 30.0),
    "wind_speed_ms": (0.0, 120.0),
    "wind_gust_ms": (0.0, 150.0),
    "pressure_hpa": (850.0, 1085.0),
    "salinity_psu": (0.0, 45.0),
    "depth_m": (0.0, 11000.0),
    "tide_height_m": (-15.0, 15.0),
}


def validate(weather: WeatherState, ocean: OceanState, geo: GeoState, risk: RiskAssessment) -> ValidationResult:
    issues: list[str] = []

    _check_bound(issues, "SST", ocean.sst_c, *BOUNDS["sst_c"], unit="C")
    _check_bound(issues, "Wave height", ocean.significant_wave_height_m, *BOUNDS["wave_height_m"], unit="m")
    _check_bound(issues, "Wind speed", weather.wind_speed_ms, *BOUNDS["wind_speed_ms"], unit="m/s")
    _check_bound(issues, "Wind gust", weather.wind_gust_ms, *BOUNDS["wind_gust_ms"], unit="m/s")
    _check_bound(issues, "Pressure", weather.pressure_msl_hpa, *BOUNDS["pressure_hpa"], unit="hPa")
    _check_bound(issues, "Salinity", ocean.salinity_psu, *BOUNDS["salinity_psu"], unit="PSU")
    _check_bound(issues, "Depth", geo.depth_m, *BOUNDS["depth_m"], unit="m")
    _check_bound(issues, "Tide height", ocean.tide_height_m, *BOUNDS["tide_height_m"], unit="m")

    # Gust should never read lower than sustained wind — if it does, one of
    # the two is wrong (unit mix-up, stale cached value, source glitch).
    if weather.wind_gust_ms is not None and weather.wind_speed_ms is not None:
        if weather.wind_gust_ms < weather.wind_speed_ms - 0.5:  # small tolerance for rounding
            issues.append(
                f"Wind gust ({weather.wind_gust_ms:.1f} m/s) is lower than sustained wind "
                f"({weather.wind_speed_ms:.1f} m/s) — physically inconsistent, one reading is wrong"
            )

    # A vetoed candidate must never carry a non-REJECTED risk level, and
    # vice versa — these two fields are set together in risk_agent.py, but
    # asserting it here catches a future edit that breaks that invariant
    # instead of silently shipping a contradictory response.
    if risk.hard_constraints.vetoed and risk.risk_level != "REJECTED":
        issues.append(
            f"Internal contradiction: hard_constraints.vetoed=True but risk_level={risk.risk_level!r} "
            f"(should be REJECTED) — Risk Agent's Stage 1/Stage 2 wiring is broken"
        )
    if not risk.hard_constraints.vetoed and risk.risk_level == "REJECTED":
        issues.append(
            "Internal contradiction: risk_level=REJECTED but hard_constraints.vetoed=False — "
            "Risk Agent's Stage 1/Stage 2 wiring is broken"
        )

    # Land + a real (non-land) risk assessment is a contradiction — nobody
    # should be getting a fishing recommendation for dry land.
    if geo.is_land and not risk.hard_constraints.vetoed:
        issues.append("Point is on land per bathymetry but was not vetoed — geo/risk wiring gap")

    return ValidationResult(valid=not issues, issues=issues)


def _check_bound(issues: list[str], label: str, value: float | None, lo: float, hi: float, unit: str) -> None:
    if value is None:
        return
    if value < lo or value > hi:
        issues.append(f"{label} {value:.2f}{unit} is outside plausible bounds [{lo}, {hi}]{unit} — likely a bad reading")
