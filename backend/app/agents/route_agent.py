"""
Route/Navigation Agent — PRD Sections 8.6, 42 (Demo 1: "safest productive
fishing area within 40km"). Deterministic candidate generation + scoring,
no LLM math (PRD Section 6): every candidate's risk score comes straight
from the same Risk Agent used elsewhere, not a model guess.

DESIGN NOTE ON SPEED: a full multi-source Ocean Agent call (Copernicus
Marine login + dataset open) takes ~15-20s per point — fine for a single
query, not for scanning a dozen candidate zones. So this agent scans with
Open-Meteo only (fast, no auth, good enough for a relative ranking), picks
the best candidate, and leaves full multi-source consensus fusion (the
Ocean Agent's job) for whoever displays the final chosen zone in detail.
This mirrors a real operational pattern: coarse fast search, then a
detailed check on the winner — not a shortcut that skips the real fusion.

PFZ NOTE: real "productive" (fishing-suitability) scoring needs the
INCOIS PFZ model (blocked on MOSDAC access — see app/ml/). Until that
lands, "safest" is the only ranking criterion this agent can honestly
offer; it does not claim to find "productive" zones yet.
"""
import asyncio
import math

from app.agents._timeout import run_with_timeout
from app.agents.geo_agent import check_mpa, get_depth, run_geo_agent
from app.agents.ocean_agent import run_ocean_agent
from app.agents.risk_agent import assess_risk
from app.agents.weather_agent import run_weather_agent
from app.core.maps import google_maps_url
from app.models.schemas import (
    GeoState,
    OceanState,
    RiskAssessment,
    RouteCandidate,
    RouteRecommendation,
    VesselProfile,
    WeatherState,
)
from app.tools import open_meteo_adapter

EARTH_RADIUS_KM = 6371.0


def _destination_point(lat: float, lon: float, bearing_deg: float, distance_km: float) -> tuple[float, float]:
    """Haversine destination-point formula."""
    lat1, lon1, brng = map(math.radians, (lat, lon, bearing_deg))
    d_r = distance_km / EARTH_RADIUS_KM
    lat2 = math.asin(math.sin(lat1) * math.cos(d_r) + math.cos(lat1) * math.sin(d_r) * math.cos(brng))
    lon2 = lon1 + math.atan2(
        math.sin(brng) * math.sin(d_r) * math.cos(lat1), math.cos(d_r) - math.sin(lat1) * math.sin(lat2)
    )
    return math.degrees(lat2), math.degrees(lon2)


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _generate_candidates(lat: float, lon: float, range_km: float) -> list[tuple[float, float, float, float]]:
    """8 bearings x 2 rings (half-range, full-range) = 16 candidate points."""
    candidates = []
    for ring_frac in (0.5, 1.0):
        distance = range_km * ring_frac
        for bearing in range(0, 360, 45):
            plat, plon = _destination_point(lat, lon, bearing, distance)
            candidates.append((plat, plon, distance, float(bearing)))
    return candidates


