"""
Phase 0 Week 3 endpoint: runs Weather + Ocean + Geo agents in parallel,
then the Risk agent composites them into an explainable safety score.
This is the deterministic core the LangGraph planner will sit on top of in
Phase 1 — no LLM involved yet, matching the PRD principle that the LLM
never computes values.
"""
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.agents._timeout import AGENT_TIMEOUT_S, run_with_timeout
from app.agents.geo_agent import list_ports, run_geo_agent
from app.agents.ocean_agent import run_ocean_agent
from app.agents.risk_agent import assess_risk
from app.agents.route_agent import find_safest_zone, quick_check
from app.agents.passage_agent import plan_passage
from app.agents.route_optimizer import optimize_route
from app.agents.simulation_agent import simulate_time_shift, simulate_vessel_swap, simulate_wave_perturbation
from app.agents.validation_agent import validate
from app.core.decisions import new_decision_id, save_decision
from app.core.maps import google_maps_url
from app.models.schemas import (
    FusedMarineState,
    GeoState,
    OceanState,
    OptimizedRoute,
    PassagePlan,
    QuickCheckResult,
    RouteRecommendation,
    SimulationResult,
    VesselProfile,
    WeatherState,
)
from app.agents.vessel_profiles import VESSEL_CLASSES, resolve_vessel
from app.agents.weather_agent import run_weather_agent

router = APIRouter(prefix="/marine", tags=["marine"])

# Moved to app/agents/_timeout.py (29 Aug 2026) so the /chat planner shares
# this exact ceiling instead of running the same agents unbounded — see that
# module's docstring for the 504 this asymmetry was causing. Re-exported
# under the original private names so existing call sites below are
# unchanged.
_run_with_timeout = run_with_timeout


def _validate_coords(lat: float, lon: float) -> None:
    if not (-90 <= lat <= 90):
        raise HTTPException(status_code=400, detail=f"lat must be between -90 and 90, got {lat}")
    if not (-180 <= lon <= 180):
        raise HTTPException(status_code=400, detail=f"lon must be between -180 and 180, got {lon}")


def _vessel_from_query(
    vessel_class: str | None = None,
    length_m: float | None = None,
    max_safe_wave_m: float | None = None,
    wind_threshold_ms: float | None = None,
    operational_range_km: float | None = None,
) -> VesselProfile:
    """
    Turn query parameters into a VesselProfile — one place, so every
    endpoint accepts vessels identically.

    `vessel_class` names one of the registry classes in
    app/agents/vessel_profiles.py (fishing boats, sailing yachts, cargo and
    trade vessels). The individual numeric parameters are OVERRIDES on top
    of that class and default to None rather than to the small-boat numbers
    — that matters: if they still defaulted to 1.5m/12ms/40km, asking about
    a tanker would silently score it against an 8m fishing boat's
    thresholds, which is the exact class of quietly-wrong answer this
    system is built to avoid. Omitting vessel_class entirely resolves to
    the original 8m fishing boat, so every pre-existing caller is unchanged.
    """
    if length_m is not None and (length_m <= 0 or length_m > 500):
        raise HTTPException(status_code=400, detail="vessel_length_m must be between 0 and 500")
    if max_safe_wave_m is not None and (max_safe_wave_m <= 0 or max_safe_wave_m > 20):
        raise HTTPException(status_code=400, detail="vessel_max_safe_wave_m must be between 0 and 20")
    if wind_threshold_ms is not None and (wind_threshold_ms <= 0 or wind_threshold_ms > 60):
        raise HTTPException(status_code=400, detail="vessel_wind_threshold_ms must be between 0 and 60")
    if operational_range_km is not None and (operational_range_km <= 0 or operational_range_km > 25000):
        raise HTTPException(status_code=400, detail="vessel_operational_range_km must be between 0 and 25000")

    return resolve_vessel(
        vessel_class,
        length_m=length_m,
        max_safe_wave_m=max_safe_wave_m,
        wind_threshold_ms=wind_threshold_ms,
        operational_range_km=operational_range_km,
    )


