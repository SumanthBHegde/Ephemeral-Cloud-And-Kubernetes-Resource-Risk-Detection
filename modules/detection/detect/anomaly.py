"""Stage 1 — recall-first unsupervised anomaly ensemble (design doc §7, §16).

Two complementary, label-free detectors vote over the §5 feature matrix and their
min-max-normalized scores are averaged:

  - IsolationForest (scikit-learn) — primary; ~10k x 8 tabular is its sweet spot.
  - ECOD (PyOD)                    — required second vote; parameter-free, deterministic,
                                     with interpretable per-dimension contributions.

Tuned for HIGH RECALL — over-flagging here is expected and acceptable; Stage 2 (cohort
suppression) wins the precision back. Neither detector sees the held-out labels.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from modules.detection.detect import FEATURE_COLS

RANDOM_STATE = 1337
# generous contamination → IsolationForest flags broadly (recall-first).
CONTAMINATION = 0.30
# fraction of events promoted to candidates by the ensemble score (top ~35%).
CANDIDATE_QUANTILE = 0.65


def _minmax(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    if hi <= lo:
        return pd.Series(0.0, index=s.index, dtype="float64")
    return (s - lo) / (hi - lo)


def _feature_matrix(df: pd.DataFrame) -> np.ndarray:
    """Numeric feature matrix with NaNs (tag_completeness, exposure_window_s) median-imputed."""
    raw = df[FEATURE_COLS].apply(pd.to_numeric, errors="coerce")
    imputed = SimpleImputer(strategy="median").fit_transform(raw)
    return StandardScaler().fit_transform(imputed)


def score_anomaly(df: pd.DataFrame,
                  candidate_quantile: float = CANDIDATE_QUANTILE) -> pd.DataFrame:
    """Add `if_score`, `ecod_score`, `ensemble_score`, `is_candidate` columns.

    Scores are normalized to [0, 1] where higher == more anomalous. `is_candidate` flags the
    top (1 - candidate_quantile) fraction by ensemble score (recall-first).
    """
    from pyod.models.ecod import ECOD  # local import: keeps import cost off the rest of Stage 2

    df = df.copy()
    X = _feature_matrix(df)

    # IsolationForest: higher decision_function == more normal, so negate for an anomaly score.
    iforest = IsolationForest(
        n_estimators=200, contamination=CONTAMINATION, random_state=RANDOM_STATE)
    iforest.fit(X)
    if_raw = pd.Series(-iforest.decision_function(X), index=df.index)

    # ECOD: decision_scores_ already increase with outlierness.
    ecod = ECOD()
    ecod.fit(X)
    ecod_raw = pd.Series(ecod.decision_scores_, index=df.index)

    df["if_score"] = _minmax(if_raw)
    df["ecod_score"] = _minmax(ecod_raw)
    df["ensemble_score"] = (df["if_score"] + df["ecod_score"]) / 2.0

    threshold = df["ensemble_score"].quantile(candidate_quantile)
    df["is_candidate"] = df["ensemble_score"] >= threshold
    return df
