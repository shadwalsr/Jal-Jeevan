"""
Bathymetry lookups — GEBCO_2026, small verified regional tiles (see
data/raw/gebco/regions/), fetched via OPeNDAP directly from CEDA/BODC's
THREDDS server.

IMPORTANT — why regional tiles, not one India-wide file: a single large
OPeNDAP request (25x35 degrees, ~101MB decompressed) was observed to
silently truncate mid-transfer and zero-fill everything past the cutoff —
no error raised, just wrong data (a real bug caught during testing on
26 Aug 2026, not a hypothetical). Small per-region tiles (~1x1 degree) with
an explicit nonzero-fraction sanity check before saving are what's actually
reliable. See scripts/ for the fetch script if more regions are needed —
run it with a fresh region bbox and the same >85% nonzero_frac gate.

Elevation is in meters, positive = above sea level. Depth (what callers
want) is the negation of elevation and clamped at 0 for land cells.
"""
import threading
from pathlib import Path

import xarray as xr

REGIONS_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "gebco" / "regions"

_datasets: dict[str, xr.Dataset] | None = None
# get_depth_m runs off the event loop via asyncio.to_thread (see
# geo_agent.py), and route_agent.py's candidate scan now calls it for up to
# 16 candidates CONCURRENTLY (26 Aug 2026 fix — see route_agent.py). That
# turned this lazy-load into a real race: the old code's plain
# `if _datasets is not None: return; _datasets = {}` is a classic
# check-then-set — multiple threads could all see None, each reassign
# _datasets to a fresh {} (discarding whatever an earlier thread had already
# populated), and a candidate whose lookup ran mid-race would see an empty/
# partial dict and get back "unavailable" instead of the real land/depth
# answer. "unavailable" doesn't hard-veto, so this could silently let a
# genuinely on-land candidate through as if it were open water — caught live
# via a query where the same land point scored REJECTED called in isolation
# but LOW inside the 16-way concurrent scan. Double-checked locking below
# fixes it: only one thread ever performs the actual load.
_load_lock = threading.Lock()


def _load_regions() -> dict[str, xr.Dataset]:
    global _datasets
    if _datasets is not None:
        return _datasets
    with _load_lock:
        if _datasets is not None:  # someone else finished loading while we waited
            return _datasets
        datasets: dict[str, xr.Dataset] = {}
        if REGIONS_DIR.exists():
            for path in REGIONS_DIR.glob("*.nc"):
                try:
                    # .load() pulls the whole tile into memory once, so every
                    # subsequent depth lookup is pure numpy indexing with no
                    # HDF5 access. That matters for two reasons: the candidate
                    # scan reads these from 16 threads at once, and HDF5 is not
                    # thread-safe (see app/tools/_executor.py::netcdf_lock).
                    # A tile is ~70 KB, so holding them all costs nothing.
                    datasets[path.stem] = xr.open_dataset(path).load()
                except Exception as exc:
                    print(f"[bathymetry_adapter] failed to load region tile {path.name}: {type(exc).__name__}: {exc}")
                    continue
        _datasets = datasets
        return _datasets


def _find_region(lat: float, lon: float) -> xr.Dataset | None:
    for ds in _load_regions().values():
        lat_min, lat_max = float(ds.lat.min()), float(ds.lat.max())
        lon_min, lon_max = float(ds.lon.min()), float(ds.lon.max())
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return ds
    return None


def get_depth_m(lat: float, lon: float) -> dict:
    """Returns depth in meters (positive = underwater) or status='unavailable'."""
    ds = _find_region(lat, lon)
    if ds is None:
        return {
            "status": "unavailable",
            "reason": "No GEBCO tile covers this point yet — only a few demo regions are loaded, see DATA_ACQUISITION.md",
        }
    try:
        elevation = float(ds.elevation.sel(lat=lat, lon=lon, method="nearest").values)
        depth = max(0.0, -elevation)
        return {"status": "success", "depth_m": round(depth, 1), "is_land": elevation > 0}
    except Exception as exc:  # pragma: no cover - out-of-bounds lookup etc.
        return {"status": "failed", "error": str(exc)}
