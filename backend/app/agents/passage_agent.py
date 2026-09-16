"""
Passage Agent — port-to-port (A -> B) voyage planning.

This is the capability sailors and traders were missing. Everything routing
in this system before it was RADIAL: route_agent.py scans candidate zones
within a radius, route_optimizer.py A*-searches to the safest cell at the
edge of a radius. Both answer "where near me should I go?" — the fisherman's
question. A sailor or a trader has a fixed destination and a schedule, and
asks a different question entirely: "get me from Kochi to Tuticorin, tell me
what the passage looks like, and tell me when I arrive."

Same machinery, different objective:
  1. Build an H3 corridor around the great-circle track between the two
     endpoints, dilated laterally so A* has room to route AROUND hazards
     rather than only along the rhumb line.
  2. Score every cell with the same fast Risk Agent path everything else
     uses. Hard-constraint-vetoed cells are removed from the graph entirely
     (never merely penalised) — identical rule to route_optimizer.py.
  3. A* with an edge weight that is real distance inflated by real risk, so
     the result is a genuine trade-off between a longer route and a rougher
     one, and total cost stays interpretable as distance.
  4. SECOND PASS: re-score the cells actually on the chosen path against
     the forecast hour the vessel would really arrive there, derived from
     its own cruise speed. A 40-hour passage scored entirely against
     right-now conditions would be a lie; this reads real future hours out
     of the same Open-Meteo forecast (never extrapolated, never invented),
     and anything past the forecast horizon is flagged as such rather than
     silently filled in.

No LLM anywhere in this file. Distances are haversine, bearings are great
circle, ETA is distance over the vessel's stated cruise speed, risk comes
from risk_agent.py. The planner may phrase the result; it never computes it.
"""
import asyncio
import math

import h3
import networkx as nx

from app.agents.geo_agent import get_nearest_port, get_port_by_name
from app.agents.route_agent import _score_point
from app.agents.risk_agent import UPWIND_DISTANCE_PENALTY_FACTOR
from app.core.maps import google_maps_url
from app.models.schemas import (
    DiversionPort,
    PassageLeg,
    PassagePlan,
    RouteWaypointRisk,
    VesselProfile,
)

EARTH_RADIUS_KM = 6371.0088
KM_PER_NM = 1.852

# Adaptive H3 resolution. A passage is potentially hundreds of km long,
# where route_optimizer.py's radial search is tens — and cell count grows
# with the SQUARE of the corridor length in cells, with one live Open-Meteo
# call per cell. Res 5 (~8.7km) measured fine for a 40km radius; a 700km
# passage at res 5 would be ~80 cells along the track times a dilated
# corridor, i.e. several hundred network calls, which is exactly the
# failure route_optimizer.py already hit going from res 6 to res 5.
# Coarser resolution over longer distance keeps the cell budget flat: a
# 700km ocean passage does not need 8km granularity to answer "which side
# of the storm do I pass".
RESOLUTION_BY_DISTANCE_KM = [
    (150.0, 5),   # ~8.7km edge  — coastal hop
    (500.0, 4),   # ~22.6km edge — regional passage
    (float("inf"), 3),  # ~59.8km edge — ocean crossing
]

H3_EDGE_KM = {3: 59.81, 4: 22.61, 5: 8.68, 6: 3.23}

# Lateral half-width of the search corridor, in hex rings either side of the
# direct track. 2 rings gives A* somewhere to go around a hazard without
# opening up the whole ocean as a search space.
CORRIDOR_RINGS = 2

# Hard ceiling on live scoring calls per passage request. Beyond this the
# corridor is narrowed (and then the resolution coarsened) rather than
# letting a request quietly take minutes — the same "bound it, don't hope"
# reasoning as route_optimizer.MAX_CONCURRENT_CELL_SCORES.
MAX_CELLS = 300

# Matches route_optimizer.py: each cell scoring opens its own DB connection
# for the MPA check, against a 5+10 pool. Bounded so one passage request
# cannot starve every other request on the server.
MAX_CONCURRENT_CELL_SCORES = 12

# Open-Meteo publishes 7 days of hourly forecast. Past that we do not have
# a forecast, and say so, rather than reusing hour 168 as though it were a
# prediction for day 10.
FORECAST_HORIZON_HOURS = 168

