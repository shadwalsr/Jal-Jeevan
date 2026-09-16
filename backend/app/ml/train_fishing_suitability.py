"""
JalJeev — Fishing Suitability Predictor training (PRD Section 11.1).

THE LABEL PROBLEM (read this before trusting any metric this script prints):

The real label is "did INCOIS issue a PFZ advisory for this H3 cell on this
date" — that comes from the INCOIS PFZ archive (2003-2025), which requires
MOSDAC/INCOIS access we don't have yet (pending approval, see README).

Without it, there is nothing genuine to predict. This script supports two
modes:

  --labels <path>   Real PFZ labels (h3_cell, date, pfz_label columns).
                     Use this once MOSDAC access lands. Metrics from this
                     mode are real and reportable.

  --proxy-labels     Generates a RULE-BASED proxy target (favorable SST band
                     + above-median chlorophyll) purely so the training/
                     evaluation MECHANICS can be exercised end-to-end before
                     real labels exist. The model trained this way is
                     learning to reconstruct our own SST/chlorophyll rule —
                     high AUC here proves NOTHING about real-world PFZ
                     prediction. Every output in this mode is stamped
                     "SYNTHETIC" and must never be quoted as a real metric
                     to judges or in the PRD's KPI table.

Run:
    python -m app.ml.train_fishing_suitability --proxy-labels
    python -m app.ml.train_fishing_suitability --labels data/processed/pfz_labels.parquet
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    average_precision_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
PROCESSED = REPO_ROOT / "data" / "processed"
MODELS_DIR = REPO_ROOT / "data" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLUMNS = [
    "sst_c",
    "salinity_psu",
    "current_speed_ms",
    "sea_level_anomaly_m",
    "mixed_layer_depth_m",
    "chlorophyll_mg_m3",
    "nppv",
    "no3",
    "o2",
    "month",
]

# PRD Section 11.1 hyperparameters
XGB_PARAMS = dict(
    n_estimators=500,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=5,
    reg_alpha=0.1,
    reg_lambda=1.0,
    eval_metric="auc",
)


def make_proxy_labels(features: pd.DataFrame) -> pd.Series:
    """
    RULE-BASED PROXY LABEL — for pipeline testing only, see module docstring.
    "Favorable" = SST 26-30C (typical productive tropical range) AND
    chlorophyll above the regional median (proxy for productivity front).
    """
    sst_ok = features["sst_c"].between(26, 30)
    chl_median = features["chlorophyll_mg_m3"].median()
    chl_ok = features["chlorophyll_mg_m3"] > chl_median
    return (sst_ok & chl_ok).astype(int)


def temporal_split(df: pd.DataFrame, date_col: str = "date"):
    """
    Single-year data (2023) can't reproduce the PRD's real multi-year split
    (train 2003-2022 / val 2023-24 / test 2025) — that needs the INCOIS PFZ
    archive across years. For now: first 9 months train, last 3 months test,
    so the mechanics (no leakage, held-out evaluation) are still correct.
    """
    dates = pd.to_datetime(df[date_col])
    cutoff = dates.quantile(0.75)
    train = df[dates <= cutoff]
    test = df[dates > cutoff]
    return train, test


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", default=str(PROCESSED / "features_2023.parquet"))
    parser.add_argument("--labels", default=None, help="Path to real PFZ labels parquet")
    parser.add_argument("--proxy-labels", action="store_true", help="Use synthetic proxy labels (pipeline test only)")
    args = parser.parse_args()

    if not args.labels and not args.proxy_labels:
        raise SystemExit(
            "No label source given. Real PFZ labels aren't available yet "
            "(MOSDAC access pending) — pass --proxy-labels to test the "
            "pipeline mechanics, or --labels <path> once real labels exist."
        )

    print(f"Loading features from {args.features} ...")
    features = pd.read_parquet(args.features)
    features = features.dropna(subset=FEATURE_COLUMNS)
    print(f"{len(features):,} complete-feature rows after dropping nulls")

    if args.proxy_labels:
        print("\n" + "=" * 70)
        print("WARNING: using SYNTHETIC proxy labels. Metrics below are a")
        print("pipeline sanity check ONLY — not a real PFZ prediction result.")
        print("Do not report these numbers as the model's real performance.")
        print("=" * 70 + "\n")
        features["label"] = make_proxy_labels(features)
        run_tag = "SYNTHETIC_PROXY"
    else:
        labels = pd.read_parquet(args.labels)
        features = features.merge(labels, on=["h3_cell", "date"], how="inner")
        features = features.rename(columns={"pfz_label": "label"})
        run_tag = "REAL"

    train, test = temporal_split(features)
    print(f"Train: {len(train):,} rows | Test: {len(test):,} rows")
    print(f"Positive rate — train: {train['label'].mean():.3f}, test: {test['label'].mean():.3f}")

    X_train, y_train = train[FEATURE_COLUMNS], train["label"]
    X_test, y_test = test[FEATURE_COLUMNS], test["label"]

    model = xgb.XGBClassifier(**XGB_PARAMS)
    model.fit(X_train, y_train)

    proba = model.predict_proba(X_test)[:, 1]
    pred = (proba >= 0.5).astype(int)

    auc = roc_auc_score(y_test, proba)
    ap = average_precision_score(y_test, proba)
    precision = precision_score(y_test, pred, zero_division=0)
    recall = recall_score(y_test, pred, zero_division=0)

    print(f"\n[{run_tag}] AUC-ROC: {auc:.4f} (target > 0.82)")
    print(f"[{run_tag}] Average Precision: {ap:.4f}")
    print(f"[{run_tag}] Precision@0.5: {precision:.4f} (target > 0.75)")
    print(f"[{run_tag}] Recall@0.5: {recall:.4f} (target > 0.70)")

    importances = pd.Series(model.feature_importances_, index=FEATURE_COLUMNS).sort_values(ascending=False)
    print("\nFeature importances:")
    print(importances)

    model_path = MODELS_DIR / f"fishing_suitability_{run_tag.lower()}.json"
    model.save_model(model_path)
    print(f"\nSaved model to {model_path}")


if __name__ == "__main__":
    main()
