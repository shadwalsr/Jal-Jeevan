"""
Tide predictions via pyTMD + the EOT20 global ocean tide model (DGFI-TUM,
freely downloadable from SEANOE, DOI 10.17882/79489 — no login wall, unlike
FES2014/TPXO which need a registration step). Harmonic-constituent based:
this predicts astronomical tide (the moon/sun-driven signal), not storm
surge, which is a separate, unmodeled hazard (see readiness audit).

Model data lives at data/raw/tides/EOT20/ — see DATA_ACQUISITION.md for how
it was fetched.

WHY THIS CACHES A SERIES, NOT A NUMBER (27 Aug 2026 rewrite)
------------------------------------------------------------
Measured: a cold EOT20 prediction takes ~61s (17 global NetCDF constituent
files, re-read from disk on every call — and previously re-read once PER
nudge offset, so a coastal point needing the search paid it twice).

The old design cached the single "tide height right now" value. That forces
a short TTL — a height computed 40 minutes ago is not the height now — so
the 61s cost recurred constantly, and because ocean_agent capped the call
at 20s, the computation was always cancelled before `cache_set` ran. Net
result measured live: every single request paid 20s, tide was ALWAYS
reported missing, and the cache was never populated. Worst of both.

The fix is to cache what is actually time-invariant. Astronomical tide is
deterministic: a 28-hour predicted series computed at 09:00 is still
exactly correct when read at 15:00 — nothing about it goes stale, because
it was never a measurement of "now" in the first place. So:

  * compute one 28h series (now-2h .. now+26h) per point,
  * evaluate every nudge offset in ONE pyTMD call instead of one call each,
  * cache the SERIES for 12h (always well inside the window it covers),
  * interpolate "now" out of it per request — microseconds, and correct.

And because even ~30s is far too long to sit on a request, a cold point
does not block: it schedules the computation in the background and reports
`status: "computing"` immediately. The next request for that point gets a
real answer. Nothing is fabricated, nothing is stale, and no user ever
waits on EOT20.
"""
import asyncio
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.core.cache import cache_get, cache_set
from app.tools._executor import netcdf_lock, network_executor

TIDE_MODEL_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "tides"

# The cached series spans now-2h .. now+26h; the cache TTL is 12h, so a
# cached series is always read well inside the window it actually covers
# (worst case: read at +12h with 14h of series still ahead).
SERIES_BEFORE_H = 2
SERIES_AFTER_H = 26
SERIES_STEP_MIN = 10

# EOT20's native grid is ~0.125 deg — a genuinely offshore point can still
# land on a masked/near-shore cell at that resolution and come back NaN.
# Standard practical fix: nudge outward in a small ring of offsets and use
# the first cell with real data, rather than silently reporting nothing for
# a point that has a real tide, just not resolvable exactly at that pixel.
_NUDGE_OFFSETS_DEG = [
    (0, 0),
    (0.15, 0), (-0.15, 0), (0, 0.15), (0, -0.15),
    (0.3, 0), (-0.3, 0), (0, 0.3), (0, -0.3),
]

# Points whose series is being computed right now. Without this, N concurrent
# requests for the same cold point would each schedule their own ~30s
# background job and all 9 offsets x N would pile into network_executor's
# 16 worker slots — the exact pool-starvation failure _executor.py warns
# about. One computation per point at a time.
_in_flight: set[str] = set()
_in_flight_lock = asyncio.Lock()


def _point_key(lat: float, lon: float) -> str:
    return f"{round(lat, 2)},{round(lon, 2)}"


def _compute_series_sync(lat: float, lon: float) -> dict:
    """
    One pyTMD call covering every nudge offset at every sample time.

    The 17-file constituent read dominates the cost and happens once per
    call regardless of how many points are passed, so evaluating all 9
    offsets together costs roughly what evaluating one used to — that alone
    removes the doubled cost a coastal point used to pay.
    """
    import pyTMD.compute as compute

    now = datetime.now(timezone.utc)
    minutes = np.arange(-SERIES_BEFORE_H * 60, SERIES_AFTER_H * 60 + SERIES_STEP_MIN, SERIES_STEP_MIN)
    n_times = len(minutes)
    t0 = now.timestamp() + float(minutes[0]) * 60
    times = now.timestamp() + minutes.astype("float64") * 60

    # type="drift" wants x, y and time as equal-length parallel arrays, so
    # build the full (offset x time) cross product and reshape the result.
    n_offsets = len(_NUDGE_OFFSETS_DEG)
    xs = np.repeat([lon + dlon for _, dlon in _NUDGE_OFFSETS_DEG], n_times)
    ys = np.repeat([lat + dlat for dlat, _ in _NUDGE_OFFSETS_DEG], n_times)
    ts = np.tile(times, n_offsets)

    # netcdf_lock: pyTMD reads the 17 EOT20 constituent files through
    # netCDF4, whose HDF5 backend is not thread-safe, and this runs in the
    # same pool as the Copernicus reader — see app/tools/_executor.py.
    with netcdf_lock:
        raw = compute.tide_elevations(
            xs,
            ys,
            ts,
            directory=TIDE_MODEL_DIR,
            model="EOT20",
            epoch=(1970, 1, 1, 0, 0, 0),
            type="drift",
            method="linear",
        )
    grid = np.asarray(raw).astype(float).reshape(n_offsets, n_times)

    for i, (dlat, dlon) in enumerate(_NUDGE_OFFSETS_DEG):
        series = grid[i]
        # Require the whole series to be real, not just some samples — a
        # partially-masked cell would give a series with holes exactly where
        # a later request might land.
        if not np.isnan(series).any():
            return {
                "source": "EOT20 (pyTMD)",
                "status": "success",
                "computed_at": datetime.now(timezone.utc).isoformat(),
                "t0_epoch_s": t0,
                "step_s": SERIES_STEP_MIN * 60,
                "heights_m": [round(float(v), 4) for v in series],
                "grid_cell_used": {"lat": round(lat + dlat, 3), "lon": round(lon + dlon, 3)},
            }

    raise ValueError(f"No valid EOT20 grid cell found near ({lat}, {lon}) within search radius")