# Risk-to-distance exchange rate for the A* edge weight. A cell scoring 25
# (the LOW/MODERATE boundary) costs as though it were twice as far, so the
# search will accept a genuine detour to avoid it but will not wander the
# ocean to shave a couple of points.
RISK_COST_DIVISOR = 25.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _resolution_for(distance_km: float) -> int:
    for threshold, resolution in RESOLUTION_BY_DISTANCE_KM:
        if distance_km <= threshold:
            return resolution
    return 3


def _build_corridor(origin_cell: str, dest_cell: str, rings: int) -> list[str]:
    """
    Cells along the direct track, dilated laterally by `rings`. h3_line can
    fail on a pair of cells that are pentagon-adjacent or very far apart; a
    corridor is a convenience for bounding the search, so falling back to
    the union of two disks is a correct-but-broader search, not a wrong one.
    """
    try:
        spine = h3.h3_line(origin_cell, dest_cell)
    except Exception as exc:  # never swallow silently — CLAUDE.md gotcha #4
        print(f"passage_agent: h3_line failed ({type(exc).__name__}: {exc}) — falling back to disk union")
        spine = [origin_cell, dest_cell]

    cells: set[str] = set()
    for cell in spine:
        cells.update(h3.k_ring(cell, rings))
    cells.add(origin_cell)
    cells.add(dest_cell)
    return list(cells)


def _plan_corridor(origin_cell_res: int, olat: float, olon: float, dlat: float, dlon: float):
    """
    Pick the finest (resolution, corridor width) that stays inside MAX_CELLS.
    Narrowing the corridor is tried before coarsening resolution — a
    narrower corridor loses detour options, a coarser one loses fidelity
    everywhere, and losing detour room is the lesser harm on a long passage
    where the coarse cells are enormous anyway.
    """
    resolution = origin_cell_res
    while True:
        for rings in range(CORRIDOR_RINGS, 0, -1):
            o = h3.geo_to_h3(olat, olon, resolution)
            d = h3.geo_to_h3(dlat, dlon, resolution)
            cells = _build_corridor(o, d, rings)
            if len(cells) <= MAX_CELLS:
                return resolution, rings, o, d, cells
        if resolution <= 3:
            # Floor: accept whatever res 3 with a 1-ring corridor produces.
            o = h3.geo_to_h3(olat, olon, 3)
            d = h3.geo_to_h3(dlat, dlon, 3)
            return 3, 1, o, d, _build_corridor(o, d, 1)
        resolution -= 1


async def _resolve_endpoint(name: str | None, lat: float | None, lon: float | None) -> dict:
    """Coordinates win over a name; a name is resolved against the ports table."""
    if lat is not None and lon is not None:
        return {"status": "success", "lat": lat, "lon": lon, "name": name}
    if name:
        port = await get_port_by_name(name)
        if port.get("status") == "success":
            return {"status": "success", "lat": port["lat"], "lon": port["lon"], "name": port["name"]}
        return port
    return {"status": "failed", "reason": "no coordinates and no port name given"}


def _sailed_distance_from_verdict(distance_nm: float, risk) -> tuple[float, bool]:
    """
    Distance actually sailed over the ground for one leg, and whether it has
    to be tacked. A sailing vessel that cannot lay the course covers roughly
    UPWIND_DISTANCE_PENALTY_FACTOR times the direct distance — a real,
    schedule-relevant cost a motor vessel never pays, and the single biggest
    reason a sailor's ETA differs from a trader's over the same water.

    The upwind determination is NOT repeated here. It is read back out of
    the Risk Agent's own `point_of_sail` factor, which already compared this
    leg's heading against the wind at the forecast hour the leg was scored
    against. One definition of "upwind" in the system, not two that drift.
    A motor vessel has no `point_of_sail` factor, so this is a no-op for it.
    """
    if risk.factor_breakdown.get("point_of_sail", 0) >= 14:
        return distance_nm * UPWIND_DISTANCE_PENALTY_FACTOR, True
    return distance_nm, False


