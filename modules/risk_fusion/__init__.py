"""Stage 4 — risk fusion & calibration.

Scores the incidents from Stage 3 at the **incident level** (the non-negotiable "score AFTER
clustering" ordering catch, §3). Recovers the precision that intentionally dropped to ~24% at
correlation by ranking incidents so the real attacks rise to the top of the analyst queue.
"""