async def _score_point(
    lat: float,
    lon: float,
    vessel: VesselProfile,
    distance_from_origin_km: float | None = None,
    hour_offset: int = 0,
    course_bearing_deg: float | None = None,
):
    """
    Fast (Open-Meteo-only) risk scoring for one point — shared by candidate
    scanning, waypoint scoring, AND the Simulation Agent's time-shift
    scenarios (hour_offset reads a real future point in the same forecast,
    not a fabricated value — see open_meteo_adapter.py). Returns the
    RiskAssessment itself so callers can read hard_constraints, risk_score,
    etc. directly.
    """
    # All four independent lookups run concurrently (see CLAUDE.md gotcha #1)
    # — this used to run mpa_check sequentially after marine/wx, and skipped
    # depth entirely. Skipping depth was the real bug (26 Aug 2026): bathymetry
    # is a fast, local, already-open-file lookup (no network I/O — see
    # bathymetry_adapter.py), there was never a speed reason to leave it out
    # of the fast scan, and without it `check_hard_constraints`'s on-land /
    # insufficient-depth veto could never fire during candidate scanning —
    # a point that is actually on land could score as low-risk "LOW" here
    # and only get caught later (or not at all) when the winning candidate
    # gets its full detail recheck. See find_safest_zone for the other half
    # of this fix.
    marine, wx, mpa_check, depth = await asyncio.gather(
        open_meteo_adapter.get_marine_forecast(lat, lon, hour_offset=hour_offset),
        open_meteo_adapter.get_weather_forecast(lat, lon, hour_offset=hour_offset),
        check_mpa(lat, lon),
        get_depth(lat, lon),
    )

    ocean = OceanState(
        significant_wave_height_m=marine.get("wave_height_m"),
        wave_period_s=marine.get("wave_period_s"),
        sources_used=["Open-Meteo Marine"] if marine.get("status") == "success" else [],
        partial=marine.get("status") != "success",
        missing=[] if marine.get("status") == "success" else ["wave height"],
    )
    weather = WeatherState(
        wind_speed_ms=wx.get("wind_speed_ms"),
        wind_gust_ms=wx.get("wind_gust_ms"),
        wind_direction_deg=wx.get("wind_direction_deg"),
        sources_used=["Open-Meteo Forecast"] if wx.get("status") == "success" else [],
        partial=wx.get("status") != "success",
        missing=[] if wx.get("status") == "success" else ["wind speed"],
    )
    geo_missing = []
    if mpa_check.get("status") == "unavailable":
        geo_missing.append("MPA boundaries")
    if depth.get("status") != "success":
        geo_missing.append(f"bathymetry ({depth.get('reason') or depth.get('error') or depth.get('status')})")
    geo = GeoState(
        inside_mpa=mpa_check.get("inside_mpa", False),
        mpa_name=mpa_check.get("name"),
        nearest_port_distance_km=distance_from_origin_km,
        depth_m=depth.get("depth_m"),
        is_land=bool(depth.get("is_land")),
        missing=geo_missing,
    )

    # assess_risk runs Stage 1 (hard constraints) internally and returns
    # risk_level="REJECTED" when vetoed — this is the single shared source
    # of truth for what counts as a veto, used identically by the
    # single-point /marine/state path. No separate inline MPA check here
    # anymore (see risk_agent.py's module docstring for why that mattered).
    # course_bearing_deg is passed straight through to the Risk Agent, which
    # uses it only for the sail-specific point-of-sail factor — the passage
    # planner knows the heading through each cell, the radial candidate scan
    # does not, and both call this same function.
    return assess_risk(weather, ocean, geo, vessel, course_bearing_deg=course_bearing_deg)


async def quick_check(lat: float, lon: float, vessel: VesselProfile) -> RiskAssessment:
    """
    Public entry point for a fast, single-point safety check — the same
    Open-Meteo + MPA + bathymetry path the candidate scan uses (see
    _score_point's docstring), deliberately NOT the full Copernicus/tide/SST
    Ocean Agent. This exists for the live safety monitor
    (/marine/quick-check, polled every ~10s from a moving vessel's browser)
    — that cadence would exhaust the Copernicus login/dataset-open pipeline
    and the DB pool (see route_optimizer.py's MAX_CONCURRENT_CELL_SCORES fix
    for exactly that failure mode) if it hit the full multi-source path.
    Same shared check_hard_constraints veto logic either way — this is
    faster, not less safe.
    """
    return await _score_point(lat, lon, vessel)


async def _score_candidate(lat: float, lon: float, distance_km: float, bearing: float, vessel: VesselProfile) -> RouteCandidate:
    risk = await _score_point(lat, lon, vessel, distance_from_origin_km=distance_km)
    rejected = risk.hard_constraints.vetoed
    reason = "; ".join(risk.hard_constraints.reasons) if rejected else None

    return RouteCandidate(
        lat=lat,
        lon=lon,
        distance_from_origin_km=round(distance_km, 1),
        bearing_deg=bearing,
        risk_score=risk.risk_score,
        risk_level=risk.risk_level,
        rejected=rejected,
        rejection_reason=reason,
    )


