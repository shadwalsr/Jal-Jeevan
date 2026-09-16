"""
JalJeev — feature engineering: NetCDF (Copernicus physics/BGC) -> H3-indexed
daily feature table (Parquet). This is the bridge between raw downloaded
data (data/raw/) and the ML training pipeline (train_fishing_suitability.py).

Run:
    python -m app.ml.build_features

Output: data/processed/features_2023.parquet
One row per (h3_cell, date) with the feature columns listed in
PRD Section 11.1's feature table (the subset derivable from data we
currently have access to — SST, currents, salinity, chlorophyll, nutrients,
MLD, sea level anomaly; wave height/tide/D20/bathymetry join in once those
sources are wired up).

NOTE ON LABELS: this script produces FEATURES only. It deliberately does not
invent fishing-suitability labels — see train_fishing_suitability.py for how
the (currently missing, MOSDAC-gated) label problem is handled.
"""
import warnings
from pathlib import Path

import h3
import numpy as np
import pandas as pd
import xarray as xr

warnings.filterwarnings("ignore")

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW = REPO_ROOT / "data" / "raw" / "copernicus"
PROCESSED = REPO_ROOT / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)

H3_RESOLUTION = 7  # ~5km edge, matches PRD Marine Digital Twin grid


def _latlon_to_h3_lookup(lats: np.ndarray, lons: np.ndarray, resolution: int) -> pd.DataFrame:
    """
    Precompute h3_cell for each unique (lat, lon) grid point ONCE — the
    naive approach (recomputing per timestep) is O(grid_size * n_days),
    e.g. ~46M calls for a 301x421x365 cube; this reduces it to O(grid_size)
    (~127k calls) and merges the result onto the full table via a join
    instead of a per-row Python loop.
    """
    lat_grid, lon_grid = np.meshgrid(lats, lons, indexing="ij")
    flat_lat = lat_grid.ravel()
    flat_lon = lon_grid.ravel()
    h3_cells = [h3.geo_to_h3(float(la), float(lo), resolution) for la, lo in zip(flat_lat, flat_lon)]
    return pd.DataFrame({"latitude": flat_lat, "longitude": flat_lon, "h3_cell": h3_cells})


def _to_h3_daily(ds: xr.Dataset, var_names: list[str], resolution: int = H3_RESOLUTION) -> pd.DataFrame:
    """
    Collapse a lat/lon/time NetCDF into (h3_cell, date) rows by averaging
    all grid points that fall inside each hex — a coarse but simple and
    correct spatial join (good enough for res-7 hexes at 0.083-0.25 deg
    native resolution; revisit with area-weighted regridding if precision
    becomes a bottleneck).
    """
    lookup = _latlon_to_h3_lookup(ds["latitude"].values, ds["longitude"].values, resolution)

    df = ds[var_names].to_dataframe().reset_index()
    df = df.dropna(subset=var_names, how="all")
    df = df.merge(lookup, on=["latitude", "longitude"], how="left")
    df["date"] = pd.to_datetime(df["time"]).dt.date
    agg = df.groupby(["h3_cell", "date"])[var_names].mean().reset_index()
    return agg


def build():
    physics_3d = xr.open_dataset(RAW / "physics_3d_2023.nc")
    physics_surface = xr.open_dataset(RAW / "physics_surface_2023.nc")
    bgc = xr.open_dataset(RAW / "bgc_2023.nc")

    print("Indexing physics (SST, salinity, currents) to H3...")
    physics_df = _to_h3_daily(physics_3d, ["thetao", "so", "uo", "vo"])
    physics_df = physics_df.rename(columns={"thetao": "sst_c", "so": "salinity_psu"})
    physics_df["current_speed_ms"] = np.sqrt(physics_df["uo"] ** 2 + physics_df["vo"] ** 2)

    print("Indexing surface (sea level anomaly, mixed layer depth) to H3...")
    surface_df = _to_h3_daily(physics_surface, ["zos", "mlotst"])
    surface_df = surface_df.rename(columns={"zos": "sea_level_anomaly_m", "mlotst": "mixed_layer_depth_m"})

    print("Indexing BGC (chlorophyll, NPP, nitrate, oxygen) to H3...")
    bgc_df = _to_h3_daily(bgc, ["chl", "nppv", "no3", "o2"])
    bgc_df = bgc_df.rename(columns={"chl": "chlorophyll_mg_m3"})

    print("Joining feature tables...")
    features = physics_df.merge(surface_df, on=["h3_cell", "date"], how="outer")
    features = features.merge(bgc_df, on=["h3_cell", "date"], how="outer")

    features["month"] = pd.to_datetime(features["date"]).dt.month
    features["season"] = features["month"].map(_season)

    out_path = PROCESSED / "features_2023.parquet"
    features.to_parquet(out_path, index=False)
    print(f"Wrote {len(features):,} rows to {out_path}")
    return features


def _season(month: int) -> str:
    # Indian monsoon seasons, per PRD feature table ("Season 1-4")
    if month in (6, 7, 8, 9):
        return "sw_monsoon"
    if month in (10, 11):
        return "ne_monsoon_onset"
    if month in (12, 1, 2):
        return "ne_monsoon"
    return "pre_monsoon"


if __name__ == "__main__":
    build()
