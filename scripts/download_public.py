"""
JalJeev — bulk download of publicly-available marine datasets.
Adapted from the team's acquisition plan; writes into this repo's data/raw/
instead of a separate project folder. Safe to re-run — skips files that
already exist (see `fetch()`).

Usage:
    python scripts/download_public.py

Expect this to take a while and use tens of GB of disk (see README /
DATA_ACQUISITION.md for a size estimate per source). Run from the repo root
or anywhere — paths are relative to the repo root via ROOT below.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
import pandas as pd
import xarray as xr

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT = REPO_ROOT / "data" / "raw"
ROOT.mkdir(parents=True, exist_ok=True)


def fetch(url, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if out.exists() and out.stat().st_size > 1000:
        print("SKIP:", out)
        return

    part = Path(str(out) + ".part")
    start = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={start}-"} if start else {}

    print("GET:", out)
    with requests.get(url, stream=True, timeout=300, headers=headers) as r:
        r.raise_for_status()
        mode = "ab" if start and r.status_code == 206 else "wb"
        with open(part, mode) as f:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)

    part.replace(out)


jobs = [
    # Cyclones — IBTrACS North Indian Ocean basin
    (
        "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.NI.list.v04r01.csv",
        ROOT / "ibtracs/ibtracs_NI.csv",
    ),
    # GFW vessel identity
    (
        "https://zenodo.org/records/14982712/files/fishing-vessels-v3.csv?download=1",
        ROOT / "gfw/fishing-vessels-v3.csv",
    ),
    # Daily MMSI sample
    (
        "https://zenodo.org/records/14982712/files/mmsi-daily-csvs-10-v3-2023.zip?download=1",
        ROOT / "gfw/mmsi-daily-csvs-10-v3-2023.zip",
    ),
    # WOA23 annual climatologies
    (
        "https://www.ncei.noaa.gov/data/oceans/woa/WOA23/DATA/temperature/netcdf/decav/1.00/woa23_decav_t00_01.nc",
        ROOT / "woa23/temperature.nc",
    ),
    (
        "https://www.ncei.noaa.gov/data/oceans/woa/WOA23/DATA/salinity/netcdf/decav/1.00/woa23_decav_s00_01.nc",
        ROOT / "woa23/salinity.nc",
    ),
    (
        "https://www.ncei.noaa.gov/data/oceans/woa/WOA23/DATA/oxygen/netcdf/all/1.00/woa23_all_o00_01.nc",
        ROOT / "woa23/oxygen.nc",
    ),
    (
        "https://www.ncei.noaa.gov/data/oceans/woa/WOA23/DATA/nitrate/netcdf/all/1.00/woa23_all_n00_01.nc",
        ROOT / "woa23/nitrate.nc",
    ),
    (
        "https://www.ncei.noaa.gov/data/oceans/woa/WOA23/DATA/phosphate/netcdf/all/1.00/woa23_all_p00_01.nc",
        ROOT / "woa23/phosphate.nc",
    ),
    (
        "https://www.ncei.noaa.gov/data/oceans/woa/WOA23/DATA/silicate/netcdf/all/1.00/woa23_all_i00_01.nc",
        ROOT / "woa23/silicate.nc",
    ),
]

import sys

FULL_GFW_HISTORY = "--full" in sys.argv
YEAR_START, YEAR_END = (2012, 2025) if FULL_GFW_HISTORY else (2023, 2024)

# GFW monthly effort. Default: 2023 only. Pass --full for the entire
# 2012-2024 archive (~10-20 GB extra).
for year in range(YEAR_START, YEAR_END):
    name = f"fleet-monthly-csvs-10-v3-{year}.zip"
    jobs.append((f"https://zenodo.org/records/14982712/files/{name}?download=1", ROOT / "gfw" / name))

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda x: fetch(*x), jobs))

    # OISST Indian Ocean subset, one file per year.
    # Default: 2023 only, matching the rest of this run. Pass --full for
    # the full 2010-2023 regional history (~1-2 GB extra).
    oisst_start, oisst_end = (2010, 2024) if FULL_GFW_HISTORY else (2023, 2024)
    try:
        source = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/ncdcOisst21Agg_LonPM180"
        ds = xr.open_dataset(source, engine="netcdf4")
        variables = [v for v in ["sst", "anom"] if v in ds]

        for year in range(oisst_start, oisst_end):
            out = ROOT / f"oisst/oisst_india_{year}.nc"
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists():
                continue
            print("OISST:", year)
            subset = ds[variables].sel(
                time=slice(f"{year}-01-01", f"{year}-12-31"),
                latitude=slice(0, 25),
                longitude=slice(65, 100),
            )
            subset.to_netcdf(out, encoding={v: {"zlib": True, "complevel": 4} for v in variables})
        ds.close()
    except Exception as e:
        print("OISST failed; rerun later:", e)

    # Inventory
    rows = []
    for p in ROOT.rglob("*"):
        if p.is_file() and not p.name.endswith(".part"):
            rows.append({"path": str(p), "size_mb": round(p.stat().st_size / 1024**2, 2)})
    pd.DataFrame(rows).to_csv(REPO_ROOT / "data" / "manifest.csv", index=False)
    print("Finished. Open data/manifest.csv")
