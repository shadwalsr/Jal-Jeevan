"""
Simulation / Scenario Agent (PRD Section 8, "what if?" exploration —
Demo 3's adversarial scenario: "what if the cyclone shifts and I leave two
hours later?"). No LLM math here either: every scenario reruns the exact
same deterministic Risk Agent used everywhere else, just against different
inputs.

Two kinds of scenario, clearly distinguished (never blur them together):

  1. TIME-SHIFT — "what if I leave N hours later?" Reads a real future
     point in Open-Meteo's own forecast (hour_offset, see
     open_meteo_adapter.py). This is genuine forecast data, not a guess.

  2. PARAMETER PERTURBATION — "what if wave height were 30% higher?" or
     "what if I used a different vessel?" A hypothetical stress-test, not
     a claim about what will actually happen. Every result from this path
     is stamped `is_synthetic_perturbation=True` so a caller (and the
     planner's phrasing) can never present it as a forecast.
"""
from app.agents.risk_agent import assess_risk
from app.agents.route_agent import _score_point
from app.models.schemas import GeoState, OceanState, SimulationResult, VesselProfile, WeatherState


async def simulate_time_shift(lat: float, lon: float, vessel: VesselProfile, hours_later: int) -> SimulationResult:
    baseline = await _score_point(lat, lon, vessel, hour_offset=0)
    scenario = await _score_point(lat, lon, vessel, hour_offset=hours_later)

    return _build_result(
        scenario_label=f"Leaving {hours_later}h later" if hours_later >= 0 else f"Leaving {-hours_later}h earlier",
        baseline=baseline,
        scenario=scenario,
        is_synthetic=False,
    )


async def simulate_vessel_swap(
    weather: WeatherState, ocean: OceanState, geo: GeoState, baseline_vessel: VesselProfile, alt_vessel: VesselProfile
) -> SimulationResult:
    """
    Reuses already-fetched real conditions — no new data needed, since
    conditions don't change, only which vessel is asking about them.
    """
    baseline = assess_risk(weather, ocean, geo, baseline_vessel)
    scenario = assess_risk(weather, ocean, geo, alt_vessel)

    return _build_result(
        scenario_label=f"Using {alt_vessel.vessel_name} instead of {baseline_vessel.vessel_name}",
        baseline=baseline,
        scenario=scenario,
        is_synthetic=False,
    )


async def simulate_wave_perturbation(
    weather: WeatherState, ocean: OceanState, geo: GeoState, vessel: VesselProfile, wave_multiplier: float
) -> SimulationResult:
    """
    Hypothetical stress-test: "what if wave height were X% different?" —
    NOT a forecast, a what-if. Always stamped is_synthetic_perturbation=True.
    """
    baseline = assess_risk(weather, ocean, geo, vessel)

    perturbed_ocean = ocean.model_copy(deep=True)
    if perturbed_ocean.significant_wave_height_m is not None:
        perturbed_ocean.significant_wave_height_m = round(perturbed_ocean.significant_wave_height_m * wave_multiplier, 2)
    scenario = assess_risk(weather, perturbed_ocean, geo, vessel)

    pct = round((wave_multiplier - 1) * 100)
    label = f"Wave height {'+' if pct >= 0 else ''}{pct}% (hypothetical, not a forecast)"

    return _build_result(scenario_label=label, baseline=baseline, scenario=scenario, is_synthetic=True)


def _build_result(scenario_label: str, baseline, scenario, is_synthetic: bool) -> SimulationResult:
    delta = scenario.risk_score - baseline.risk_score

    if scenario.risk_level == "REJECTED" and baseline.risk_level != "REJECTED":
        narrative = f"{scenario_label}: this scenario becomes UNSAFE — {'; '.join(scenario.hard_constraints.reasons)}"
    elif delta > 15:
        narrative = f"{scenario_label}: risk rises notably ({baseline.risk_score} -> {scenario.risk_score}/100, {baseline.risk_level} -> {scenario.risk_level})"
    elif delta < -15:
        narrative = f"{scenario_label}: risk drops notably ({baseline.risk_score} -> {scenario.risk_score}/100, {baseline.risk_level} -> {scenario.risk_level})"
    else:
        narrative = f"{scenario_label}: risk stays about the same ({baseline.risk_score} -> {scenario.risk_score}/100)"

    return SimulationResult(
        scenario=scenario_label,
        baseline_risk_score=baseline.risk_score,
        baseline_risk_level=baseline.risk_level,
        scenario_risk_score=scenario.risk_score,
        scenario_risk_level=scenario.risk_level,
        delta=delta,
        scenario_explanation=scenario.explanation or scenario.hard_constraints.reasons,
        is_synthetic_perturbation=is_synthetic,
        narrative=narrative,
    )