def _read_now(series: dict) -> dict | None:
    """Interpolate the current height and trend out of a cached series."""
    heights = np.asarray(series["heights_m"], dtype=float)
    t0 = float(series["t0_epoch_s"])
    step = float(series["step_s"])
    now = datetime.now(timezone.utc).timestamp()

    idx = (now - t0) / step
    # Outside the window the series covers — treat as a miss and recompute
    # rather than extrapolating a tide we did not predict.
    if idx < 1 or idx > len(heights) - 2:
        return None

    lo = int(np.floor(idx))
    frac = idx - lo
    current = float(heights[lo] + (heights[lo + 1] - heights[lo]) * frac)

    # Trend across +/- one step (20 min) around now, same basis as before.
    trend = float(heights[min(lo + 1, len(heights) - 1)] - heights[max(lo - 1, 0)])
    if abs(trend) < 0.01:
        state = "high" if current > float(np.nanmean(heights)) else "low"
    else:
        state = "rising" if trend > 0 else "falling"

    return {
        "source": "EOT20 (pyTMD)",
        "status": "success",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "tide_height_m": round(current, 3),
        "tide_state": state,
        "grid_cell_used": series.get("grid_cell_used"),
        "prediction_computed_at": series.get("computed_at"),
    }


async def _compute_and_cache(lat: float, lon: float) -> dict | None:
    key = _point_key(lat, lon)
    try:
        loop = asyncio.get_running_loop()
        series = await asyncio.wait_for(
            loop.run_in_executor(network_executor, _compute_series_sync, lat, lon), timeout=180
        )
        # asyncio.shield: this task is deliberately independent of whatever
        # request triggered it, but shield the write anyway so a cancelled
        # loop shutdown cannot discard ~30s of completed work — losing the
        # write is what made the old implementation never populate its cache.
        await asyncio.shield(cache_set("tide", lat, lon, series))
        return series
    except Exception as exc:
        print(f"[tide_adapter] background series computation failed: {type(exc).__name__}: {exc}")
        return None
    finally:
        async with _in_flight_lock:
            _in_flight.discard(key)


async def get_tide(lat: float, lon: float) -> dict:
    """
    Never blocks. Returns a real prediction when one is cached for this
    point, otherwise reports honestly that it is being computed and returns
    immediately — a request must not wait ~30s for astronomy that will be
    identical whenever it is calculated.
    """
    if not TIDE_MODEL_DIR.exists() or not any(TIDE_MODEL_DIR.rglob("*.nc*")):
        return {
            "source": "EOT20 (pyTMD)",
            "status": "unavailable",
            "reason": "EOT20 model files not found under data/raw/tides — see DATA_ACQUISITION.md",
        }

    cached = await cache_get("tide", lat, lon)
    if cached is not None and "heights_m" in cached:
        reading = _read_now(cached)
        if reading is not None:
            return reading
        # Series exists but "now" has walked off the end of it — fall through
        # and recompute rather than extrapolating.

    key = _point_key(lat, lon)
    async with _in_flight_lock:
        already_running = key in _in_flight
        if not already_running:
            _in_flight.add(key)

    if not already_running:
        asyncio.create_task(_compute_and_cache(lat, lon))

    return {
        "source": "EOT20 (pyTMD)",
        "status": "computing",
        "reason": (
            "EOT20 harmonic prediction for this point is being computed in the background "
            "(~30s, cached for 12h afterwards). Tide is not included in this response."
        ),
    }


async def prewarm_tide(lat: float, lon: float, timeout_s: int = 200) -> dict:
    """
    Blocking variant for scripts/prewarm_demo.py and background refresh jobs
    ONLY — never call this from a request path. Waits for the real
    computation so a demo starts with the cache already populated.
    """
    cached = await cache_get("tide", lat, lon)
    if cached is not None and "heights_m" in cached and _read_now(cached) is not None:
        return {"status": "success", "reason": "already cached"}
    series = await asyncio.wait_for(_compute_and_cache(lat, lon), timeout=timeout_s)
    return {"status": "success" if series else "failed"}