async def plan_passage(
    vessel: VesselProfile,
    origin_name: str | None = None,
    origin_lat: float | None = None,
    origin_lon: float | None = None,
    destination_name: str | None = None,
    destination_lat: float | None = None,
    destination_lon: float | None = None,
    departure_hour_offset: int = 0,
) -> PassagePlan:
    origin = await _resolve_endpoint(origin_name, origin_lat, origin_lon)
    destination = await _resolve_endpoint(destination_name, destination_lat, destination_lon)

    for label, endpoint in (("Origin", origin), ("Destination", destination)):
        if endpoint.get("status") != "success":
            return PassagePlan(
                origin_lat=origin.get("lat") or 0.0,
                origin_lon=origin.get("lon") or 0.0,
                destination_lat=destination.get("lat") or 0.0,
                destination_lon=destination.get("lon") or 0.0,
                origin_name=origin.get("name"),
                destination_name=destination.get("name"),
                vessel_class=vessel.vessel_class,
                vessel_name=vessel.vessel_name,
                found_route=False,
                reason=f"{label} could not be resolved: {endpoint.get('reason', endpoint.get('status'))}",
            )

    olat, olon = origin["lat"], origin["lon"]
    dlat, dlon = destination["lat"], destination["lon"]
    direct_km = haversine_km(olat, olon, dlat, dlon)

    def _fail(reason: str, **extra) -> PassagePlan:
        return PassagePlan(
            origin_name=origin.get("name"), origin_lat=olat, origin_lon=olon,
            destination_name=destination.get("name"), destination_lat=dlat, destination_lon=dlon,
            vessel_class=vessel.vessel_class, vessel_name=vessel.vessel_name,
            found_route=False, reason=reason,
            direct_distance_nm=round(direct_km / KM_PER_NM, 1),
            **extra,
        )

    if direct_km < 1.0:
        return _fail("Origin and destination are the same point")

    # A passage far beyond the vessel's stated range is a hard fact about the
    # vessel, not a routing outcome — answer it before spending hundreds of
    # live source calls discovering it.
    if vessel.operational_range_km > 0 and direct_km > vessel.operational_range_km:
        return _fail(
            f"{direct_km:.0f}km direct exceeds {vessel.vessel_name}'s stated "
            f"{vessel.operational_range_km:.0f}km operational range — this passage is out of "
            f"range for this vessel before any routing is considered"
        )

    resolution, rings, origin_cell, dest_cell, cells = _plan_corridor(
        _resolution_for(direct_km), olat, olon, dlat, dlon
    )

    # --- Pass 1: score the whole corridor at the departure hour. ---
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CELL_SCORES)
    direct_bearing = initial_bearing_deg(olat, olon, dlat, dlon)

    async def _score_bounded(cell: str):
        async with semaphore:
            clat, clon = h3.h3_to_geo(cell)
            # The direct bearing is the best heading estimate available
            # before a path exists; pass 2 replaces it with each leg's real
            # heading once the path is known.
            return await _score_point(
                clat, clon, vessel,
                hour_offset=departure_hour_offset,
                course_bearing_deg=direct_bearing,
            )

    risks = await asyncio.gather(*[_score_bounded(c) for c in cells])
    cell_risk = dict(zip(cells, risks))

    graph = nx.Graph()
    for cell, risk in cell_risk.items():
        if not risk.hard_constraints.vetoed:
            graph.add_node(cell, risk_score=risk.risk_score, risk_level=risk.risk_level)

    common = {
        "h3_resolution": resolution,
        "cells_evaluated": len(cells),
        "cells_viable": len(graph.nodes),
    }

    if origin_cell not in graph.nodes:
        reasons = "; ".join(cell_risk[origin_cell].hard_constraints.reasons)
        return _fail(f"The departure point itself fails a hard constraint: {reasons}", **common)
    if dest_cell not in graph.nodes:
        reasons = "; ".join(cell_risk[dest_cell].hard_constraints.reasons)
        return _fail(f"The destination itself fails a hard constraint: {reasons}", **common)

    for cell in graph.nodes:
        for neighbor in h3.k_ring(cell, 1):
            if neighbor != cell and neighbor in graph.nodes:
                clat, clon = h3.h3_to_geo(cell)
                nlat, nlon = h3.h3_to_geo(neighbor)
                leg_km = haversine_km(clat, clon, nlat, nlon)
                # Real distance, inflated by the risk of the water being
                # entered. This is what makes the result a trade-off rather
                # than either a straight line or an infinite detour.
                weight = leg_km * (1.0 + graph.nodes[neighbor]["risk_score"] / RISK_COST_DIVISOR)
                graph.add_edge(cell, neighbor, weight=weight, distance_km=leg_km)

    if not nx.has_path(graph, origin_cell, dest_cell):
        return _fail(
            "No route exists through this corridor without crossing water that fails a hard "
            "constraint (protected area, insufficient depth for this vessel's draft, or "
            "unsurvivable sea state). Widening the search will not make a vetoed cell passable.",
            **common,
        )

    def _heuristic(a: str, b: str) -> float:
        alat, alon = h3.h3_to_geo(a)
        blat, blon = h3.h3_to_geo(b)
        return haversine_km(alat, alon, blat, blon)

    path = nx.astar_path(graph, origin_cell, dest_cell, heuristic=_heuristic, weight="weight")
    points = [h3.h3_to_geo(c) for c in path]

    # --- Pass 2: re-score the chosen path against the forecast hour the
    # vessel would really be there. Cheap (only the path, not the corridor)
    # and it is the difference between "conditions now along this line" and
    # an actual passage forecast. ---
    speed_kn = max(vessel.cruise_speed_kn, 0.1)
    leg_plans = []
    for i in range(len(points) - 1):
        (flat, flon), (tlat, tlon) = points[i], points[i + 1]
        leg_km = haversine_km(flat, flon, tlat, tlon)
        leg_plans.append(
            {
                "from": (flat, flon),
                "to": (tlat, tlon),
                "bearing": initial_bearing_deg(flat, flon, tlat, tlon),
                "distance_nm": leg_km / KM_PER_NM,
            }
        )

    def _assign_offsets(sailed_per_leg: list[float]) -> None:
        """
        Set each leg's forecast hour from the cumulative time to REACH it.
        The conditions that matter on a leg are the ones at its start, so
        the offset is the running total BEFORE this leg is sailed.
        """
        running = 0.0
        for plan, sailed in zip(leg_plans, sailed_per_leg):
            plan["offset"] = departure_hour_offset + int(round(running / speed_kn))
            running += sailed

    async def _rescore(plan: dict):
        async with semaphore:
            clamped = min(plan["offset"], FORECAST_HORIZON_HOURS)
            risk = await _score_point(
                *plan["to"], vessel,
                hour_offset=clamped,
                course_bearing_deg=plan["bearing"],
            )
            return risk, clamped, plan["offset"] > FORECAST_HORIZON_HOURS

    # Chicken-and-egg: which forecast hour a leg is scored against depends on
    # when the vessel arrives, and that depends on whether the leg has to be
    # tacked — which is only known after it has been scored. So iterate:
    # start from direct distances, score, and if tacking turned up, redo the
    # offsets with the real sailed distances and score once more.
    #
    # Without this a heavily-tacked passage reports each leg's risk against a
    # forecast hour materially earlier than the ETA shown beside it (measured
    # live: legs scored at +13h while the plan said +19h), which reads as a
    # forecast for a time it was never actually evaluated at. One extra pass
    # over the chosen path only — a handful of cells, not the corridor — and
    # a motor vessel never tacks, so it converges on the first pass and pays
    # nothing.
    sailed_per_leg = [plan["distance_nm"] for plan in leg_plans]
    _assign_offsets(sailed_per_leg)
    rescored = await asyncio.gather(*[_rescore(p) for p in leg_plans])

    refined = [_sailed_distance_from_verdict(p["distance_nm"], r)[0] for p, (r, _, _) in zip(leg_plans, rescored)]
    if any(abs(a - b) > 0.01 for a, b in zip(refined, sailed_per_leg)):
        _assign_offsets(refined)
        rescored = await asyncio.gather(*[_rescore(p) for p in leg_plans])

    legs: list[PassageLeg] = []
    cumulative_hours = 0.0
    total_nm = 0.0
    total_sailed_nm = 0.0
    beyond_horizon_count = 0

    for plan, (risk, used_offset, beyond) in zip(leg_plans, rescored):
        # Whether this leg must be tacked is decided by the Risk Agent, not
        # re-derived here: assess_risk already compared this leg's real
        # heading against the wind direction from the same forecast hour the
        # leg was scored against, and the maximum point_of_sail penalty is
        # exactly its "inside the no-go zone" verdict. Reading that back is
        # what keeps one definition of upwind in the system instead of two
        # that can drift apart.
        sailed_nm, must_tack = _sailed_distance_from_verdict(plan["distance_nm"], risk)

        total_nm += plan["distance_nm"]
        total_sailed_nm += sailed_nm
        cumulative_hours += sailed_nm / speed_kn
        beyond_horizon_count += 1 if beyond else 0

        legs.append(
            PassageLeg(
                from_lat=round(plan["from"][0], 4), from_lon=round(plan["from"][1], 4),
                to_lat=round(plan["to"][0], 4), to_lon=round(plan["to"][1], 4),
                bearing_deg=round(plan["bearing"], 1),
                distance_nm=round(plan["distance_nm"], 1),
                sailed_distance_nm=round(sailed_nm, 1),
                eta_hours_from_departure=round(cumulative_hours, 1),
                risk_score=risk.risk_score,
                risk_level=risk.risk_level,
                forecast_hour_offset=used_offset,
                beyond_forecast_horizon=beyond,
                must_tack=must_tack,
                explanation=risk.explanation,
            )
        )

    waypoints = [
        RouteWaypointRisk(lat=round(lat, 4), lon=round(lon, 4), risk_score=graph.nodes[cell]["risk_score"])
        for cell, (lat, lon) in zip(path, points)
    ]

    # --- Diversion ports: where to run for shelter from each part of the
    # passage. Sampled rather than computed per leg — consecutive legs on a
    # coastal passage share the same nearest port, and each lookup is a DB
    # round trip. ---
    sample_indices = sorted({0, len(legs) // 2, max(len(legs) - 1, 0)})
    diversion_lookups = await asyncio.gather(
        *[get_nearest_port(legs[i].to_lat, legs[i].to_lon) for i in sample_indices]
    )
    diversion_ports: list[DiversionPort] = []
    seen_names: set[str] = set()
    for idx, port in zip(sample_indices, diversion_lookups):
        if port.get("status") == "success" and port["name"] not in seen_names:
            seen_names.add(port["name"])
            diversion_ports.append(
                DiversionPort(
                    name=port["name"], lat=port["lat"], lon=port["lon"],
                    distance_km=port["distance_km"], from_leg_index=idx,
                )
            )

    worst = max(legs, key=lambda leg: leg.risk_score) if legs else None

    if beyond_horizon_count:
        forecast_note = (
            f"{beyond_horizon_count} of {len(legs)} legs fall beyond the {FORECAST_HORIZON_HOURS // 24}-day "
            f"forecast horizon and were scored against the last available forecast hour. Treat the later "
            f"part of this passage as unforecast — re-plan en route."
        )
    else:
        forecast_note = (
            f"Every leg was scored against the real forecast hour this vessel would arrive there "
            f"(departure +0h to +{legs[-1].forecast_hour_offset}h), at {speed_kn:.1f} kn cruise."
            if legs else None
        )

    return PassagePlan(
        origin_name=origin.get("name"), origin_lat=olat, origin_lon=olon,
        destination_name=destination.get("name"), destination_lat=dlat, destination_lon=dlon,
        vessel_class=vessel.vessel_class, vessel_name=vessel.vessel_name,
        found_route=True,
        legs=legs,
        waypoints=waypoints,
        diversion_ports=diversion_ports,
        direct_distance_nm=round(direct_km / KM_PER_NM, 1),
        routed_distance_nm=round(total_nm, 1),
        sailed_distance_nm=round(total_sailed_nm, 1),
        total_eta_hours=round(cumulative_hours, 1),
        max_leg_risk_score=worst.risk_score if worst else None,
        max_leg_risk_level=worst.risk_level if worst else None,
        forecast_note=forecast_note,
        destination_maps_url=google_maps_url(dlat, dlon),
        **common,
    )
