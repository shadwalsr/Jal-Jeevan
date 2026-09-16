"""
IMD adapter — India Meteorological Department.
Requires IMD_API_KEY (see .env.example — registration needed, 1-3 days).

NOTE: IMD does not currently publish one single stable public REST API the
way INCOIS/NOAA do via ERDDAP. As of Phase 0 the team should confirm the
exact endpoint via https://mausam.imd.gov.in (city/coastal forecast) and
https://city.imd.gov.in (JSON API used by IMD's own site) — both are used
in practice by third-party integrations. This adapter isolates that
uncertainty behind one function so the rest of the system is unaffected
if the endpoint changes.
"""
from datetime import datetime, timezone

import httpx

from app.core.config import settings

IMD_BASE_URL = "https://city.imd.gov.in/api"  # TODO(data-eng): verify/replace


async def get_imd_current_weather(lat: float, lon: float) -> dict:
    if not settings.IMD_API_KEY:
        return {
            "source": "IMD",
            "status": "unavailable",
            "reason": "IMD_API_KEY not configured (registration pending)",
        }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{IMD_BASE_URL}/weather",
                params={"lat": lat, "lon": lon, "key": settings.IMD_API_KEY},
            )
            resp.raise_for_status()
            payload = resp.json()
        return {
            "source": "IMD",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "lat": lat,
            "lon": lon,
            "data": payload,
        }
    except Exception as exc:  # pragma: no cover - network dependent
        print(f"[imd_adapter] {type(exc).__name__}: {exc}")
        return {
            "source": "IMD",
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "fallback_recommended": "Open-Meteo Marine or ERA5",
        }
