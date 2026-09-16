"""
Copernicus Marine adapter. Uses the `copernicusmarine` toolbox with
username/password login (there is no separate API key for this service —
see PRD Appendix / README). Provides currents + SST + waves as a
consensus/fallback source.

copernicusmarine caches the login token locally after the first successful
`login()` call, so this only needs to authenticate once per environment.
"""
import asyncio
from datetime import datetime, timezone

from app.core.cache import cache_get, cache_set
from app.core.config import settings
from app.tools import _circuit_breaker
from app.tools._executor import netcdf_lock, network_executor

_BREAKER_NAME = "copernicus"

_logged_in = False

# Bounds how many copernicusmarine datasets may be OPEN at once, process-wide.
#
# Even a 0.5-degree subset costs GBs, because `open_dataset` materialises the
# chunk index of a GLOBAL 1/12-degree hourly store — the size of the area you
# ask for barely matters. Route verification opens physics+BGC for up to 3
# candidates, so six of those can be live at once.
#
# Measured peak working set, one cold /marine/safest-route (27 Aug 2026):
#   no close, cap 2   ->  8463 MB   (process was killed outright mid-prewarm)
#   close, cap 2      ->  7236 MB, 38.7s
#   close, cap 1      ->  7331 MB, 50.8s
#
# So this cap does NOT meaningfully bound peak memory: freed arenas are not
# returned to the OS, so serialising the opens spreads the same total
# allocation over more wall-clock. Cap 1 measured strictly worse — same
# memory, 12s slower — so it stays at 2. This comment records the
# measurement rather than the intuition, because the intuition was wrong.
#
# What actually helped was closing promptly (~1.2 GB) and, far more
# importantly, not crashing — see _open_read_close. The real fix for the
# remaining ~7 GB is to stop re-opening the global store on every call: open
# each dataset ONCE process-wide and subset the cached lazy object under a
# lock. Not done yet; it needs care around xarray thread-safety, and
# prewarming makes the cold path rare in practice.
MAX_CONCURRENT_DATASET_OPENS = 2
_open_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DATASET_OPENS)


def _ensure_login():
    global _logged_in
    if _logged_in:
        return
    if not (settings.COPERNICUS_MARINE_USERNAME and settings.COPERNICUS_MARINE_PASSWORD):
        raise RuntimeError("Copernicus Marine credentials not configured")
    import copernicusmarine

    copernicusmarine.login(
        username=settings.COPERNICUS_MARINE_USERNAME,
        password=settings.COPERNICUS_MARINE_PASSWORD,
        force_overwrite=True,
    )
    _logged_in = True


def _open_read_close(dataset_id: str, variables: list[str], lat: float, lon: float,
                     half_deg: float, min_depth: float, max_depth: float,
                     fields: dict[str, tuple[str, int]]) -> dict:
    """
    Open a Copernicus dataset, pull the scalars we need, and close it —
    ALL ON ONE THREAD.

    This runs entirely inside network_executor, and that is not a style
    preference (27 Aug 2026, found the hard way):

    1. netCDF4/HDF5 is not thread-safe. Opening a dataset in an executor
       worker and then closing it from the event-loop thread crashes the
       interpreter outright — no Python traceback, the process just
       disappears. Observed live: the server died ~19s into a route query
       with nothing in either log.
    2. The actual data transfer is not in `open_dataset` at all, it is in
       `.mean().values` — xarray is lazy. So the previous shape of this code
       did the network fetch ON THE EVENT LOOP while only the cheap open
       call was in the executor, quietly stalling every other coroutine
       (CLAUDE.md gotcha #2, hiding one level deeper than usual).
    3. Closing promptly, rather than waiting for GC, is what keeps memory
       bounded — see MAX_CONCURRENT_DATASET_OPENS.

    `fields` maps result-key -> (variable name, rounding precision).
    """
    import copernicusmarine

    # netcdf_lock: HDF5 underneath is not thread-safe and this pool runs the
    # tide reader concurrently — see app/tools/_executor.py.
    with netcdf_lock:
        ds = copernicusmarine.open_dataset(
            dataset_id=dataset_id,
            variables=variables,
            minimum_longitude=lon - half_deg,
            maximum_longitude=lon + half_deg,
            minimum_latitude=lat - half_deg,
            maximum_latitude=lat + half_deg,
            minimum_depth=min_depth,
            maximum_depth=max_depth,
        )
        try:
            latest = ds.isel(time=-1)
            return {
                key: round(float(latest[var].mean().values), precision)
                for key, (var, precision) in fields.items()
            }
        finally:
            ds.close()


