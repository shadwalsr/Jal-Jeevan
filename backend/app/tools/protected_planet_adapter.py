"""
Protected Planet API v4 adapter — Marine Protected Areas (WDPA + WD-OECM).
Retrieves official MPA and OECM designations, boundaries, and spatial geometries
from UNEP-WCMC's Protected Planet API v4 (https://api.protectedplanet.net).

Key capabilities:
  - Search protected areas by country (e.g. IND, LKA), marine flag, and name.
  - Fetch detailed protected area data including GeoJSON polygon boundaries.
  - High-performance in-memory point-in-polygon checks via Shapely as a
    direct live fallback when PostGIS is unavailable or incomplete.
  - Sync/enrichment routine to update the PostGIS `mpa_boundaries` table with
    live Protected Planet API v4 data and correct marine surface area metrics.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from shapely.geometry import Point, shape
from shapely.prepared import prep

from app.core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.protectedplanet.net/v4"
REQUEST_TIMEOUT = 30

REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = REPO_ROOT / "data" / "raw" / "boundaries" / "protected_planet" / "api_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# In-memory spatial index cache: (last_updated, [ (prepared_geom, properties) ])
_SPATIAL_INDEX_CACHE: list[tuple[Any, dict]] = []
_SPATIAL_INDEX_LOCK = asyncio.Lock()


def is_configured() -> bool:
    """Return True if Protected Planet API key is configured."""
    return bool(settings.PROTECTED_PLANET_API_KEY and settings.PROTECTED_PLANET_API_KEY.strip())


def _unavailable(reason: str) -> dict:
    return {
        "status": "unavailable",
        "source": "Protected Planet (api.protectedplanet.net)",
        "reason": reason,
    }


async def search_protected_areas(
    country: str = "IND",
    marine: bool = True,
    query: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    """
    Search protected areas via Protected Planet API v4.
    """
    if not is_configured():
        return _unavailable("PROTECTED_PLANET_API_KEY not configured in .env")

    params: dict[str, Any] = {
        "token": settings.PROTECTED_PLANET_API_KEY,
        "country": country,
        "marine": str(marine).lower(),
        "page": page,
        "per_page": per_page,
    }
    if query:
        params["q"] = query

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(f"{BASE_URL}/protected_areas/search", params=params)
            if resp.status_code != 200:
                return {
                    "status": "failed",
                    "status_code": resp.status_code,
                    "error": resp.text,
                    "source": "Protected Planet API v4",
                }
            data = resp.json()
            areas = data.get("protected_areas", [])
            return {
                "status": "success",
                "count": len(areas),
                "country": country,
                "marine": marine,
                "protected_areas": areas,
                "source": "Protected Planet API v4",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as exc:
        logger.warning("[protected_planet] Search failed: %s", exc)
        return {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "source": "Protected Planet API v4",
        }


async def get_protected_area(site_id: int) -> dict:
    """
    Retrieve full details of a specific protected area by site_id, including GeoJSON.
    Caches locally to disk to avoid repeated API calls for unchanged boundaries.
    """
    if not is_configured():
        return _unavailable("PROTECTED_PLANET_API_KEY not configured in .env")

    cache_file = CACHE_DIR / f"pa_{site_id}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            return {
                "status": "success",
                "protected_area": cached_data,
                "cached": True,
                "source": "Protected Planet API v4 (local cache)",
            }
        except Exception:
            pass

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(
                f"{BASE_URL}/protected_areas/{site_id}",
                params={"token": settings.PROTECTED_PLANET_API_KEY},
            )
            if resp.status_code != 200:
                return {
                    "status": "failed",
                    "status_code": resp.status_code,
                    "error": resp.text,
                    "source": "Protected Planet API v4",
                }
            data = resp.json()
            pa = data.get("protected_area", {})
            # Cache to disk
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(pa, f)
            except Exception as e:
                logger.debug("Failed caching PA %s: %s", site_id, e)

            return {
                "status": "success",
                "protected_area": pa,
                "cached": False,
                "source": "Protected Planet API v4",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as exc:
        logger.warning("[protected_planet] get_protected_area(%s) failed: %s", site_id, exc)
        return {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "source": "Protected Planet API v4",
        }


async def get_country_summary(iso3: str = "IND") -> dict:
    """
    Fetch country-level conservation metrics and overview.
    """
    if not is_configured():
        return _unavailable("PROTECTED_PLANET_API_KEY not configured in .env")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(
                f"{BASE_URL}/countries/{iso3}",
                params={"token": settings.PROTECTED_PLANET_API_KEY},
            )
            if resp.status_code != 200:
                return {"status": "failed", "error": resp.text}
            return {
                "status": "success",
                "country": resp.json().get("country", {}),
                "source": "Protected Planet API v4",
            }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


async def fetch_marine_protected_areas(countries: list[str] = ["IND"]) -> list[dict]:
    """
    Fetch all marine protected areas for specified countries, returning list of PA objects
    with GeoJSON geometry populated. Concurrent fetching with rate limiting.
    """
    all_pas = []
    sem = asyncio.Semaphore(5)

    async def _fetch_one(site_id: int):
        async with sem:
            detail_res = await get_protected_area(site_id)
            if detail_res.get("status") == "success" and detail_res.get("protected_area"):
                return detail_res["protected_area"]
            return None

    for country in countries:
        search_res = await search_protected_areas(country=country, marine=True, per_page=50)
        if search_res.get("status") != "success":
            continue
        items = search_res.get("protected_areas", [])
        site_ids = [item["site_id"] for item in items if item.get("site_id")]
        results = await asyncio.gather(*[_fetch_one(sid) for sid in site_ids])
        all_pas.extend([r for r in results if r is not None])

    return all_pas


async def _get_or_build_spatial_index(countries: list[str] = ["IND"]) -> list[tuple[Any, dict]]:
    """
    Builds or returns an in-memory spatial index of prepared geometries for fast point checks.
    """
    global _SPATIAL_INDEX_CACHE
    async with _SPATIAL_INDEX_LOCK:
        if _SPATIAL_INDEX_CACHE:
            return _SPATIAL_INDEX_CACHE

        pas = await fetch_marine_protected_areas(countries=countries)
        index_entries = []
        for pa in pas:
            geojson = pa.get("geojson")
            if not geojson or not isinstance(geojson, dict):
                continue
            geom_data = geojson.get("geometry")
            if not geom_data:
                continue
            try:
                geom = shape(geom_data)
                prepared_geom = prep(geom)
                props = {
                    "site_id": pa.get("site_id"),
                    "name": pa.get("name_english") or pa.get("name"),
                    "marine": pa.get("marine"),
                    "gis_marine_area": pa.get("gis_marine_area"),
                    "iucn_category": (pa.get("iucn_category") or {}).get("name") if isinstance(pa.get("iucn_category"), dict) else pa.get("iucn_category"),
                    "designation": (pa.get("designation") or {}).get("name") if isinstance(pa.get("designation"), dict) else pa.get("designation"),
                }
                index_entries.append((prepared_geom, props))
            except Exception as e:
                logger.debug("Failed to index PA geom: %s", e)

        _SPATIAL_INDEX_CACHE = index_entries
        return _SPATIAL_INDEX_CACHE


async def check_point_in_mpa_api(lat: float, lon: float, countries: list[str] = ["IND"]) -> dict:
    """
    Check if a coordinate (lat, lon) is inside any Marine Protected Area using
    Protected Planet API v4 boundaries and in-memory spatial indexing.
    """
    if not is_configured():
        return _unavailable("PROTECTED_PLANET_API_KEY not configured")

    try:
        index_entries = await _get_or_build_spatial_index(countries=countries)
        point = Point(lon, lat)

        for prep_geom, props in index_entries:
            if prep_geom.contains(point):
                return {
                    "status": "success",
                    "inside_mpa": True,
                    "name": props["name"],
                    "site_id": props["site_id"],
                    "designation": props["designation"],
                    "iucn_category": props["iucn_category"],
                    "marine_area_km2": props["gis_marine_area"],
                    "source": "Protected Planet API v4 (live boundary verification)",
                }

        return {
            "status": "success",
            "inside_mpa": False,
            "source": "Protected Planet API v4 (live boundary verification)",
        }
    except Exception as exc:
        logger.warning("[protected_planet] Point check failed: %s", exc)
        return {
            "status": "failed",
            "error": str(exc),
            "source": "Protected Planet API v4",
        }


async def sync_mpas_to_db(session, countries: list[str] = ["IND"]) -> dict:
    """
    Synchronizes live Protected Planet API v4 MPAs for India and neighboring waters
    into the PostGIS `mpa_boundaries` table, ensuring up-to-date geometry,
    designations, and calculated marine areas.
    """
    if not is_configured():
        return _unavailable("PROTECTED_PLANET_API_KEY not configured")

    from sqlalchemy import text

    pas = await fetch_marine_protected_areas(countries=countries)
    synced_count = 0

    for pa in pas:
        site_id = pa.get("site_id")
        name = pa.get("name_english") or pa.get("name")
        geojson = pa.get("geojson")
        if not site_id or not geojson or not geojson.get("geometry"):
            continue

        geom_json = json.dumps(geojson["geometry"])
        gis_m_area = float(pa.get("gis_marine_area") or 0.0)
        rep_m_area = float(pa.get("reported_marine_area") or 0.0)
        rep_area = float(pa.get("reported_area") or 0.0)
        gis_area = float(pa.get("gis_area") or 0.0)
        iso3 = pa.get("parent_iso3") or "IND"
        desig_eng = (pa.get("designation") or {}).get("name") if isinstance(pa.get("designation"), dict) else str(pa.get("designation") or "")
        iucn_cat = (pa.get("iucn_category") or {}).get("name") if isinstance(pa.get("iucn_category"), dict) else str(pa.get("iucn_category") or "")

        # Check if row exists in mpa_boundaries
        check = await session.execute(
            text('SELECT "SITE_ID" FROM mpa_boundaries WHERE "SITE_ID" = :site_id'),
            {"site_id": site_id},
        )
        existing = check.scalar()

        if existing:
            # Update existing row with live GIS_M_AREA, REALM, DESIG_ENG, etc.
            await session.execute(
                text(
                    """
                    UPDATE mpa_boundaries
                    SET "GIS_M_AREA" = :gis_m_area,
                        "REP_M_AREA" = :rep_m_area,
                        "REALM" = 'Marine',
                        "DESIG_ENG" = COALESCE(:desig_eng, "DESIG_ENG"),
                        "IUCN_CAT" = COALESCE(:iucn_cat, "IUCN_CAT")
                    WHERE "SITE_ID" = :site_id
                    """
                ),
                {
                    "site_id": site_id,
                    "gis_m_area": gis_m_area,
                    "rep_m_area": rep_m_area,
                    "desig_eng": desig_eng,
                    "iucn_cat": iucn_cat,
                },
            )
        else:
            # Insert new MPA feature from API v4 into MultiPolygon column
            geom_type = geojson["geometry"].get("type", "")
            if geom_type == "Point":
                # Buffer point based on reported area or 1000m default
                import math
                radius_m = math.sqrt(rep_area * 1_000_000 / math.pi) if rep_area > 0 else 1000.0
                geom_sql = "ST_Multi(ST_Buffer(ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326)::geography, :radius_m)::geometry)"
                params = {
                    "site_id": site_id,
                    "gis_m_area": gis_m_area,
                    "rep_m_area": rep_m_area,
                    "gis_area": gis_area,
                    "rep_area": rep_area,
                    "iso3": iso3,
                    "name": name,
                    "desig_eng": desig_eng,
                    "iucn_cat": iucn_cat,
                    "geom_json": geom_json,
                    "radius_m": radius_m,
                }
            elif geom_type == "Polygon":
                geom_sql = "ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326))"
                params = {
                    "site_id": site_id,
                    "gis_m_area": gis_m_area,
                    "rep_m_area": rep_m_area,
                    "gis_area": gis_area,
                    "rep_area": rep_area,
                    "iso3": iso3,
                    "name": name,
                    "desig_eng": desig_eng,
                    "iucn_cat": iucn_cat,
                    "geom_json": geom_json,
                }
            else:
                geom_sql = "ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326)"
                params = {
                    "site_id": site_id,
                    "gis_m_area": gis_m_area,
                    "rep_m_area": rep_m_area,
                    "gis_area": gis_area,
                    "rep_area": rep_area,
                    "iso3": iso3,
                    "name": name,
                    "desig_eng": desig_eng,
                    "iucn_cat": iucn_cat,
                    "geom_json": geom_json,
                }

            await session.execute(
                text(
                    f"""
                    INSERT INTO mpa_boundaries (
                        "SITE_ID", "GIS_M_AREA", "REP_M_AREA", "GIS_AREA", "REP_AREA",
                        "ISO3", "PRNT_ISO3", "REALM", name, "NAME_ENG", "DESIG_ENG", "IUCN_CAT",
                        geometry
                    ) VALUES (
                        :site_id, :gis_m_area, :rep_m_area, :gis_area, :rep_area,
                        :iso3, :iso3, 'Marine', :name, :name, :desig_eng, :iucn_cat,
                        {geom_sql}
                    )
                    """
                ),
                params,
            )
        synced_count += 1

    await session.commit()
    return {
        "status": "success",
        "synced_count": synced_count,
        "source": "Protected Planet API v4",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
