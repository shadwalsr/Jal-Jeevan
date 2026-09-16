"""
/map/boundaries — the static exclusion layers the map draws underneath
everything else (PRD §7.1a, §16.7).

These are the *Stage 1* layer: legal and physical boundaries that veto a
candidate outright, as opposed to the risk field, which scores candidates
that already passed. They are rendered as hatched exclusions rather than
filled risk colours precisely so the two never look like the same thing —
a boundary you crossed is categorically different from a number that got
high, and the map must not blur that (see risk_agent.py's two-stage design).

Three things make this cheap enough to call on every map move:

1. **Bbox filtering.** Never return the whole world's polygons.
2. **Server-side simplification.** WDPA geometry is far more detailed than
   any screen can show. Measured on the Odisha demo box: 84,479 bytes raw
   vs 3,619 bytes at a 0.005 deg tolerance — a 23x reduction with no
   visible difference at map scale. Tolerance scales with the requested
   bbox, so a zoomed-out view gets coarser geometry, not more bytes.
3. **Long cache.** Boundaries do not change between requests; the PRD's
   own freshness policy lists them as a weekly integrity check, not live
   data.
"""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.core.cache import cache_get, cache_set
from app.db.session import async_session
from app.tools import protected_planet_adapter

router = APIRouter(prefix="/map", tags=["map"])

# Whole-of-India default view, used when the caller does not supply a bbox.
DEFAULT_BBOX = (6.0, 68.0, 24.0, 90.0)  # min_lat, min_lon, max_lat, max_lon

# A request wider than this is a mistake, not a map view.
MAX_SPAN_DEG = 40.0

VALID_TYPES = {"eez", "mpa", "ports"}


def _auto_tolerance(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> float:
    """
    Simplification tolerance in degrees, scaled to the requested view.

    Roughly one screen pixel's worth of detail for a ~600px map: anything
    finer cannot be seen and only costs bytes. Clamped so a very tight zoom
    still gets real geometry and a very wide one still gets simplified.
    """
    span = max(max_lat - min_lat, max_lon - min_lon)
    return max(0.0005, min(0.05, span / 600.0))


async def _table_exists(session, table_name: str) -> bool:
    result = await session.execute(
        text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"public.{table_name}"}
    )
    return bool(result.scalar())


