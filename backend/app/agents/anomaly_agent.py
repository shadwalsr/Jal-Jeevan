"""
Anomaly Detection Agent (PRD Section 8). Deterministic z-score comparison —
no LLM, no ML model: this is arithmetic against a precomputed baseline
(scripts/build_sst_climatology.py), not a learned anomaly detector.

HONESTY LIMIT, carried through to every response this agent produces: the
baseline is built from a single year (2023) of data, not a true multi-year
climatology. Every result is labeled accordingly — never presented as "N
standard deviations from the 30-year normal" because that dataset doesn't
exist here yet. See scripts/build_sst_climatology.py's docstring.
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
CLIMATOLOGY_PATH = REPO_ROOT / "data" / "processed" / "sst_climatology.parquet"

ANOMALY_Z_THRESHOLD = 2.0

_climatology: pd.DataFrame | None = None
_load_failed = False


def _load() -> pd.DataFrame | None:
    global _climatology, _load_failed
    if _climatology is not None or _load_failed:
        return _climatology
    if not CLIMATOLOGY_PATH.exists():
        _load_failed = True
        return None
    try:
        _climatology = pd.read_parquet(CLIMATOLOGY_PATH)
        return _climatology
    except Exception:
        _load_failed = True
        return None


def detect_sst_anomaly(lat: float, lon: float, month: int, sst_c: float | None) -> dict:
    if sst_c is None:
        return {"status": "unavailable", "reason": "no current SST reading to compare"}

    clim = _load()
    if clim is None:
        return {"status": "unavailable", "reason": "SST baseline not built — run scripts/build_sst_climatology.py"}

    grid_lat, grid_lon = round(lat), round(lon)
    row = clim[(clim["grid_lat"] == grid_lat) & (clim["grid_lon"] == grid_lon) & (clim["month"] == month)]
    if row.empty:
        return {"status": "unavailable", "reason": f"no baseline for grid cell ({grid_lat}, {grid_lon}), month {month}"}

    mean_sst = float(row["mean_sst"].iloc[0])
    std_sst = float(row["std_sst"].iloc[0])
    n_samples = int(row["n_samples"].iloc[0])
    z_score = (sst_c - mean_sst) / std_sst if std_sst > 0 else 0.0

    return {
        "status": "success",
        "is_anomaly": abs(z_score) >= ANOMALY_Z_THRESHOLD,
        "current_sst_c": sst_c,
        "baseline_mean_c": round(mean_sst, 2),
        "baseline_std_c": round(std_sst, 2),
        "z_score": round(z_score, 2),
        "baseline_note": (
            f"Baseline from {n_samples} samples within 2023 only — a single-year regional average, "
            "not a true multi-year climatological normal. Treat as 'unusual for this dataset', not "
            "'unusual for this location historically'."
        ),
    }
