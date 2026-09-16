"""
Nominatim (OpenStreetMap) geocoding — free, no API key. Used only to turn a
place name mentioned in a chat query ("near Puri") into coordinates; not a
substitute for GPS input when the user's actual vessel position is known.
"""
import asyncio
from datetime import datetime, timezone

import httpx

from app.core.cache import cache_get, cache_set

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy requires a descriptive User-Agent identifying the app.
HEADERS = {"User-Agent": "JalJeev-SIH26176/0.1 (marine decision-support prototype)"}


async def geocode(place_name: str) -> dict:
    # Not a spatial lookup, so lat/lon are unused as cache-key inputs here —
    # the place name itself (via `extra`) is the actual key.
    cached = await cache_get("geocode", 0, 0, extra=place_name.lower().strip())
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient(timeout=10, headers=HEADERS) as client:
            resp = await asyncio.wait_for(
                client.get(NOMINATIM_URL, params={"q": place_name, "format": "json", "limit": 1}), timeout=10
            )
            resp.raise_for_status()
            results = resp.json()
        if not results:
            return {"status": "not_found", "query": place_name}
        r = results[0]
        result = {
            "status": "success",
            "query": place_name,
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "display_name": r.get("display_name"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        await cache_set("geocode", 0, 0, result, extra=place_name.lower().strip())
        return result
    except Exception as exc:  # pragma: no cover - network dependent
        return {"status": "failed", "query": place_name, "error": str(exc)}
