"""
Fetch GEBCO_2026 bathymetry as small, verified regional tiles.

app/tools/bathymetry_adapter.py has always pointed at "the fetch script in
scripts/" for adding new regions — this is that script. It did not exist
before 27 Aug 2026, which is why the four original tiles could not be
extended without redoing the work by hand.

WHY SMALL TILES (CLAUDE.md gotcha #7)
------------------------------------
A single large OPeNDAP request (25x35 degrees, ~101MB) was observed to
silently truncate mid-transfer and zero-fill the remainder — no error
raised, just wrong data, and every downstream depth lookup then returned
"0m / land" instead of real bathymetry. So: one ~1x1 degree tile per
request, and every tile is checked for a plausible nonzero fraction before
it is allowed to touch data/raw/. A tile that fails the check is reported
and NOT saved, rather than saved with a warning nobody reads.

Source: GEBCO_2026 grid, 15 arc-second global terrain model, via the
CEDA/BODC THREDDS OPeNDAP server. Public domain, no credentials needed.
https://data.ceda.ac.uk/bodc/gebco/global/gebco_2026

Usage:
    cd D:/Jaljeev
    backend/.venv/Scripts/python.exe scripts/fetch_gebco_regions.py
    backend/.venv/Scripts/python.exe scripts/fetch_gebco_regions.py --only paradip
    backend/.venv/Scripts/python.exe scripts/fetch_gebco_regions.py --force
    backend/.venv/Scripts/python.exe scripts/fetch_gebco_regions.py \
        --add konark 19.6 20.6 85.8 86.8
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import xarray as xr

GEBCO_OPENDAP = (
    "https://dap.ceda.ac.uk/thredds/dodsC/bodc/gebco/global/gebco_2026"
    "/ice_surface_elevation/netcdf/GEBCO_2026.nc"
)

REGIONS_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "gebco" / "regions"

# A tile that came back mostly zeros is a truncated transfer, not a real
# seafloor: exact 0 m elevation is vanishingly rare over a 1-degree box.
MIN_NONZERO_FRACTION = 0.85

# Elevation sanity bounds from GEBCO's own global metadata (-10930 .. 8627).
PLAUSIBLE_MIN_M = -11500
PLAUSIBLE_MAX_M = 9000

# name -> (lat_min, lat_max, lon_min, lon_max)
#
# The four originals (chennai, kochi, puri, vizag) are listed so this script
# is a complete description of what should exist on disk; they are skipped
# when already present.
#
# The odisha_* / paradip / gopalpur tiles were added 27 Aug 2026: the single
# puri tile covers only 19.30-20.30 N, 85.30-86.30 E, and Bhubaneswar sits
# ~60 km inland at 20.30 N — so any search from there either never reached
# open water or ran straight off the edge of the loaded data and got back
# "no GEBCO tile covers this point". These extend coverage along the whole
# Odisha coast and out past the shelf break.
REGIONS: dict[str, tuple[float, float, float, float]] = {
    "kochi": (9.30, 10.30, 75.30, 76.30),
    "chennai": (12.60, 13.60, 79.80, 80.80),
    "vizag": (17.20, 18.20, 82.90, 83.90),
    "puri": (19.30, 20.30, 85.30, 86.30),
    # --- Odisha extension (27 Aug 2026) ---
    "paradip": (19.80, 20.80, 86.30, 87.30),
    "puri_offshore": (18.80, 19.80, 85.30, 86.30),
    "odisha_se_offshore": (19.00, 20.00, 86.30, 87.30),
    "gopalpur": (18.80, 19.80, 84.40, 85.40),
}


def fetch_region(ds: xr.Dataset, name: str, bbox: tuple[float, float, float, float]) -> bool:
    lat_min, lat_max, lon_min, lon_max = bbox
    out_path = REGIONS_DIR / f"{name}.nc"

    print(f"\n{name}: lat {lat_min}..{lat_max}, lon {lon_min}..{lon_max}")
    t0 = time.perf_counter()
    try:
        tile = ds.sel(lat=slice(lat_min, lat_max), lon=slice(lon_min, lon_max)).load()
    except Exception as exc:
        print(f"  FAILED to fetch: {type(exc).__name__}: {exc}")
        return False
    elapsed = time.perf_counter() - t0

    values = tile["elevation"].values
    nonzero = float((values != 0).mean())
    vmin, vmax = float(values.min()), float(values.max())
    print(f"  fetched {values.shape} in {elapsed:.1f}s")
    print(f"  nonzero fraction {nonzero:.1%}, elevation {vmin:.0f}..{vmax:.0f} m")

    # Gate 1: truncated/zero-filled transfer.
    if nonzero < MIN_NONZERO_FRACTION:
        print(
            f"  REJECTED: only {nonzero:.1%} nonzero (< {MIN_NONZERO_FRACTION:.0%}). "
            "This is what a silently truncated OPeNDAP transfer looks like. Not saved."
        )
        return False

    # Gate 2: values outside anything the real seafloor does.
    if vmin < PLAUSIBLE_MIN_M or vmax > PLAUSIBLE_MAX_M:
        print(f"  REJECTED: elevation {vmin:.0f}..{vmax:.0f} m is outside plausible bounds. Not saved.")
        return False

    # Gate 3: a tile of one constant value is not terrain.
    if np.unique(values).size < 10:
        print(f"  REJECTED: only {np.unique(values).size} distinct elevation values. Not saved.")
        return False

    REGIONS_DIR.mkdir(parents=True, exist_ok=True)
    encoding = {"elevation": {"zlib": True, "complevel": 4}}
    tile.to_netcdf(out_path, encoding=encoding)
    size_kb = out_path.stat().st_size / 1024
    depth_pct = float((values < 0).mean())
    print(f"  SAVED {out_path.name} ({size_kb:.0f} KB), {depth_pct:.0%} of cells are below sea level")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="fetch just this region name")
    parser.add_argument("--force", action="store_true", help="re-fetch regions that already exist")
    parser.add_argument(
        "--add",
        nargs=5,
        metavar=("NAME", "LAT_MIN", "LAT_MAX", "LON_MIN", "LON_MAX"),
        help="fetch an ad-hoc region not in the REGIONS table",
    )
    args = parser.parse_args()

    targets = dict(REGIONS)
    if args.add:
        name, *coords = args.add
        targets = {name: tuple(float(c) for c in coords)}
    elif args.only:
        if args.only not in targets:
            print(f"Unknown region '{args.only}'. Known: {', '.join(sorted(targets))}")
            return 2
        targets = {args.only: targets[args.only]}

    pending = {
        name: bbox
        for name, bbox in targets.items()
        if args.force or not (REGIONS_DIR / f"{name}.nc").exists()
    }
    skipped = [n for n in targets if n not in pending]
    if skipped:
        print(f"Already present, skipping: {', '.join(sorted(skipped))}")
    if not pending:
        print("Nothing to fetch.")
        return 0

    print(f"Opening GEBCO_2026 over OPeNDAP ({len(pending)} tile(s) to fetch)...")
    try:
        ds = xr.open_dataset(GEBCO_OPENDAP)
    except Exception as exc:
        print(f"Could not open the GEBCO OPeNDAP endpoint: {type(exc).__name__}: {exc}")
        return 1

    ok, failed = [], []
    for name, bbox in pending.items():
        (ok if fetch_region(ds, name, bbox) else failed).append(name)

    print(f"\n{'=' * 60}")
    print(f"Saved:  {', '.join(ok) if ok else '(none)'}")
    if failed:
        print(f"FAILED: {', '.join(failed)} — re-run to retry; nothing bad was written.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
