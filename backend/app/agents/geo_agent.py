"""
Geo Agent — deterministic PostGIS + bathymetry lookups (PRD Section 8.4).
No LLM involved: geofencing and depth are spatial facts, not something to
be inferred by a language model.

Depends on:
  - `eez_boundaries` table (Marine Regions World EEZ v12) — loaded
  - `mpa_boundaries` table (Protected Planet WDPA) — loaded
  - `ports` table — curated seed list, loaded (infra/sql/002_ports_seed.sql)
  - GEBCO_2026 bathymetry subset (data/raw/gebco/) — loaded via OPeNDAP,
    see app/tools/bathymetry_adapter.py

Each function checks whether its backing data exists and returns a clear
"unavailable" status instead of crashing if something hasn't been loaded
yet — same fallback pattern as the Weather/Ocean agents.
"""
import asyncio
import math

from sqlalchemy import text

from app.db.session import async_session
from app.models.schemas import GeoState
from app.tools import bathymetry_adapter, protected_planet_adapter

# Built-in seed list of major Indian fishing harbours / ports from infra/sql/002_ports_seed.sql.
# Enables deterministic port distance calculation even when PostGIS is unreachable on cloud deployments.
FALLBACK_PORTS = [
    {"name": "Puri", "state": "Odisha", "lat": 19.8135, "lon": 85.8312},
    {"name": "Paradip", "state": "Odisha", "lat": 20.2648, "lon": 86.6947},
    {"name": "Visakhapatnam", "state": "Andhra Pradesh", "lat": 17.6868, "lon": 83.2185},
    {"name": "Kakinada", "state": "Andhra Pradesh", "lat": 16.9891, "lon": 82.2475},
    {"name": "Chennai", "state": "Tamil Nadu", "lat": 13.0827, "lon": 80.2907},
    {"name": "Nagapattinam", "state": "Tamil Nadu", "lat": 10.7661, "lon": 79.8420},
    {"name": "Rameswaram", "state": "Tamil Nadu", "lat": 9.2876, "lon": 79.3129},
    {"name": "Tuticorin", "state": "Tamil Nadu", "lat": 8.7642, "lon": 78.1348},
    {"name": "Kochi", "state": "Kerala", "lat": 9.9312, "lon": 76.2673},
    {"name": "Kollam", "state": "Kerala", "lat": 8.8932, "lon": 76.6141},
    {"name": "Mangalore", "state": "Karnataka", "lat": 12.9141, "lon": 74.8560},
    {"name": "Goa (Mormugao)", "state": "Goa", "lat": 15.4028, "lon": 73.7996},
    {"name": "Mumbai", "state": "Maharashtra", "lat": 18.9220, "lon": 72.8347},
    {"name": "Veraval", "state": "Gujarat", "lat": 20.9159, "lon": 70.3629},
    {"name": "Porbandar", "state": "Gujarat", "lat": 21.6417, "lon": 69.6293},
    {"name": "Kandla", "state": "Gujarat", "lat": 23.0333, "lon": 70.2167},
    {"name": "Port Blair", "state": "Andaman & Nicobar", "lat": 11.6234, "lon": 92.7265},
]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _nearest_fallback_port(lat: float, lon: float) -> dict:
    best = None
    min_dist = float("inf")
    for p in FALLBACK_PORTS:
        d = _haversine_km(lat, lon, p["lat"], p["lon"])
        if d < min_dist:
            min_dist = d
            best = p
    if best:
        return {
            "status": "success",
            "name": best["name"],
            "state": best["state"],
            "distance_km": round(min_dist, 1),
            "lat": best["lat"],
            "lon": best["lon"],
        }
    return {"status": "failed", "reason": "no ports available"}


def _find_fallback_port_by_name(name: str) -> dict:
    clean = name.strip().lower()
    for p in FALLBACK_PORTS:
        if p["name"].lower() == clean:
            return {"status": "success", "name": p["name"], "state": p["state"], "lat": p["lat"], "lon": p["lon"]}
    for p in FALLBACK_PORTS:
        if p["name"].lower().startswith(clean):
            return {"status": "success", "name": p["name"], "state": p["state"], "lat": p["lat"], "lon": p["lon"]}
    return {"status": "failed", "reason": f"no port named '{name}' found"}


async def _table_exists(session, table_name: str) -> bool:
    try:
        result = await session.execute(
            text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{table_name}"}
        )
        return bool(result.scalar())
    except Exception:
        return False


async def check_eez(lat: float, lon: float) -> dict:
    try:
        async with async_session() as session:
            if not await _table_exists(session, "eez_boundaries"):
                return {"status": "unavailable", "reason": "eez_boundaries not loaded yet — see DATA_ACQUISITION.md"}
            result = await session.execute(
                text(
                    """
                    SELECT "TERRITORY1" AS territory, "UNION" AS name
                    FROM eez_boundaries
                    WHERE ST_Contains(geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                    LIMIT 1
                    """
                ),
                {"lat": lat, "lon": lon},
            )
            row = result.mappings().first()
            if row:
                return {"status": "success", "inside_eez": True, "territory": row["territory"], "name": row["name"]}
            return {"status": "success", "inside_eez": False}
    except Exception as exc:
        return {"status": "unavailable", "reason": f"eez database unavailable ({type(exc).__name__})"}


