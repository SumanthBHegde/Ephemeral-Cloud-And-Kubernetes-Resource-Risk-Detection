"""Always-on rule tripwires (design doc §3 step 2).

Deterministic, always-on checks that force a severity floor: a tripwire hit is promoted to
`predicted_risky=1` regardless of the ML score and is *never* suppressed by the cohort stage.
These encode the four canonical danger signals directly, so the demoable V1 catches the
headline incidents even before any ML runs.

The rules read the §5 feature columns + the lifted raw signals already present on the
enriched table — no recomputation.
"""
from __future__ import annotations

import pandas as pd

# burst size that is suspicious on its own (matches the "burst > 10 in 5 min" rule).
BURST_TRIPWIRE = 10


def apply_tripwires(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with `tripwire_hit` (bool) and `severity_floor` (str) columns added."""
    df = df.copy()

    # NodePort 0.0.0.0/0 — the exposed debug-pod danger (public_exposure_flag == 1.0).
    nodeport_open = df["public_exposure_flag"].fillna(0.0) >= 1.0

    # bare privileged pod — no controller owner + privileged (container-escape surface).
    bare_priv = df["controller_owner"].isna() & df["privileged"].fillna(False).astype(bool)

    # burst of same-action events by one principal in the 5-min window.
    burst = df["burst_rate"].fillna(0) > BURST_TRIPWIRE

    # broad RBAC — cluster-admin / wildcard binding (the buried credential-abuse event).
    broad = df["broad_rbac"].fillna(False).astype(bool)

    # unrecognized identity — a principal that fits no known behavioral cohort is itself the
    # signal (design doc thesis; see ingest_enrich README). The anomaly model cannot catch
    # these: they form a dense same-shape cluster (the identity_anomaly campaign), not sparse
    # outliers. This is a context tripwire, not a volume/value one.
    unknown_cohort = df["cohort"].eq("unknown")

    hit = nodeport_open | bare_priv | burst | broad | unknown_cohort
    df["tripwire_hit"] = hit
    df["severity_floor"] = hit.map({True: "HIGH", False: "NONE"})
    return df
