"""Stage 2 — Two-Stage Detection.

Reads the Stage-1 enriched table and flags risky events with three layers:
always-on rule tripwires, a recall-first unsupervised anomaly ensemble
(IsolationForest + ECOD), and cohort-aware suppression for precision.

Public entrypoint:
    from modules.detection.pipeline import run_detection
"""