# Expansion policy for when nothing viable turns up within the vessel's
# stated/requested range. A fisherman asking "what's safe within 40km" does
# not actually want a flat "nothing found" if the truth is "nothing until
# 55km" — a real answer they can act on (even if it means more fuel/time
# than planned) beats a dead end. Same reasoning covers a query point that
# is itself on land (see gotcha #8, city-centre geocoding): the origin ring
# is land in every direction, but water is very likely a few rings further
# out along the coast, so the same expansion loop finds it instead of the
# agent reporting "this point is on land" and stopping there.
#
# Growth is geometric (not linear) so a handful of iterations covers a wide
# span without generating hundreds of candidates: 1x, 1.8x, 3.24x, 5.8x,
# 10.5x, 19x range_km. EXPANSION_HARD_CAP_KM bounds it in absolute terms too
# (no boat search should ever wander mid-ocean past ~1200km looking for
# "the nearest safe spot") — whichever cap is hit first stops the loop.
#
# TIMING (28 Aug 2026): the expansion rings are fast-scanned CONCURRENTLY in a
# single batch, never one ring after another. The first version of this walked
# the rings sequentially and paid a full scan-plus-verify round (~25s cold) per
# ring — up to 7 of them, ~175s, which blew /chat's 115s ceiling and returned a
# 504 instead of an answer. The expensive half is verification (Copernicus
# login + dataset opens through network_executor's shared 16-worker pool), so
# that stays capped at MAX_VERIFICATION_ATTEMPTS per PHASE, not per ring:
# at most two phases run, so at most 6 full-detail checks and ~50s worst case
# regardless of how far the search has to reach.
EXPANSION_GROWTH = 1.8
MAX_EXPANSIONS = 6
EXPANSION_HARD_CAP_KM = 1200.0
# Open-Meteo + PostGIS + local bathymetry only (no network_executor worker is
# held), but a 7-ring batch is still 112 candidate points — cap the in-flight
# count so a wide search cannot hammer Open-Meteo into rate-limiting us.
EXPANSION_SCAN_CONCURRENCY = 24


def _expansion_ranges(range_km: float) -> list[float]:
    """Ring radii beyond the requested range, nearest first."""
    out: list[float] = []
    r = range_km
    for _ in range(MAX_EXPANSIONS):
        r *= EXPANSION_GROWTH
        if r > EXPANSION_HARD_CAP_KM:
            break
        out.append(r)
    return out


async def _fast_scan(lat: float, lon: float, ranges: list[float], vessel: VesselProfile,
                     sem: asyncio.Semaphore | None = None) -> list[RouteCandidate]:
    """
    Open-Meteo-only candidate scan across one or more ring radii, all points
    in flight together. Cheap per point (no Copernicus, no network_executor
    worker), which is exactly why the whole expansion fans out here rather
    than paying a separate round-trip per ring.
    """
    async def one(plat, plon, dist, bearing):
        if sem is None:
            return await _score_candidate(plat, plon, dist, bearing, vessel)
        async with sem:
            return await _score_candidate(plat, plon, dist, bearing, vessel)

    points = [p for r in ranges for p in _generate_candidates(lat, lon, r)]
    return list(await asyncio.gather(*[one(*p) for p in points]))


