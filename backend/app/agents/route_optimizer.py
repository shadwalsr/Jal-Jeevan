"""
Route Optimizer — A* over an H3 risk-weighted graph (PRD Section 11.3,
upgrading route_agent.py's 16-candidate radial scan into an actual routed
path). NetworkX does the graph search; every edge weight comes from the
same real Risk Agent used everywhere else — no LLM, no invented cost
function.

Design:
  1. Build an H3 disk (resolution 6, ~3.2km edge) covering the search
     radius around the origin — small enough (~90-150 cells for a 40km
     radius) to score every cell with the FAST Open-Meteo-only path
     (route_agent._score_point) without the request taking minutes.
  2. Score every cell concurrently. A cell whose hard constraints veto it
     (MPA, insufficient depth, etc.) is removed from the graph entirely —
     A* can never route through it, not just penalized for it.
  3. Edge weight between adjacent cells = the risk score of the cell being
     entered — so the path A* finds is the one that avoids the highest-risk
     water, not just the shortest as the crow flies.
  4. A* from the origin cell to the best (lowest-risk) reachable cell at or
     beyond the requested range — same "safest zone" objective as
     route_agent.py, but now the PATH there is risk-aware too, not a
     straight line that might cross a hazardous patch.
"""
import asyncio

import h3
import networkx as nx

from app.agents.route_agent import _score_point
from app.core.maps import google_maps_url
from app.models.schemas import OptimizedRoute, RouteWaypointRisk, VesselProfile

H3_RESOLUTION = 5  # ~8.7km hex edge. Res 6 (~3.2km) was tried first and
# measured at 251s for a 25km-radius disk (271 cells, each a live Open-Meteo
# call) — too slow for any live request regardless of concurrency, since
# cell count grows quadratically with ring count (3k^2+3k+1). Res 5 cuts the
# same-radius cell count by ~4x; still fine granularity for a "which broad
# corridor is safest" route, not meant to compete with GPS-precision nav.
H3_EDGE_KM = 8.68

# _score_point's MPA check opens its own DB connection per call (see
# geo_agent.check_mpa), and the async engine's default pool (app/db/session.py)
# is only 5 + 10 overflow = 15 concurrent connections. A realistic 40km
# search is ~127 cells (3k^2+3k+1 at k=6) — scoring them all in one flat
# asyncio.gather (confirmed live, 26 Aug 2026) blew straight through the
# pool: "QueuePool limit of size 5 overflow 10 reached, connection timed
# out". Bounding concurrency here, rather than just raising the pool size,
# keeps this one endpoint from being able to starve the pool for every other
# concurrent request on the server too.
MAX_CONCURRENT_CELL_SCORES = 12


def _km_to_rings(range_km: float) -> int:
    return max(1, min(8, round(range_km / H3_EDGE_KM) + 1))


async def optimize_route(lat: float, lon: float, range_km: float, vessel: VesselProfile) -> OptimizedRoute:
    origin_cell = h3.geo_to_h3(lat, lon, H3_RESOLUTION)
    k = _km_to_rings(range_km)
    cells = list(h3.k_ring(origin_cell, k))

    # Score every cell — fast (Open-Meteo-only) path, same one route_agent.py's
    # candidate scan uses, and benefits from the same cache. Bounded via a
    # semaphore (see MAX_CONCURRENT_CELL_SCORES) rather than one flat gather —
    # a flat gather over ~127 cells at a realistic search radius exhausts the
    # shared DB connection pool (each cell's MPA check is its own connection).
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CELL_SCORES)

    async def _score_bounded(cell):
        async with semaphore:
            return await _score_point(*h3.h3_to_geo(cell), vessel)

    risks = await asyncio.gather(*[_score_bounded(c) for c in cells])
    cell_risk = dict(zip(cells, risks))

    graph = nx.Graph()
    for cell, risk in cell_risk.items():
        if not risk.hard_constraints.vetoed:
            graph.add_node(cell, risk_score=risk.risk_score)

    for cell in graph.nodes:
        for neighbor in h3.k_ring(cell, 1):
            if neighbor != cell and neighbor in graph.nodes:
                # Entering a higher-risk cell costs more — this is what
                # makes A* actually avoid hazards instead of just finding
                # the geometrically shortest path.
                weight = 1 + graph.nodes[neighbor]["risk_score"]
                graph.add_edge(cell, neighbor, weight=weight)

    if origin_cell not in graph.nodes:
        return OptimizedRoute(
            origin_lat=lat, origin_lon=lon, found_route=False,
            reason="Origin itself fails a hard constraint (see /marine/state for that point)",
            waypoints=[], total_risk_cost=None, cells_evaluated=len(cells), cells_viable=len(graph.nodes),
        )

    # Target: lowest-risk reachable cell at least ~80% of the requested
    # range away — same "go find the safest zone within range" objective
    # as route_agent.py, just with a real path to it now.
    def _distance_km(cell: str) -> float:
        clat, clon = h3.h3_to_geo(cell)
        return h3.point_dist((lat, lon), (clat, clon), unit="km")

    candidates = [
        c for c in graph.nodes if c != origin_cell and nx.has_path(graph, origin_cell, c) and _distance_km(c) >= range_km * 0.8
    ]
    if not candidates:
        # Range too tight for any full-range target — relax to whatever's reachable and safest.
        candidates = [c for c in graph.nodes if c != origin_cell and nx.has_path(graph, origin_cell, c)]

    if not candidates:
        return OptimizedRoute(
            origin_lat=lat, origin_lon=lon, found_route=False,
            reason="No reachable, non-vetoed cell found within range",
            waypoints=[], total_risk_cost=None, cells_evaluated=len(cells), cells_viable=len(graph.nodes),
        )

    target_cell = min(candidates, key=lambda c: graph.nodes[c]["risk_score"])

    def _heuristic(a: str, b: str) -> float:
        alat, alon = h3.h3_to_geo(a)
        blat, blon = h3.h3_to_geo(b)
        return h3.point_dist((alat, alon), (blat, blon), unit="km")

    path = nx.astar_path(graph, origin_cell, target_cell, heuristic=_heuristic, weight="weight")
    total_cost = nx.path_weight(graph, path, weight="weight")

    waypoints = []
    for cell in path:
        wlat, wlon = h3.h3_to_geo(cell)
        waypoints.append(
            RouteWaypointRisk(lat=round(wlat, 4), lon=round(wlon, 4), risk_score=graph.nodes[cell]["risk_score"])
        )

    return OptimizedRoute(
        origin_lat=lat,
        origin_lon=lon,
        found_route=True,
        reason=None,
        waypoints=waypoints,
        destination_maps_url=google_maps_url(waypoints[-1].lat, waypoints[-1].lon) if waypoints else None,
        total_risk_cost=round(total_cost, 1),
        cells_evaluated=len(cells),
        cells_viable=len(graph.nodes),
    )
