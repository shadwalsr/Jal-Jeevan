"""
INCOIS ERDDAP adapter — Ocean State Forecast (OSF).
No registration required. Public ERDDAP endpoint.
Docs: https://erddap.incois.gov.in/erddap

NOTE: exact dataset_id / variable names must be confirmed against the live
ERDDAP catalog (https://erddap.incois.gov.in/erddap/index.html) — INCOIS
dataset IDs change occasionally. This adapter is a working template; the
Data Engineer should verify dataset_id against the catalog on first run.
"""
import asyncio
from datetime import datetime, timezone

from erddapy import ERDDAP

from app.core.config import settings
from app.tools._executor import network_executor


async def get_incois_wave_forecast(lat: float, lon: float) -> dict:
    """
    Fetch nearest wave height / period forecast from INCOIS OSF via ERDDAP.
    Returns a normalized dict with provenance metadata (per PRD Section 8 —
    every value must carry source + timestamp).
    """
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        e = ERDDAP(server=settings.INCOIS_ERDDAP_URL, protocol="griddap")
        e.dataset_id = "incois_osf_wave"
        e.requests_kwargs = {"timeout": 4, "verify": False}
        loop = asyncio.get_running_loop()

        def _fetch_incois():
            e.griddap_initialize()
            e.variables = ["wave_height", "wave_period"]
            e.constraints["latitude>="] = lat - 0.25
            e.constraints["latitude<="] = lat + 0.25
            e.constraints["longitude>="] = lon - 0.25
            e.constraints["longitude<="] = lon + 0.25
            return e.to_xarray()

        ds = await asyncio.wait_for(loop.run_in_executor(network_executor, _fetch_incois), timeout=5)
        return {
            "source": "INCOIS OSF (ERDDAP)",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "lat": lat,
            "lon": lon,
            "data": ds.to_dict(),
        }
    except Exception as exc:  # pragma: no cover - network dependent
        print(f"[incois_adapter] {type(exc).__name__}: {exc}")
        return {
            "source": "INCOIS OSF (ERDDAP)",
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "fallback_recommended": "Copernicus Marine or Open-Meteo Marine",
        }
