"""Detection layers for Stage 2.

  tripwires.py    always-on deterministic rules (severity floor)
  anomaly.py      Stage 1 — recall-first unsupervised ensemble (IsolationForest + ECOD)
  suppression.py  Stage 2 — cohort-aware suppression (rule/statistical, no ML)
"""
from __future__ import annotations

# The §5 feature matrix the anomaly ensemble scores on (all numeric, behavior-bearing).
FEATURE_COLS = [
    "burst_rate",
    "principal_novelty",
    "tag_completeness",
    "privilege_level",
    "public_exposure_flag",
    "exposure_window_s",
    "off_hours_flag",
    "cohort_deviation",
]
