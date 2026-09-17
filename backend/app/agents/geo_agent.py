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

from sqlalchemy import text

from app.db.session import async_session
from app.models.schemas import GeoState
from app.tools import bathymetry_adapter, protected_planet_adapter


async def _table_exists(session, table_name: str) -> bool:
    result = await session.execute(
        text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{table_name}"}
    )
    return bool(result.scalar())


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
        return {"status": "unavailable", "reason": f"Database offline ({exc})"}


async def check_mpa(lat: float, lon: float) -> dict:
    try:
        async with async_session() as session:
            if not await _table_exists(session, "mpa_boundaries"):
                # Fall back to live Protected Planet API check if table is absent
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
    except Exception as exc:
        if protected_planet_adapter.is_configured():
            try:
                return await protected_planet_adapter.check_point_in_mpa_api(lat, lon)
            except Exception:
                pass
        return {"status": "unavailable", "reason": f"Database offline ({exc})"}


async def get_nearest_port(lat: float, lon: float) -> dict:
    try:
        async with async_session() as session:
            if not await _table_exists(session, "ports"):
                return {"status": "unavailable", "reason": "ports table not loaded — run infra/sql/002_ports_seed.sql"}
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
            return {"status": "failed", "reason": "no ports in table"}
    except Exception as exc:
        return {"status": "unavailable", "reason": f"Database offline ({exc})"}


async def get_port_by_name(name: str) -> dict:
    """
    Resolve a port NAME to its harbour-entrance coordinates — the endpoint
    lookup the passage planner needs ("Kochi to Colombo"), as opposed to
    get_nearest_port's spatial search from a coordinate.

    Deliberately matched against the ports table rather than the general
    geocoder: a geocoded city name resolves to the city CENTRE, which is on
    land and correctly hard-vetoes (CLAUDE.md's demo note about
    Visakhapatnam). A port's harbour entrance is in the water, which is what
    a passage actually starts and ends at.
    """
    try:
        async with async_session() as session:
            if not await _table_exists(session, "ports"):
                return {"status": "unavailable", "reason": "ports table not loaded — run infra/sql/002_ports_seed.sql"}
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
                {"exact": name.strip(), "prefix": f"{name.strip()}%"},
            )
            row = result.mappings().first()
            if row:
                return {"status": "success", "name": row["name"], "state": row["state"], "lat": row["lat"], "lon": row["lon"]}
            return {"status": "failed", "reason": f"no port named '{name}' in the ports table"}
    except Exception as exc:
        return {"status": "unavailable", "reason": f"Database offline ({exc})"}


async def list_ports() -> list[dict]:
    """Every known port — used to offer passage endpoints in the UI."""
    try:
        async with async_session() as session:
            if not await _table_exists(session, "ports"):
                return []
            result = await session.execute(text("SELECT name, state, lat, lon FROM ports ORDER BY name"))
            return [dict(r) for r in result.mappings().all()]
    except Exception:
        return []


async def get_depth(lat: float, lon: float) -> dict:
    # xarray/netCDF point lookup is blocking (file I/O + numpy indexing) —
    # off the event loop via to_thread, same reasoning as every other
    # blocking adapter in this codebase (see CLAUDE.md gotcha #2). Small
    # single-point lookups against an already-open dataset are fast enough
    # not to need the dedicated network_executor pool.
    return await asyncio.to_thread(bathymetry_adapter.get_depth_m, lat, lon)


async def run_geo_agent(lat: float, lon: float) -> GeoState:
    # Previously sequential (three round-trip DB queries in a row) — now
    # concurrent, consistent with every other agent in this codebase.
    eez, mpa, port, depth = await asyncio.gather(
        check_eez(lat, lon),
        check_mpa(lat, lon),
        get_nearest_port(lat, lon),
        get_depth(lat, lon),
    )

    missing = []
    if eez.get("status") == "unavailable":
        missing.append("EEZ boundaries")
    if mpa.get("status") == "unavailable":
        missing.append("MPA boundaries")
    if port.get("status") == "unavailable":
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
