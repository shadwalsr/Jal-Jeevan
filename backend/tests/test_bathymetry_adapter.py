"""
Tests for app/tools/bathymetry_adapter.py's region-tile cache.

Real bug (26 Aug 2026): the lazy `_load_regions()` cache used a plain
"if _datasets is not None: return; _datasets = {}" check-then-set with no
lock. That's safe when called once, but route_agent.py's candidate scan
calls get_depth_m for up to 16 points CONCURRENTLY (via asyncio.to_thread,
i.e. real OS threads) — multiple threads could all see the cache as
unloaded, each reassign it to a fresh {}, and stomp on each other's
in-progress population. A candidate whose lookup landed mid-race got back
"unavailable" instead of the real land/depth answer. "unavailable" doesn't
hard-veto, so this could silently let an on-land candidate through as safe
water — confirmed live: the same land point scored REJECTED when checked in
isolation but LOW (not rejected) inside the 16-way concurrent scan.

These tests don't depend on real GEBCO tiles being present (data/raw/ isn't
guaranteed to exist in every environment) — they inject a small synthetic
region so the concurrency behavior itself is what's under test.
"""
import concurrent.futures
import threading

import numpy as np
import pytest
import xarray as xr

from app.tools import bathymetry_adapter as ba


def _write_synthetic_region(path, lat_range, lon_range, elevation_value):
    """A 4x4 grid, uniform elevation — enough for _find_region's bbox check
    and get_depth_m's nearest-neighbor .sel() to resolve deterministically."""
    lats = np.linspace(lat_range[0], lat_range[1], 4)
    lons = np.linspace(lon_range[0], lon_range[1], 4)
    ds = xr.Dataset(
        {"elevation": (("lat", "lon"), np.full((4, 4), elevation_value, dtype="float64"))},
        coords={"lat": lats, "lon": lons},
    )
    ds.to_netcdf(path)


@pytest.fixture
def synthetic_region_dir(tmp_path, monkeypatch):
    region_dir = tmp_path / "regions"
    region_dir.mkdir()
    _write_synthetic_region(region_dir / "test_region.nc", (10.0, 11.0), (80.0, 81.0), elevation_value=-25.0)
    monkeypatch.setattr(ba, "REGIONS_DIR", region_dir)
    monkeypatch.setattr(ba, "_datasets", None)
    yield region_dir
    monkeypatch.setattr(ba, "_datasets", None)


def test_get_depth_m_reads_synthetic_region(synthetic_region_dir):
    result = ba.get_depth_m(10.5, 80.5)
    assert result["status"] == "success"
    assert result["depth_m"] == pytest.approx(25.0)
    assert result["is_land"] is False


def test_concurrent_load_does_not_lose_data(synthetic_region_dir):
    """The actual regression: hammer _load_regions() from many real OS
    threads at once (matching route_agent.py's asyncio.to_thread usage) and
    verify every thread converges on the same, fully-populated cache rather
    than a partial/empty one from a losing race."""
    barrier = threading.Barrier(32)

    def _load():
        barrier.wait()  # maximize the chance every thread hits the race window together
        return ba._load_regions()

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(lambda _: _load(), range(32)))

    # Every thread must see the region — none should have raced past a
    # concurrent reset and gotten an empty dict.
    assert all("test_region" in d for d in results), "some threads saw an incomplete cache — the race is back"
    # And they should all have converged on the SAME dict object — proof
    # only one thread actually performed the load.
    assert all(d is results[0] for d in results)


def test_concurrent_lookups_never_return_unavailable_for_a_loaded_region(synthetic_region_dir):
    """End-to-end version of the same race: get_depth_m (what route_agent.py
    actually calls) must never spuriously report "unavailable" for a point
    inside a region that IS loaded, no matter how many concurrent callers
    are racing to trigger the initial load."""
    barrier = threading.Barrier(32)

    def _lookup():
        barrier.wait()
        return ba.get_depth_m(10.5, 80.5)

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(lambda _: _lookup(), range(32)))

    assert all(r["status"] == "success" for r in results), (
        "a concurrent lookup returned 'unavailable' for a point inside a loaded region — "
        "the cache race is back, and this is exactly what let an on-land route candidate "
        "through as unvetoed 'safe' water"
    )
