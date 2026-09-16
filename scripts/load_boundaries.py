"""
JalJeev — load geospatial boundary data (EEZ, territorial seas, MPAs) into
PostGIS. Run this after manually downloading the source files (see
DATA_ACQUISITION.md) — these sources require browser click-through /
licence acceptance and can't be scripted.

Expected input files:
    data/raw/boundaries/eez/*.shp (or .gpkg)          — Marine Regions World EEZ v12
    data/raw/boundaries/territorial_seas/*.shp (or .gpkg) — World 12NM Zone v4
    data/raw/boundaries/protected_planet/*.shp        — WDPA marine protected areas

Usage:
    python -m app.ml... no — this is a one-off script, run directly:
    python scripts/load_boundaries.py --eez data/raw/boundaries/eez/eez_v12.shp
    python scripts/load_boundaries.py --mpa data/raw/boundaries/protected_planet/WDPA.shp
"""
import argparse
from pathlib import Path

import geopandas as gpd
from sqlalchemy import create_engine

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_engine():
    import os

    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    # geopandas/PostGIS wants a sync (psycopg2) URL, not the app's asyncpg one
    db_url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    return create_engine(db_url)


# Indian Ocean operational bbox (with margin) — keeps tables small and load
# times reasonable instead of ingesting the whole planet.
BBOX = (60, -5, 100, 25)  # (minx, miny, maxx, maxy)


def load_eez(path: str, table: str = "eez_boundaries"):
    print(f"Reading {path} (bbox-filtered) ...")
    gdf = gpd.read_file(path, bbox=BBOX)
    gdf = gdf.to_crs(epsg=4326)
    # geopandas/PostGIS wants a single geometry type per column ideally;
    # rename to lowercase `geometry` is already the default column name.
    engine = get_engine()
    gdf.to_postgis(table, engine, if_exists="replace", index=False)
    print(f"Loaded {len(gdf)} EEZ features into `{table}`")


def load_mpa(path: str, table: str = "mpa_boundaries", layer: str | None = None):
    print(f"Reading {path} (bbox-filtered) ...")
    gdf = gpd.read_file(path, layer=layer, bbox=BBOX)
    gdf = gdf.to_crs(epsg=4326)
    # WDPA column names are upper/mixed-case; geo_agent.py's query expects
    # a lowercase `name` column — normalize it.
    name_col = next((c for c in ("NAME", "ORIG_NAME", "name") if c in gdf.columns), None)
    if name_col and name_col != "name":
        gdf = gdf.rename(columns={name_col: "name"})
    engine = get_engine()
    gdf.to_postgis(table, engine, if_exists="replace", index=False)
    print(f"Loaded {len(gdf)} MPA features into `{table}`")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--eez", help="Path to Marine Regions EEZ shapefile/GeoPackage")
    parser.add_argument("--mpa", help="Path to Protected Planet WDPA shapefile or .gdb")
    parser.add_argument("--mpa-layer", default="WDPA_poly_Aug2026", help="Layer name inside the .gdb (polygons)")
    args = parser.parse_args()

    if not args.eez and not args.mpa:
        raise SystemExit("Pass --eez and/or --mpa with a path to the downloaded file.")

    if args.eez:
        load_eez(args.eez)
    if args.mpa:
        load_mpa(args.mpa, layer=args.mpa_layer)