@router.get("/state", response_model=FusedMarineState)
async def get_marine_state(
    lat: float,
    lon: float,
    vessel_class: str | None = None,
    vessel_length_m: float | None = None,
    vessel_max_safe_wave_m: float | None = None,
    vessel_wind_threshold_ms: float | None = None,
    vessel_operational_range_km: float | None = None,
):
    _validate_coords(lat, lon)
    vessel = _vessel_from_query(
        vessel_class, vessel_length_m, vessel_max_safe_wave_m,
        vessel_wind_threshold_ms, vessel_operational_range_km,
    )

    weather, ocean, geo = await asyncio.gather(
        _run_with_timeout(run_weather_agent(lat, lon), "Weather Agent", WeatherState()),
        _run_with_timeout(run_ocean_agent(lat, lon), "Ocean Agent", OceanState()),
        _run_with_timeout(run_geo_agent(lat, lon), "Geo Agent", GeoState()),
    )

    risk = assess_risk(weather, ocean, geo, vessel)
    validation = validate(weather, ocean, geo, risk)

    gaps = weather.missing + ocean.missing + geo.missing
    if validation.issues:
        confidence_note = "VALIDATION FAILED — " + "; ".join(validation.issues)
    elif gaps:
        confidence_note = f"Partial data — missing: {', '.join(gaps)}"
    else:
        confidence_note = "All queried sources responded successfully."

    result = FusedMarineState(
        lat=lat,
        lon=lon,
        maps_url=google_maps_url(lat, lon),
        queried_at=datetime.now(timezone.utc),
        weather=weather,
        ocean=ocean,
        geo=geo,
        risk=risk,
        validation=validation,
        confidence_note=confidence_note,
    )

    # Fire-and-forget: persistence must never slow down or break the
    # response the caller is waiting on (see app/core/decisions.py).
    decision_id = new_decision_id()
    asyncio.create_task(
        save_decision(
            decision_id,
            query_text=f"marine/state lat={lat} lon={lon}",
            response=result.model_dump(),
            confidence=(100 - risk.risk_score) / 100 if not risk.insufficient_confidence else 0.0,
            risk_tier=risk.risk_level,
        )
    )

    return result


@router.get("/quick-check", response_model=QuickCheckResult)
async def get_quick_check(
    lat: float,
    lon: float,
    vessel_class: str | None = None,
    vessel_length_m: float | None = None,
    vessel_max_safe_wave_m: float | None = None,
    vessel_wind_threshold_ms: float | None = None,
    vessel_operational_range_km: float | None = None,
):
    """
    Fast single-point safety check for the live safety monitor
    (frontend SafetyMonitor.tsx polls this ~every 10s from a moving
    vessel's browser geolocation — "we are essentially also a guide,
    because nothing is sure about when the parameters might change").

    Deliberately backed by route_agent.quick_check's fast (Open-Meteo + MPA
    + bathymetry) path, NOT /state's full Copernicus/tide/SST Ocean Agent —
    same check_hard_constraints veto logic either way (risk_agent.py is the
    single shared source of truth), just fast enough to actually poll this
    often. Polling /state at this cadence would repeatedly hit the
    Copernicus login/dataset-open pipeline and the DB pool per active
    monitoring user — see route_optimizer.py's MAX_CONCURRENT_CELL_SCORES
    fix for exactly what that failure mode looks like under concurrency.
    No decision-log persistence here either, for the same reason: this is a
    frequent live poll, not a one-off decision a fisherman asked for.
    """
    _validate_coords(lat, lon)
    vessel = _vessel_from_query(
        vessel_class, vessel_length_m, vessel_max_safe_wave_m,
        vessel_wind_threshold_ms, vessel_operational_range_km,
    )

    try:
        risk = await asyncio.wait_for(quick_check(lat, lon, vessel), timeout=15)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Safety check did not complete in time. Try again shortly.")

    return QuickCheckResult(
        lat=lat,
        lon=lon,
        maps_url=google_maps_url(lat, lon),
        checked_at=datetime.now(timezone.utc),
        risk_score=risk.risk_score,
        risk_level=risk.risk_level,
        vetoed=risk.hard_constraints.vetoed,
        reasons=risk.hard_constraints.reasons,
        explanation=risk.explanation,
        insufficient_confidence=risk.insufficient_confidence,
        confidence_reason=risk.confidence_reason,
    )


@router.get("/simulate/time-shift", response_model=SimulationResult)
async def simulate_departure_time(
    lat: float,
    lon: float,
    hours_later: int,
    vessel_class: str | None = None,
    vessel_length_m: float | None = None,
    vessel_max_safe_wave_m: float | None = None,
    vessel_wind_threshold_ms: float | None = None,
    vessel_operational_range_km: float | None = None,
):
    """PRD Demo 3: 'what if I leave N hours later?' — real forecast data, not fabricated."""
    _validate_coords(lat, lon)
    vessel = _vessel_from_query(
        vessel_class, vessel_length_m, vessel_max_safe_wave_m,
        vessel_wind_threshold_ms, vessel_operational_range_km,
    )
    if hours_later < -24 or hours_later > 72:
        raise HTTPException(status_code=400, detail="hours_later must be between -24 and 72")

    return await simulate_time_shift(lat, lon, vessel, hours_later)