async def get_physics_subset(lat: float, lon: float) -> dict:
    """
    Subset sea temperature / currents / sea level at a point from the
    global ocean physics analysis-forecast product.
    Runs the (blocking, network-bound) copernicusmarine call directly —
    acceptable for Phase 0; move to a Celery task once ingestion is scheduled.
    """
    cached = await cache_get("copernicus", lat, lon)
    if cached is not None:
        return cached

    if _circuit_breaker.is_open(_BREAKER_NAME):
        return {
            "source": "Copernicus Marine",
            "status": "unavailable",
            "reason": "circuit breaker open — Copernicus has failed repeatedly in the last minute, skipping to save time",
        }

    try:
        # A hard timeout here matters: copernicusmarine's calls are
        # synchronous network I/O run in a thread, and have been observed
        # to hang indefinitely (no internal timeout) when the service is
        # slow/throttled — without wait_for, that would block this request
        # forever with no fallback ever triggering.
        # Kept tight: if Copernicus is slow, the Risk/Route agents should get
        # a fast "unavailable" and fall back to Open-Meteo/NOAA rather than
        # stall the whole request — a slow source failing fast beats a slow
        # source blocking everything (PRD's graceful-degradation principle).
        loop = asyncio.get_running_loop()
        await asyncio.wait_for(loop.run_in_executor(network_executor, _ensure_login), timeout=10)
        import functools

        async with _open_semaphore:
            values = await asyncio.wait_for(
                loop.run_in_executor(
                    network_executor,
                    functools.partial(
                        _open_read_close,
                        # NOTE: mlotst (mixed-layer depth) is NOT in this hourly
                        # product despite being in the combined "_my_" reanalysis
                        # dataset used for the bulk download — confirmed by a
                        # live 404 on the variable name. Left out rather than
                        # guessing at a different dataset ID; MLD stays
                        # unavailable live until that's tracked down.
                        dataset_id="cmems_mod_glo_phy_anfc_0.083deg_PT1H-m",
                        variables=["thetao", "uo", "vo", "zos", "so"],
                        lat=lat,
                        lon=lon,
                        half_deg=0.25,
                        min_depth=0.49,
                        max_depth=0.5,
                        fields={
                            "sst_c": ("thetao", 2),
                            "current_u_ms": ("uo", 3),
                            "current_v_ms": ("vo", 3),
                            "sea_level_anomaly_m": ("zos", 3),
                            "salinity_psu": ("so", 3),
                        },
                    ),
                ),
                # Raised from 12s: this budget now covers the actual data
                # transfer too, not just the (cheap, lazy) dataset open — the
                # transfer used to happen outside any timeout at all.
                timeout=25,
            )
        result = {
            "source": "Copernicus Marine",
            "status": "success",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            **values,
        }
        await cache_set("copernicus", lat, lon, result)
        _circuit_breaker.record_success(_BREAKER_NAME)
        return result
    except Exception as exc:  # pragma: no cover - network dependent
        # Never swallow silently — see CLAUDE.md gotcha #4. Also: str(exc)
        # is empty for asyncio.TimeoutError, which made every timeout here
        # show up as an unhelpful blank "error": "" with no way to tell a
        # timeout from any other failure — always include the exception type.
        print(f"[copernicus_adapter.get_physics_subset] {type(exc).__name__}: {exc}")
        _circuit_breaker.record_failure(_BREAKER_NAME)
        return {"source": "Copernicus Marine", "status": "failed", "error": f"{type(exc).__name__}: {exc}"}


async def get_bgc_subset(lat: float, lon: float) -> dict:
    """
    Chlorophyll from the global biogeochemistry analysis-forecast product.
    Unlike the combined "_my_" reanalysis dataset used for the bulk 2023
    download, the live "_anfc_" catalog splits biogeochemistry into
    separate thematic datasets (confirmed live: requesting chl/no3/o2/nppv
    from one combined dataset ID 404'd) — "-pft-" (phytoplankton functional
    types) carries chlorophyll; nitrate/oxygen/NPP live in "-nut-"/"-bio-"
    and aren't fetched here yet (lower priority than the HAB proxy this
    exists for — see risk_agent.py).
    """
    cached = await cache_get("copernicus_bgc", lat, lon)
    if cached is not None:
        return cached
    try:
        loop = asyncio.get_running_loop()
        await asyncio.wait_for(loop.run_in_executor(network_executor, _ensure_login), timeout=10)
        import functools

        async with _open_semaphore:
            values = await asyncio.wait_for(
                loop.run_in_executor(
                    network_executor,
                    functools.partial(
                        _open_read_close,
                        dataset_id="cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m",
                        variables=["chl"],
                        lat=lat,
                        lon=lon,
                        half_deg=0.3,
                        min_depth=0.49,
                        max_depth=0.6,
                        fields={"chlorophyll_mg_m3": ("chl", 4)},
                    ),
                ),
                timeout=25,
            )
        result = {
            "source": "Copernicus Marine BGC",
            "status": "success",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            **values,
        }
        await cache_set("copernicus_bgc", lat, lon, result)
        return result
    except Exception as exc:  # pragma: no cover - network dependent
        print(f"[copernicus_adapter.get_bgc_subset] {type(exc).__name__}: {exc}")
        return {"source": "Copernicus Marine BGC", "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
