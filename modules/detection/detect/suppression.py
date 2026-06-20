"""Stage 2 — cohort-aware suppression (design doc §7). Rule/statistical, no ML.

The recall-first ensemble over-flags by design. Here we drop candidates that are *normal for
their cohort*, which is where precision is won without giving back Stage-1 recall:

  suppress a candidate IFF all hold —
    - cohort is a recognized one (NOT `unknown` — an unknown cohort is itself the signal),
    - it is in-distribution for that cohort (cohort_deviation below the cohort's 75th pct),
    - tag_completeness is high (>= 0.5) or undefined for the cohort (NaN),
    - it is in-cohort hours (off_hours_flag == 0),
    - it is NOT a tripwire hit (tripwires force a severity floor and are never suppressed).

`predicted_risky = (is_candidate & ~is_suppressed) | tripwire_hit`.
"""
from __future__ import annotations

import pandas as pd

DEVIATION_PCT = 0.75
TAG_OK = 0.5


def apply_suppression(df: pd.DataFrame) -> pd.DataFrame:
    """Add `is_suppressed` and `predicted_risky` columns.

    Expects `is_candidate` (anomaly) and `tripwire_hit` (rules) already present.
    """
    df = df.copy()

    # per-cohort 75th-percentile of cohort_deviation → "in-distribution for its cohort".
    dev = df["cohort_deviation"].fillna(0.0)
    pct = df.groupby("cohort")["cohort_deviation"].transform(
        lambda s: s.fillna(0.0).quantile(DEVIATION_PCT))
    in_distribution = dev <= pct

    known_cohort = df["cohort"].ne("unknown")
    tags_ok = df["tag_completeness"].isna() | (df["tag_completeness"] >= TAG_OK)
    in_hours = df["off_hours_flag"].fillna(0).astype(int) == 0
    not_tripwire = ~df["tripwire_hit"]

    cohort_normal = known_cohort & in_distribution & tags_ok & in_hours & not_tripwire

    df["is_suppressed"] = df["is_candidate"] & cohort_normal
    df["predicted_risky"] = (
        (df["is_candidate"] & ~df["is_suppressed"]) | df["tripwire_hit"]
    )
    return df
