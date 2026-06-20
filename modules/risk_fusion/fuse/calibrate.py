"""Out-of-fold isotonic calibration (design doc §9, §16).

This is the **one sanctioned place the pipeline reads labels** — §9/§16 explicitly permit
held-out-label calibration so a `risk_score = 0.82` behaves like a probability. Everything else in
the pipeline (detection, correlation, the raw fusion in `score.py`, the aggregation in
`aggregate.py`) is strictly label-free.

Leakage is avoided two ways:
  * `StratifiedKFold` (not plain KFold): at a ~17% risky rate plain KFold can land a fold with only
    a handful of positives and fit a degenerate isotonic curve; stratification keeps ~17% positives
    in every fold.
  * Out-of-fold prediction: each event's `p_event` comes from a model fit on the *other* folds, so
    no event is ever scored by a calibrator that saw it.

A separate full-data calibrator is also returned for the streaming path (where there is no held-out
fold to predict on).
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import StratifiedKFold

from modules.risk_fusion.fuse import N_CALIB_FOLDS, RANDOM_STATE

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
LABELS = REPO_ROOT / "data" / "raw" / "labels.jsonl"


def _load_is_risky(record_ids: pd.Series, path: pathlib.Path = LABELS) -> np.ndarray:
    """is_risky aligned 1:1 to `record_ids` (the sole label read in the scoring path)."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    labels = pd.DataFrame(rows).set_index("record_id")
    return labels.loc[record_ids, "is_risky"].astype(int).to_numpy()


def oof_calibrate(raw_risk: pd.Series, y: np.ndarray) -> pd.Series:
    """Out-of-fold isotonic probabilities for every row (no row scored by a model that saw it)."""
    x = pd.to_numeric(raw_risk, errors="coerce").fillna(0.0).to_numpy()
    p = np.zeros(len(x), dtype="float64")
    skf = StratifiedKFold(n_splits=N_CALIB_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    for train_idx, test_idx in skf.split(x, y):
        ir = IsotonicRegression(out_of_bounds="clip")
        ir.fit(x[train_idx], y[train_idx])
        p[test_idx] = ir.predict(x[test_idx])
    return pd.Series(p, index=raw_risk.index)


def fit_full(raw_risk: pd.Series, y: np.ndarray) -> IsotonicRegression:
    """Full-data calibrator for the streaming path (scores new events, no fold to hold out)."""
    x = pd.to_numeric(raw_risk, errors="coerce").fillna(0.0).to_numpy()
    return IsotonicRegression(out_of_bounds="clip").fit(x, y)


def calibrate_events(df: pd.DataFrame) -> pd.Series:
    """Given a df carrying `record_id` + `raw_risk`, return calibrated `p_event` per row."""
    y = _load_is_risky(df["record_id"])
    return oof_calibrate(df["raw_risk"], y)