async def _verify_best(candidates: list[RouteCandidate], vessel: VesselProfile):
    """
    Full multi-source recheck (Copernicus + Open-Meteo + Geo) of the fast
    scan's best candidates — the "detailed check on the winner" the module
    docstring describes; scanning did NOT skip real fusion, it deferred it.
    The fast scan checks bathymetry too (see _score_point), so this normally
    just confirms what the scan found — but it can legitimately disagree
    (multi-source Ocean Agent consensus vs. Open-Meteo alone) and MUST be
    allowed to overrule it.

    BUG HISTORY (26 Aug 2026): this used to trust the scan unconditionally —
    a real query returned `found_safe_zone: true` for a destination the
    detailed recheck had itself just scored REJECTED (on land), quoting the
    scan's stale "LOW risk" figure. Now the first candidate that also clears
    Stage 1 here wins.

    Bounded, not "try them all": each check runs the full multi-source path
    through network_executor's shared 16-worker pool, which has no reliable
    way to reclaim a worker whose call hung past its own timeout (wait_for
    abandons the coroutine; the OS thread keeps the slot). Retrying
    unboundedly was measured stalling one request for 5+ minutes and
    starving every other request on the server.

    Concurrent, not sequential (27 Aug 2026): running the capped set together
    costs ~max() instead of ~sum() — measured 27-34s down to ~10-20s — without
    widening the bound above.
    """
    async def _verify(candidate: RouteCandidate):
        # Per-agent ceilings here too (29 Aug 2026). These three were bare
        # awaits, so one slow Copernicus fetch stretched a verification
        # round out with nothing to stop it — the same unbounded-agent
        # shape that made /chat 504 (see app/agents/_timeout.py). A source
        # that times out becomes a recorded gap on that candidate, which
        # check_hard_constraints already knows how to treat conservatively.
        w, o, g = await asyncio.gather(
            run_with_timeout(run_weather_agent(candidate.lat, candidate.lon), "Weather Agent", WeatherState()),
            run_with_timeout(run_ocean_agent(candidate.lat, candidate.lon), "Ocean Agent", OceanState()),
            run_with_timeout(run_geo_agent(candidate.lat, candidate.lon), "Geo Agent", GeoState()),
        )
        return candidate, assess_risk(w, o, g, vessel), w, o, g

    verified = await asyncio.gather(*[_verify(c) for c in candidates[:MAX_VERIFICATION_ATTEMPTS]])

    rejections = []
    for candidate, risk, w, o, g in verified:
        if not risk.hard_constraints.vetoed:
            return candidate, risk, w, o, g, rejections
        rejections.append(
            f"{candidate.lat:.2f},{candidate.lon:.2f} ({candidate.bearing_deg:.0f} deg, "
            f"{candidate.distance_from_origin_km}km): scan said {candidate.risk_level} but full "
            f"detail check found: {'; '.join(risk.hard_constraints.reasons)}"
        )
    return None, None, None, None, None, rejections


# Reduced from 3 to 1 (5 Sep 2026): each verification runs the full Ocean
# Agent (Copernicus + INCOIS + NOAA + tides), which takes 25-40s cold due to
# the netcdf_lock serialising dataset opens. Verifying 3 candidates triples
# wall time and was the main contributor to the 60s timeout — the fast scan
# already checks bathymetry (land/depth veto), MPA, and Open-Meteo weather/
# waves, so the top-1 winner is almost never overturned by verification.
MAX_VERIFICATION_ATTEMPTS = 1


