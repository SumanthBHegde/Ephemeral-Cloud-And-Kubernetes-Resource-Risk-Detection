"""Event-level raw-risk fusion (design doc §9) — LABEL-FREE.

    raw_risk = w1*anomaly_score + w2*signal_matches + w3*exposure
             + w4*privilege + w5*novelty

Weights are fixed expert constants (`WEIGHTS` in this package), not learned — so this layer never
touches labels. Calibration (`calibrate.py`) turns this monotone raw score into a probability.

Inputs are columns already present on the Stage-2 detections table:
  anomaly  = ensemble_score (IF+ECOD, already [0,1])
  signal   = tripwire_hit (0/1)
  exposure = EXPOSURE_BLEND*public_exposure_flag + (1-EXPOSURE_BLEND)*norm(exposure_window_s)
  privilege= norm(privilege_level)
  novelty  = norm(principal_novelty)
"""
from __future__ import annotations

import pandas as pd

from modules.risk_fusion.fuse import EXPOSURE_BLEND, WEIGHTS


def _minmax(s: pd.Series) -> pd.Series:
    """Min-max to [0,1]; constant column -> all zeros (pure, deterministic transform)."""
    s = pd.to_numeric(s, errors="coerce")
    lo, hi = s.min(), s.max()
    if pd.isna(lo) or pd.isna(hi) or hi <= lo:
        return pd.Series(0.0, index=s.index, dtype="float64")
    return (s - lo) / (hi - lo)


def add_raw_risk(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with the fused `raw_risk` column (and its components for transparency)."""
    df = df.copy()

    anomaly = pd.to_numeric(df["ensemble_score"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    signal = df["tripwire_hit"].astype(float)
    # no exposure window (NaN) == not exposed -> 0, never median-imputed (would invent exposure).
    exp_window = _minmax(df["exposure_window_s"].fillna(0.0))
    public = pd.to_numeric(df["public_exposure_flag"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    exposure = EXPOSURE_BLEND * public + (1.0 - EXPOSURE_BLEND) * exp_window
    privilege = _minmax(df["privilege_level"])
    novelty = _minmax(df["principal_novelty"])

    df["raw_risk"] = (
        WEIGHTS["anomaly"] * anomaly
        + WEIGHTS["signal"] * signal
        + WEIGHTS["exposure"] * exposure
        + WEIGHTS["privilege"] * privilege
        + WEIGHTS["novelty"] * novelty
    )
    return df
