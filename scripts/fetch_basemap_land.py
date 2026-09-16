"""
Clip Natural Earth's 1:50m land polygons to the India/Bay of Bengal region and
write a small, verified GeoJSON the frontend bundles as a static asset.

WHY A LOCAL FILE INSTEAD OF A TILE SERVER
------------------------------------------
The map basemap was originally third-party raster tiles (OSM, then CARTO
Positron). Both work, but both are a live third-party dependency the app
takes on every load — CARTO's terms expect an account for production use,
and even OSM's free tile endpoint is best-effort, rate-limited, and outside
this project's control. Given the whole point of the visual design is a
flat two-colour chart (land / water), there is no reason to render raster
imagery through a tile pipeline at all — a small vector polygon layer,
downloaded once and committed, removes the dependency entirely. Offline
after the JS bundle loads once, same philosophy as the project's own
"graceful degradation over hanging" principle (CLAUDE.md) applied to the
map itself.

WHY CLIPPED, NOT THE WHOLE WORLD
---------------------------------
The source file (Natural Earth 1:50m land, public domain) is 1.6 MB
globally. This app never shows anywhere outside the Indian Ocean rim, so
shipping the whole world is pure waste. Clipped to a generous India/Bay of
Bengal/Arabian Sea bbox and simplified slightly, matching
scripts/fetch_gebco_regions.py's "small verified regional tiles, not one
big global file" pattern — same reasoning, same gate-before-save discipline.

Source: Natural Earth, 1:50m Cultural/Physical vector data. Public domain,
no attribution legally required (attribution given anyway, in the map's
attribution control, as good practice).

Usage:
    cd D:/Jaljeev
    backend/.venv/Scripts/python.exe scripts/fetch_basemap_land.py
"""
import json
import sys
from pathlib import Path

from shapely.geometry import box, shape, mapping
from shapely.ops import unary_union

RAW_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "basemap" / "ne_50m_land.geojson"
OUT_PATH = Path(__file__).resolve().parents[1] / "frontend" / "public" / "basemap" / "land.geojson"

# Generous India/Bay of Bengal/Arabian Sea bbox — wide enough that panning
# around any of the project's demo points (Visakhapatnam, Puri, Paradip,
# Kochi, Chennai) never runs off the edge of the loaded land layer.
# (min_lon, min_lat, max_lon, max_lat)
BBOX = (60.0, -2.0, 98.0, 28.0)

# Coarser than GEBCO's bathymetry tiles, deliberately: this is a background
# reference layer, not a navigational depth source — real precision lives in
# the boundaries/quick-check/state endpoints, not the basemap's coastline.
SIMPLIFY_TOLERANCE_DEG = 0.01

MIN_FEATURES = 5  # a truncated/corrupt download would have far fewer


def main() -> int:
    if not RAW_PATH.exists():
        print(f"Missing {RAW_PATH} — download ne_50m_land.geojson first.")
        return 1

    print(f"Reading {RAW_PATH} ...")
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    features = raw.get("features", [])
    print(f"  {len(features)} source features")

    clip_box = box(*BBOX)
    kept = []
    for feat in features:
        try:
            geom = shape(feat["geometry"])
        except Exception as exc:
            print(f"  skipping one feature: {type(exc).__name__}: {exc}")
            continue
        if not geom.intersects(clip_box):
            continue
        clipped = geom.intersection(clip_box)
        if clipped.is_empty:
            continue
        simplified = clipped.simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)
        if simplified.is_empty:
            continue
        kept.append(simplified)

    print(f"  {len(kept)} polygons intersect the bbox {BBOX}")

    # Sanity gates before anything touches the repo — same discipline as
    # fetch_gebco_regions.py: a truncated or malformed source must not be
    # allowed to silently become "the coastline" the app renders.
    if len(kept) < MIN_FEATURES:
        print(f"REJECTED: only {len(kept)} features survived clipping (< {MIN_FEATURES}). "
              "The source download may be truncated or corrupt. Not saved.")
        return 1

    merged = unary_union(kept)
    total_area = merged.area
    if total_area <= 0:
        print("REJECTED: clipped geometry has zero area. Not saved.")
        return 1

    geoms = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    out = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {}, "geometry": mapping(g)}
            for g in geoms
        ],
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"SAVED {OUT_PATH} ({size_kb:.0f} KB), {len(geoms)} polygon(s), bbox {BBOX}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