async def find_safest_zone(lat: float, lon: float, range_km: float, vessel: VesselProfile) -> RouteRecommendation:
    # ---- Phase 1: the range the caller actually asked about.
    all_candidates = await _fast_scan(lat, lon, [range_km], vessel)
    viable = sorted((c for c in all_candidates if not c.rejected), key=lambda c: c.risk_score)
    best, destination_risk, dest_weather, dest_ocean, dest_geo, verification_rejections = (
        await _verify_best(viable, vessel) if viable else (None, None, None, None, None, [])
    )

    search_range_km = range_km
    exceeded_requested_range = False

    # ---- Phase 2: nothing usable inside the requested range, so reach past
    # it rather than dead-ending. Every expansion ring is scanned in ONE
    # concurrent batch and the winner is picked across all of them at once —
    # see the timing note on EXPANSION_GROWTH for why this is not a loop.
    if best is None:
        ranges = _expansion_ranges(range_km)
        if ranges:
            search_range_km = ranges[-1]
            sem = asyncio.Semaphore(EXPANSION_SCAN_CONCURRENCY)
            outer = await _fast_scan(lat, lon, ranges, vessel, sem=sem)
            all_candidates.extend(outer)
            # Nearest acceptable zone first — the point of expanding is to
            # hand back the closest reachable option, not the safest one
            # 700km away. Distance is bucketed to 10km so that candidates at
            # effectively the same reach still tie-break on risk.
            outer_viable = sorted(
                (c for c in outer if not c.rejected),
                key=lambda c: (round((c.distance_from_origin_km or 0) / 10.0), c.risk_score),
            )
            if outer_viable:
                best, destination_risk, dest_weather, dest_ocean, dest_geo, more = (
                    await _verify_best(outer_viable, vessel)
                )
                verification_rejections.extend(more)
                if best is not None:
                    search_range_km = best.distance_from_origin_km or search_range_km
                    exceeded_requested_range = True

    candidates = all_candidates

    if best is None:
        return RouteRecommendation(
            origin_lat=lat,
            origin_lon=lon,
            candidates_evaluated=all_candidates,
            requested_range_km=range_km,
            recommendation=(
                f"No safe zone found even after expanding the search out to "
                f"{search_range_km:.0f}km (requested range was {range_km:.0f}km) — every candidate found was "
                "either protected, unsurvivable, or on land. This area may not have a usable water route "
                "nearby; try a different starting point."
            ),
            found_safe_zone=False,
        )

    distance_km = _haversine_km(lat, lon, best.lat, best.lon)
    bearing = best.bearing_deg

    # Simple 5-point straight-line route (great-circle-ish via repeated
    # destination formula). Endpoints reuse risk already computed above
    # (candidate scan for origin's own conditions aren't separately scored —
    # it's presumed to be the vessel's current position — destination_risk
    # for the far end); the 3 INTERMEDIATE points are scored here, closing
    # the "route engine evaluates the whole route, not just the endpoint"
    # gap from the constraint-taxonomy audit — a route can look fine at
    # both ends and still cross a hazardous patch in between.
    fracs = (0.0, 0.25, 0.5, 0.75, 1.0)
    mid_fracs = fracs[1:-1]
    mid_points = [_destination_point(lat, lon, bearing, distance_km * f) for f in mid_fracs]
    mid_risks = await asyncio.gather(
        *[_score_point(plat, plon, vessel, distance_from_origin_km=distance_km * f) for (plat, plon), f in zip(mid_points, mid_fracs)]
    )

    waypoints = []
    route_hazards = []
    for frac in fracs:
        wlat, wlon = _destination_point(lat, lon, bearing, distance_km * frac)
        entry = {"lat": round(wlat, 4), "lon": round(wlon, 4)}
        if frac == 0.0:
            pass  # origin — vessel's current position, not separately scored
        elif frac == 1.0:
            entry["risk_score"] = destination_risk.risk_score
            entry["risk_level"] = destination_risk.risk_level
        else:
            idx = mid_fracs.index(frac)
            r = mid_risks[idx]
            entry["risk_score"] = r.risk_score
            entry["risk_level"] = r.risk_level
            if r.hard_constraints.vetoed:
                entry["vetoed"] = True
                entry["reason"] = "; ".join(r.hard_constraints.reasons)
                route_hazards.append(f"{frac*100:.0f}% along route: {entry['reason']}")
        waypoints.append(entry)

    rejected_summary = [
        f"{c.lat:.2f},{c.lon:.2f} ({c.bearing_deg:.0f} deg, {c.distance_from_origin_km}km): {c.rejection_reason}"
        for c in candidates
        if c.rejected
    ]
    # Use destination_risk (the verified, full multi-source recheck), not
    # best.risk_score/risk_level (the fast Open-Meteo-only scan estimate) —
    # they can legitimately disagree, and the recommendation text must
    # reflect what was actually verified, not the coarse first pass.
    rec_text = (
        f"Safest zone found {distance_km:.1f}km at bearing {bearing:.0f} deg "
        f"(risk {destination_risk.risk_score}/100, {destination_risk.risk_level}). "
    )
    if exceeded_requested_range:
        rec_text = (
            f"Nothing viable turned up within your {range_km:.0f}km range, so the search was expanded. "
            + rec_text
            + f"This exceeds your requested {range_km:.0f}km range — factor the extra distance into fuel "
            "and time before heading out. "
        )
    if verification_rejections:
        rec_text += (
            f"({len(verification_rejections)} candidate(s) the fast scan preferred failed full "
            "verification and were skipped.) "
        )
    if route_hazards:
        rec_text += "WARNING — hazard along the route itself, not just the destination: " + "; ".join(route_hazards) + ". "
    if rejected_summary:
        rec_text += f"{len(rejected_summary)} candidate(s) rejected: " + "; ".join(rejected_summary)

    return RouteRecommendation(
        origin_lat=lat,
        origin_lon=lon,
        destination_lat=best.lat,
        destination_lon=best.lon,
        destination_maps_url=google_maps_url(best.lat, best.lon),
        distance_km=round(distance_km, 1),
        bearing_deg=bearing,
        destination_risk=destination_risk,
        waypoints=waypoints,
        candidates_evaluated=candidates,
        recommendation=rec_text,
        found_safe_zone=True,
        requested_range_km=range_km,
        exceeded_requested_range=exceeded_requested_range,
    )
