"""Risk-fusion layers for Stage 4.

  score.py      event-level raw_risk = fixed-weight fusion of the §5 signals (LABEL-FREE)
  calibrate.py  out-of-fold isotonic raw_risk -> p_event (the one sanctioned label touch)
  aggregate.py  member p_event -> incident risk_score (max/mean blend), floor, bands, rank

Tunables live here so every layer reads the same constants.
"""
from __future__ import annotations

RANDOM_STATE = 1337

# --- score.py: fixed expert weights for the §9 fused raw score (sum == 1.0) ---
WEIGHTS = {
    "anomaly": 0.30,    # ensemble_score (IF+ECOD), already [0,1]
    "signal": 0.25,     # tripwire_hit (rule/signal match), 0/1
    "exposure": 0.20,   # public exposure + exposure-window length
    "privilege": 0.10,  # privilege level of the action
    "novelty": 0.15,    # principal novelty
}
# blend inside the exposure term: public_exposure_flag vs normalized exposure_window_s.
EXPOSURE_BLEND = 0.5

# --- calibrate.py: out-of-fold isotonic ---
N_CALIB_FOLDS = 5

# --- aggregate.py: incident risk_score = MAX_MEAN_BLEND*max + (1-blend)*mean of member p_event ---
MAX_MEAN_BLEND = 0.7

# severity bands from the calibrated incident risk_score (checked high -> low).
BAND_THRESHOLDS = [
    ("CRITICAL", 0.80),
    ("HIGH", 0.60),
    ("MEDIUM", 0.35),
    ("LOW", 0.0),
]
# tripwire severity floor -> minimum risk_score. Handles CRITICAL forward-compatibly even though
# the current pipeline only emits HIGH/NONE (CRITICAL floor deferred — see README).
FLOOR_THRESHOLDS = {"CRITICAL": 0.80, "HIGH": 0.60}

# columns appended to the Stage-3 incident schema by the scorer.
SCORED_COLS = [
    "risk_score",
    "risk_band",
    "risk_rank",
    "mean_p_event",
    "max_exposure_window_s",
    "max_privilege_level",
    "max_novelty",
    "any_privileged",
]