async def check_mpa(lat: float, lon: float) -> dict:
    try:
        async with async_session() as session:
            if not await _table_exists(session, "mpa_boundaries"):
                if protected_planet_adapter.is_configured():
                    return await protected_planet_adapter.check_point_in_mpa_api(lat, lon)
                return {"status": "unavailable", "reason": "mpa_boundaries not loaded and Protected Planet API not configured"}
            result = await session.execute(
                text(
                    """
                    SELECT name, "DESIG_ENG" AS designation, "IUCN_CAT" AS iucn_cat,
                           COALESCE(NULLIF("GIS_M_AREA", 0), "REP_M_AREA") AS marine_area_km2
                    FROM mpa_boundaries
                    WHERE ST_Contains(geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                    LIMIT 1
                    """
                ),
                {"lat": lat, "lon": lon},
            )
            row = result.mappings().first()
            if row:
                return {
                    "status": "success",
                    "inside_mpa": True,
                    "name": row.get("name"),
                    "designation": row.get("designation"),
                    "iucn_cat": row.get("iucn_cat"),
                    "marine_area_km2": row.get("marine_area_km2"),
                    "source": "PostGIS mpa_boundaries (Protected Planet WDPA)",
                }
            return {"status": "success", "inside_mpa": False}
    except Exception:
        if protected_planet_adapter.is_configured():
            return await protected_planet_adapter.check_point_in_mpa_api(lat, lon)
        return {"status": "unavailable", "reason": "mpa database query failed and Protected Planet API not configured"}


async def get_nearest_port(lat: float, lon: float) -> dict:
    try:
        async with async_session() as session:
            if not await _table_exists(session, "ports"):
                return _nearest_fallback_port(lat, lon)
            result = await session.execute(
                text(
                    """
                    SELECT name, state, lat, lon,
                           ST_DistanceSphere(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) / 1000.0 AS distance_km
                    FROM ports
                    ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                    LIMIT 1
                    """
                ),
                {"lat": lat, "lon": lon},
            )
            row = result.mappings().first()
            if row:
                return {
                    "status": "success",
                    "name": row["name"],
                    "state": row["state"],
                    "distance_km": round(row["distance_km"], 1),
                    "lat": row["lat"],
                    "lon": row["lon"],
                }
            return _nearest_fallback_port(lat, lon)
    except Exception:
        return _nearest_fallback_port(lat, lon)


async def get_port_by_name(name: str) -> dict:
    """
    Resolve a port NAME to its harbour-entrance coordinates — the endpoint
    lookup the passage planner needs ("Kochi to Colombo"), as opposed to
    get_nearest_port's spatial search from a coordinate.
    """
    clean_name = name.strip()
    try:
        async with async_session() as session:
            if not await _table_exists(session, "ports"):
                return _find_fallback_port_by_name(clean_name)
            result = await session.execute(
                text(
                    """
                    SELECT name, state, lat, lon
                    FROM ports
                    WHERE name ILIKE :exact OR name ILIKE :prefix
                    ORDER BY CASE WHEN name ILIKE :exact THEN 0 ELSE 1 END, length(name)
                    LIMIT 1
                    """
                ),
                {"exact": clean_name, "prefix": f"{clean_name}%"},
            )
            row = result.mappings().first()
            if row:
                return {"status": "success", "name": row["name"], "state": row["state"], "lat": row["lat"], "lon": row["lon"]}
            return _find_fallback_port_by_name(clean_name)
    except Exception:
        return _find_fallback_port_by_name(clean_name)


async def list_ports() -> list[dict]:
    """Every known port — used to offer passage endpoints in the UI."""
    try:
        async with async_session() as session:
            if not await _table_exists(session, "ports"):
                return list(FALLBACK_PORTS)
            result = await session.execute(text("SELECT name, state, lat, lon FROM ports ORDER BY name"))
            rows = [dict(r) for r in result.mappings().all()]
            return rows if rows else list(FALLBACK_PORTS)
    except Exception:
        return list(FALLBACK_PORTS)


async def get_depth(lat: float, lon: float) -> dict:
    return await asyncio.to_thread(bathymetry_adapter.get_depth_m, lat, lon)


async def run_geo_agent(lat: float, lon: float) -> GeoState:
    try:
        eez, mpa, port, depth = await asyncio.gather(
            check_eez(lat, lon),
            check_mpa(lat, lon),
            get_nearest_port(lat, lon),
            get_depth(lat, lon),
        )
    except Exception as exc:
        port = _nearest_fallback_port(lat, lon)
        eez = {"status": "unavailable", "reason": f"error: {exc}"}
        mpa = {"status": "unavailable", "reason": f"error: {exc}"}
        depth = {"status": "unavailable", "reason": f"error: {exc}"}

    missing = []
    if eez.get("status") == "unavailable":
        missing.append("EEZ boundaries")
    if mpa.get("status") == "unavailable":
        missing.append("MPA boundaries")
    if port.get("status") != "success":
        missing.append("ports table")
    if depth.get("status") != "success":
        missing.append(f"bathymetry ({depth.get('reason') or depth.get('error') or depth.get('status')})")

    return GeoState(
        inside_indian_eez=eez.get("inside_eez", False) if "india" in str(eez.get("territory", "")).lower() else eez.get("inside_eez", False),
        eez_territory=eez.get("territory"),
        inside_mpa=mpa.get("inside_mpa", False),
        mpa_name=mpa.get("name"),
        nearest_port_name=port.get("name"),
        nearest_port_distance_km=port.get("distance_km"),
        depth_m=depth.get("depth_m"),
        is_land=bool(depth.get("is_land")),
        missing=missing,
    )
