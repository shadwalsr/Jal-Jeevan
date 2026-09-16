"""
NOAA OISST v2.1 — daily 1/4-degree global SST, no auth, via public ERDDAP.
Used as one of the three consensus SST sources (PRD Section 7.3).
"""
import asyncio
from datetime import datetime, timezone

from erddapy import ERDDAP

from app.core.cache import cache_get, cache_set
from app.core.config import settings
from app.tools._executor import netcdf_lock, network_executor


async def get_sst(lat: float, lon: float) -> dict:
    cached = await cache_get("sst", lat, lon)
    if cached is not None:
        return cached
    try:
        e = ERDDAP(server=settings.NOAA_ERDDAP_URL, protocol="griddap")
        e.dataset_id = "ncdcOisst21Agg_LonPM180"
        # erddapy validates a fresh `e.constraints = {...}` assignment against
        # the keys it expects from griddap_initialize() and raises "keys in
        # e.constraints have changed. Re-run e.griddap_initialize" if they
        # don't match (confirmed live 26 Aug 2026 — this was failing SST on
        # every request). griddap_initialize() must run first to populate
        # the dataset's real constraint keys/defaults, then mutate that dict
        # in place rather than replacing it.
        e.griddap_initialize()
        e.variables = ["sst"]
        e.constraints["latitude>="] = lat - 0.25
        e.constraints["latitude<="] = lat + 0.25
        e.constraints["longitude>="] = lon - 0.25
        e.constraints["longitude<="] = lon + 0.25
        loop = asyncio.get_running_loop()
        # netcdf_lock: erddapy decodes the response through xarray/netCDF —
        # same non-thread-safe HDF5 stack as tide and Copernicus.
        def _to_xarray_locked():
            with netcdf_lock:
                return e.to_xarray()

        ds = await asyncio.wait_for(loop.run_in_executor(network_executor, _to_xarray_locked), timeout=10)
        sst_val = float(ds["sst"].mean().values)
        result = {
            "source": "NOAA OISST v2.1",
            "status": "success",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "sst_c": round(sst_val, 2),
        }
        await cache_set("sst", lat, lon, result)
        return result
    except Exception as exc:  # pragma: no cover - network dependent
        # Never swallow silently — see CLAUDE.md gotcha #4 (a real ~20s
        # "hang" once turned out to be a masked 429 found only by logging
        # type+message). Bare str(exc) can be empty (e.g. TimeoutError).
        print(f"[noaa_oisst_adapter] {type(exc).__name__}: {exc}")
        return {"source": "NOAA OISST v2.1", "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