@router.get("/simulate/wave-perturbation", response_model=SimulationResult)
async def simulate_wave_scenario(
    lat: float,
    lon: float,
    wave_multiplier: float,
    vessel_class: str | None = None,
    vessel_length_m: float | None = None,
    vessel_max_safe_wave_m: float | None = None,
    vessel_wind_threshold_ms: float | None = None,
    vessel_operational_range_km: float | None = None,
):
    """Hypothetical stress-test — 'what if wave height were X% different?' Not a forecast."""
    _validate_coords(lat, lon)
    vessel = _vessel_from_query(
        vessel_class, vessel_length_m, vessel_max_safe_wave_m,
        vessel_wind_threshold_ms, vessel_operational_range_km,
    )
    if wave_multiplier <= 0 or wave_multiplier > 5:
        raise HTTPException(status_code=400, detail="wave_multiplier must be between 0 and 5")

    weather, ocean, geo = await asyncio.gather(
        _run_with_timeout(run_weather_agent(lat, lon), "Weather Agent", WeatherState()),
        _run_with_timeout(run_ocean_agent(lat, lon), "Ocean Agent", OceanState()),
        _run_with_timeout(run_geo_agent(lat, lon), "Geo Agent", GeoState()),
    )
    return await simulate_wave_perturbation(weather, ocean, geo, vessel, wave_multiplier)


@router.get("/optimize-route", response_model=OptimizedRoute)
async def get_optimized_route(
    lat: float,
    lon: float,
    range_km: float = 40.0,
    vessel_class: str | None = None,
    vessel_length_m: float | None = None,
    vessel_max_safe_wave_m: float | None = None,
    vessel_wind_threshold_ms: float | None = None,
    vessel_operational_range_km: float | None = None,
):
    """
    A* over an H3 risk-weighted graph (PRD Section 11.3) — a real routed
    path avoiding hazardous cells, not just a straight line to the safest
    endpoint (compare with /safest-route, the faster candidate-scan version).
    """
    _validate_coords(lat, lon)
    vessel = _vessel_from_query(
        vessel_class, vessel_length_m, vessel_max_safe_wave_m,
        vessel_wind_threshold_ms, vessel_operational_range_km,
    )
    if range_km <= 0 or range_km > 200:
        raise HTTPException(status_code=400, detail="range_km must be between 0 and 200 for the graph search")

    try:
        return await asyncio.wait_for(optimize_route(lat, lon, range_km, vessel), timeout=90)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Route optimization did not complete in time. Try again shortly.")


@router.get("/safest-route", response_model=RouteRecommendation)
async def get_safest_route(
    lat: float,
    lon: float,
    range_km: float = 40.0,
    vessel_class: str | None = None,
    vessel_length_m: float | None = None,
    vessel_max_safe_wave_m: float | None = None,
    vessel_wind_threshold_ms: float | None = None,
    vessel_operational_range_km: float | None = None,
):
    """
    PRD Demo 1: "find the safest fishing area within Xkm and give me the
    safest route." Ranks by safety only (see route_agent.py docstring on
    why "productive" isn't claimed yet — that needs the PFZ model).
    """
    _validate_coords(lat, lon)
    vessel = _vessel_from_query(
        vessel_class, vessel_length_m, vessel_max_safe_wave_m,
        vessel_wind_threshold_ms, vessel_operational_range_km,
    )
    if range_km <= 0 or range_km > 500:
        raise HTTPException(status_code=400, detail="range_km must be between 0 and 500")

    try:
        result = await asyncio.wait_for(find_safest_zone(lat, lon, range_km, vessel), timeout=90)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Route search did not complete in time. Try again shortly.")

    decision_id = new_decision_id()
    asyncio.create_task(
        save_decision(
            decision_id,
            query_text=f"marine/safest-route lat={lat} lon={lon} range_km={range_km}",
            response=result.model_dump(),
            confidence=None,
            risk_tier=result.destination_risk.risk_level if result.destination_risk else None,
        )
    )

    return result