@router.get("/boundaries")
async def get_boundaries(
    min_lat: float = Query(DEFAULT_BBOX[0], ge=-90, le=90),
    min_lon: float = Query(DEFAULT_BBOX[1], ge=-180, le=180),
    max_lat: float = Query(DEFAULT_BBOX[2], ge=-90, le=90),
    max_lon: float = Query(DEFAULT_BBOX[3], ge=-180, le=180),
    types: str = Query("eez,mpa,ports", description="comma-separated: eez, mpa, ports"),
    marine_only: bool = Query(
        True,
        description=(
            "MPA only. WDPA carries terrestrial and freshwater protected areas as well as "
            "marine ones — of 1,129 loaded polygons only 203 have any marine area. Leaving "
            "this on keeps lakes and forest reserves off a sea chart."
        ),
    ),
):
    """
    Returns one GeoJSON FeatureCollection per requested layer.

    `eez` features carry `is_indian_eez`. That flag carries the whole
    meaning of the layer: India's own EEZ is the *permitted* area, while a
    neighbouring EEZ is the practical arrest-risk boundary — crossing into
    Sri Lankan or Pakistani waters is the single most consequential
    boundary event for an Indian fisherman, far more so than the high seas.
    Clients must not paint the two the same way.
    """
    if max_lat <= min_lat or max_lon <= min_lon:
        raise HTTPException(status_code=400, detail="max_lat/max_lon must be greater than min_lat/min_lon")
    if (max_lat - min_lat) > MAX_SPAN_DEG or (max_lon - min_lon) > MAX_SPAN_DEG:
        raise HTTPException(
            status_code=400,
            detail=f"Requested area is too large; each side must be under {MAX_SPAN_DEG} degrees.",
        )

    requested = {t.strip().lower() for t in types.split(",") if t.strip()}
    unknown = requested - VALID_TYPES
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown layer type(s): {', '.join(sorted(unknown))}")
    if not requested:
        raise HTTPException(status_code=400, detail="No layer types requested.")

    tolerance = _auto_tolerance(min_lat, min_lon, max_lat, max_lon)

    # Cache key rounds the bbox so panning slightly reuses the same entry.
    cache_extra = (
        f"{round(min_lat, 1)},{round(min_lon, 1)},{round(max_lat, 1)},{round(max_lon, 1)}"
        f":{','.join(sorted(requested))}:{marine_only}"
    )
    centre_lat = (min_lat + max_lat) / 2
    centre_lon = (min_lon + max_lon) / 2
    cached = await cache_get("boundaries", centre_lat, centre_lon, extra=cache_extra)
    if cached is not None:
        return cached

    bbox_params = {
        "min_lat": min_lat,
        "min_lon": min_lon,
        "max_lat": max_lat,
        "max_lon": max_lon,
        "tol": tolerance,
    }
    envelope = "ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326)"
    empty = {"type": "FeatureCollection", "features": []}
    result: dict = {
        "bbox": [min_lat, min_lon, max_lat, max_lon],
        "simplify_tolerance_deg": round(tolerance, 5),
    }

    async with async_session() as session:
        if "eez" in requested:
            if not await _table_exists(session, "eez_boundaries"):
                result["eez"] = {**empty, "unavailable": "eez_boundaries not loaded"}
            else:
                rows = await session.execute(
                    text(
                        f"""
                        SELECT json_build_object(
                          'type', 'FeatureCollection',
                          'features', COALESCE(json_agg(f), '[]'::json)
                        )
                        FROM (
                          SELECT json_build_object(
                            'type', 'Feature',
                            'geometry', ST_AsGeoJSON(
                                ST_SimplifyPreserveTopology(ST_Intersection(geometry, {envelope}), :tol)
                            )::json,
                            'properties', json_build_object(
                              'territory',      "TERRITORY1",
                              'sovereign',      "SOVEREIGN1",
                              'iso',            "ISO_TER1",
                              'pol_type',       "POL_TYPE",
                              'is_indian_eez',  ("TERRITORY1" ILIKE '%India%'
                                                 OR "TERRITORY1" ILIKE '%Andaman%'),
                              'exclusion',      NOT ("TERRITORY1" ILIKE '%India%'
                                                 OR "TERRITORY1" ILIKE '%Andaman%')
                            )
                          ) AS f
                          FROM eez_boundaries
                          WHERE ST_Intersects(geometry, {envelope})
                        ) sub
                        """
                    ),
                    bbox_params,
                )
                result["eez"] = rows.scalar() or empty

        if "mpa" in requested:
            if not await _table_exists(session, "mpa_boundaries"):
                result["mpa"] = {**empty, "unavailable": "mpa_boundaries not loaded"}
            else:
                marine_clause = (
                    'AND (COALESCE("REP_M_AREA", 0) > 0 OR COALESCE("GIS_M_AREA", 0) > 0 OR "REALM" IN (\'Marine\', \'Coastal\'))'
                    if marine_only
                    else ""
                )
                rows = await session.execute(
                    text(
                        f"""
                        SELECT json_build_object(
                          'type', 'FeatureCollection',
                          'features', COALESCE(json_agg(f), '[]'::json)
                        )
                        FROM (
                          SELECT json_build_object(
                            'type', 'Feature',
                            'geometry', ST_AsGeoJSON(
                                ST_SimplifyPreserveTopology(ST_Intersection(geometry, {envelope}), :tol)
                            )::json,
                            'properties', json_build_object(
                              'name',        name,
                              'designation', "DESIG_ENG",
                              'iucn_cat',    "IUCN_CAT",
                              'no_take',     "NO_TAKE",
                              'marine_area_km2', COALESCE(NULLIF("GIS_M_AREA", 0), "REP_M_AREA"),
                              'exclusion',   true
                            )
                          ) AS f
                          FROM mpa_boundaries
                          WHERE ST_Intersects(geometry, {envelope})
                          {marine_clause}
                        ) sub
                        """
                    ),
                    bbox_params,
                )
                result["mpa"] = rows.scalar() or empty

        if "ports" in requested:
            if not await _table_exists(session, "ports"):
                result["ports"] = {**empty, "unavailable": "ports table not loaded"}
            else:
                rows = await session.execute(
                    text(
                        f"""
                        SELECT json_build_object(
                          'type', 'FeatureCollection',
                          'features', COALESCE(json_agg(f), '[]'::json)
                        )
                        FROM (
                          SELECT json_build_object(
                            'type', 'Feature',
                            'geometry', ST_AsGeoJSON(geom)::json,
                            'properties', json_build_object(
                              'name', name, 'state', state, 'exclusion', false
                            )
                          ) AS f
                          FROM ports
                          WHERE ST_Intersects(geom, {envelope})
                        ) sub
                        """
                    ),
                    bbox_params,
                )
                result["ports"] = rows.scalar() or empty

    # Known gap, surfaced in the payload rather than left for a UI to discover:
    # Gahirmatha and Bhitarkanika — the marine sanctuaries that actually matter
    # off Odisha — are absent from the loaded WDPA extract (verified 27 Aug
    # 2026). A client showing this layer must not imply the absence of a
    # polygon means the absence of a restriction.
    result["coverage_note"] = (
        "Protected-area coverage is the loaded WDPA extract and is known to be incomplete "
        "for Indian marine sanctuaries — Gahirmatha and Bhitarkanika are not present. "
        "Absence of a polygon here does not prove a location is unrestricted."
    )

    await cache_set("boundaries", centre_lat, centre_lon, result, extra=cache_extra)
    return result


@router.get("/protected-planet/search")
async def search_protected_areas(
    country: str = Query("IND", description="ISO3 country code (e.g. IND, LKA, MDV)"),
    marine: bool = Query(True, description="Filter for marine protected areas"),
    q: str | None = Query(None, description="Optional text query filter"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=50),
):
    """
    Direct search against Protected Planet API v4.
    """
    if not protected_planet_adapter.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Protected Planet API is not configured. Set PROTECTED_PLANET_API_KEY in .env",
        )
    res = await protected_planet_adapter.search_protected_areas(
        country=country, marine=marine, query=q, page=page, per_page=per_page
    )
    if res.get("status") == "failed":
        raise HTTPException(status_code=res.get("status_code", 502), detail=res.get("error"))
    return res


@router.get("/protected-planet/{site_id}")
async def get_protected_area(site_id: int):
    """
    Retrieve single protected area details with GeoJSON from Protected Planet API v4.
    """
    if not protected_planet_adapter.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Protected Planet API is not configured. Set PROTECTED_PLANET_API_KEY in .env",
        )
    res = await protected_planet_adapter.get_protected_area(site_id)
    if res.get("status") == "failed":
        raise HTTPException(status_code=res.get("status_code", 502), detail=res.get("error"))
    return res


@router.post("/protected-planet/sync")
async def sync_protected_planet():
    """
    Trigger live sync from Protected Planet API v4 into local PostGIS mpa_boundaries table.
    """
    if not protected_planet_adapter.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Protected Planet API is not configured. Set PROTECTED_PLANET_API_KEY in .env",
        )
    async with async_session() as session:
        return await protected_planet_adapter.sync_mpas_to_db(session, countries=["IND", "LKA", "MDV"])

