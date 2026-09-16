"""
Builds a coarse SST baseline for the Anomaly Detection Agent from the
already-downloaded 2023 feature table (see app/ml/build_features.py).

HONESTY NOTE, read before trusting this: this is ONE YEAR of data. A real
climatological "normal" needs a multi-year (ideally 10-30 year) baseline —
what this produces is each 1-degree cell's own within-2023 monthly
mean/std, i.e. "is this warmer/cooler than this same region usually was in
this same month, going only by 2023" — not a true climatological anomaly.
The Anomaly Agent labels its output accordingly. Extend to multi-year
Copernicus/ERA5 history (see DATA_ACQUISITION.md) to make this a real
climatology.

Run:
    python scripts/build_sst_climatology.py

Output: data/processed/sst_climatology.parquet (~small, grid x month table)
"""
from pathlib import Path

import h3
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_2023.parquet"
OUT_PATH = REPO_ROOT / "data" / "processed" / "sst_climatology.parquet"


def build():
    print(f"Loading {FEATURES_PATH} ...")
    df = pd.read_parquet(FEATURES_PATH, columns=["h3_cell", "month", "sst_c"])
    df = df.dropna(subset=["sst_c"])
    print(f"{len(df):,} rows with valid SST")

    print("Converting H3 cells to lat/lon, binning to 1-degree grid...")
    centroids = df["h3_cell"].drop_duplicates()
    centroid_map = {c: h3.h3_to_geo(c) for c in centroids}
    df["lat"] = df["h3_cell"].map(lambda c: centroid_map[c][0])
    df["lon"] = df["h3_cell"].map(lambda c: centroid_map[c][1])
    df["grid_lat"] = df["lat"].round(0).astype(int)
    df["grid_lon"] = df["lon"].round(0).astype(int)

    print("Aggregating mean/std per (grid_lat, grid_lon, month)...")
    clim = (
        df.groupby(["grid_lat", "grid_lon", "month"])["sst_c"]
        .agg(mean_sst="mean", std_sst="std", n_samples="count")
        .reset_index()
    )
    # A std computed from very few samples is unreliable — drop those cells
    # rather than let them produce a falsely confident anomaly flag.
    clim = clim[clim["n_samples"] >= 10]
    clim["std_sst"] = clim["std_sst"].fillna(0.3)  # small nonzero floor, avoid div-by-zero

    clim.to_parquet(OUT_PATH, index=False)
    print(f"Wrote {len(clim):,} grid-cell/month baselines to {OUT_PATH}")


if __name__ == "__main__":
    build()