@router.get("/vessel-classes")
async def get_vessel_classes():
    """
    The vessel classes this system can reason about, grouped by who they
    serve. The frontend's vessel selector is built from this rather than
    hardcoding a list, so the registry in app/agents/vessel_profiles.py
    stays the single source of truth and a class added there appears in the
    UI with no frontend change.
    """
    groups: dict[str, list[dict]] = {}
    for profile in VESSEL_CLASSES.values():
        groups.setdefault(profile.user_group, []).append(
            {
                "vessel_class": profile.vessel_class,
                "vessel_name": profile.vessel_name,
                "propulsion": profile.propulsion,
                "length_m": profile.length_m,
                "draft_m": profile.draft_m,
                "max_safe_wave_m": profile.max_safe_wave_m,
                "wind_threshold_ms": profile.wind_threshold_ms,
                "operational_range_km": profile.operational_range_km,
                "cruise_speed_kn": profile.cruise_speed_kn,
                "commercial": profile.commercial,
            }
        )
    return {
        "groups": groups,
        "note": (
            "Representative class averages, not a certified vessel database. Override any "
            "field per request; they are starting points, not a substitute for a specific "
            "ship's stability booklet or the skipper's own judgement."
        ),
    }


@router.get("/ports")
async def get_ports():
    """
    Known ports — the endpoints a passage can be planned between. Returns
    an empty list (not an error) when the ports table hasn't been loaded,
    consistent with this system's "report the gap, don't fabricate" rule.
    """
    ports = await list_ports()
    return {"ports": ports, "count": len(ports)}


@router.get("/passage", response_model=PassagePlan)
async def get_passage_plan(
    origin_name: str | None = None,
    origin_lat: float | None = None,
    origin_lon: float | None = None,
    destination_name: str | None = None,
    destination_lat: float | None = None,
    destination_lon: float | None = None,
    departure_hour_offset: int = 0,
    vessel_class: str | None = None,
    vessel_length_m: float | None = None,
    vessel_max_safe_wave_m: float | None = None,
    vessel_wind_threshold_ms: float | None = None,
    vessel_operational_range_km: float | None = None,
):
    """
    Port-to-port passage planning — the sailors' and traders' primitive, as
    opposed to the radius-based "safest zone near me" that /safest-route and
    /optimize-route give fishermen.

    Endpoints may be given as port names (resolved against the ports table's
    harbour entrances) or as raw coordinates; coordinates win when both are
    supplied. Prefer port NAMES here: a geocoded city name resolves to the
    city centre, which is on land and correctly hard-vetoes.

    Returns leg-by-leg headings, distances, per-leg risk scored against the
    forecast hour the vessel would actually be there, a total ETA from the
    vessel's own cruise speed, and diversion ports along the way.
    """
    if origin_lat is not None and origin_lon is not None:
        _validate_coords(origin_lat, origin_lon)
    if destination_lat is not None and destination_lon is not None:
        _validate_coords(destination_lat, destination_lon)
    if not (origin_name or (origin_lat is not None and origin_lon is not None)):
        raise HTTPException(status_code=400, detail="Give an origin: either origin_name or origin_lat+origin_lon")
    if not (destination_name or (destination_lat is not None and destination_lon is not None)):
        raise HTTPException(
            status_code=400,
            detail="Give a destination: either destination_name or destination_lat+destination_lon",
        )
    if departure_hour_offset < 0 or departure_hour_offset > 168:
        raise HTTPException(status_code=400, detail="departure_hour_offset must be between 0 and 168 hours")

    vessel = _vessel_from_query(
        vessel_class, vessel_length_m, vessel_max_safe_wave_m,
        vessel_wind_threshold_ms, vessel_operational_range_km,
    )

    try:
        # Longer ceiling than /optimize-route's 90s: a passage scores a
        # corridor AND re-scores the chosen path against per-leg forecast
        # hours. Still bounded — an unbounded planning request is how you
        # get a request that looks like a hang (CLAUDE.md gotcha #4).
        result = await asyncio.wait_for(
            plan_passage(
                vessel,
                origin_name=origin_name, origin_lat=origin_lat, origin_lon=origin_lon,
                destination_name=destination_name,
                destination_lat=destination_lat, destination_lon=destination_lon,
                departure_hour_offset=departure_hour_offset,
            ),
            timeout=150,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Passage planning did not complete in time. Try again shortly.")

    decision_id = new_decision_id()
    asyncio.create_task(
        save_decision(
            decision_id,
            query_text=(
                f"marine/passage {origin_name or (origin_lat, origin_lon)} -> "
                f"{destination_name or (destination_lat, destination_lon)} vessel={vessel.vessel_class}"
            ),
            response=result.model_dump(),
            confidence=None,
            risk_tier=result.max_leg_risk_level,
        )
    )

    return result
