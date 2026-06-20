"""Stage 4 (risk fusion & calibration) regression tests.

Asserts the scorer produces a complete scored schema, calibrates monotonically, enforces the tripwire
severity floor, ranks deterministically, lifts the canonical incidents (including INC-D's buried
credential-abuse event) into the top of the queue, recovers precision via precision@K (the §13 metric;
event-level precision was ~24% after correlation), and keeps the fusion + aggregation layers label-free.

Requires `data/raw/` + the enriched table buildable from it; skips otherwise.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from modules.ingest_enrich.pipeline import DEFAULT_RAW, build_enriched
from modules.detection.pipeline import run_detection
from modules.correlation.pipeline import correlate
from modules.risk_fusion.fuse import BAND_THRESHOLDS, SCORED_COLS
from modules.risk_fusion.fuse.aggregate import aggregate_incidents
from modules.risk_fusion.fuse.calibrate import fit_full
from modules.risk_fusion.fuse.score import add_raw_risk
from modules.risk_fusion.pipeline import fuse
from modules.risk_fusion.evaluate import evaluate

RAW = pathlib.Path(DEFAULT_RAW)
LABELS = RAW / "labels.jsonl"
BANDS = {name for name, _ in BAND_THRESHOLDS}
HIGH_OR_ABOVE = {"HIGH", "CRITICAL"}


def _raw_present() -> bool:
    return (RAW / "cloudtrail.jsonl").exists() and LABELS.exists()


pytestmark = pytest.mark.skipif(
    not _raw_present(),
    reason="data/raw not generated; run `python -m modules.data_simulation.generator.build`")


@pytest.fixture(scope="module")
def detected() -> pd.DataFrame:
    return run_detection(build_enriched(RAW, out_path=None), out_path=None)


@pytest.fixture(scope="module")
def correlated(detected) -> tuple[pd.DataFrame, pd.DataFrame]:
    return correlate(detected)


@pytest.fixture(scope="module")
def scored(detected, correlated) -> tuple[pd.DataFrame, pd.DataFrame]:
    incidents, _ = correlated
    return fuse(detected, incidents)


@pytest.fixture(scope="module")
def labels() -> pd.DataFrame:
    rows = []
    with open(LABELS, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return pd.DataFrame(rows).set_index("record_id")


def _incident_ids_for(true_incident_id, correlated, labels) -> list[str]:
    _, event_map = correlated
    ids = labels[labels["true_incident_id"] == true_incident_id].index
    return event_map[event_map["record_id"].isin(ids)]["incident_id"].dropna().unique().tolist()


def test_determinism(detected, correlated):
    """Same inputs -> byte-identical risk_score (seed 1337 throughout)."""
    incidents, _ = correlated
    a, _ = fuse(detected, incidents)
    b, _ = fuse(detected, incidents)
    pd.testing.assert_series_equal(a["risk_score"], b["risk_score"])
    pd.testing.assert_series_equal(a["risk_rank"], b["risk_rank"])


def test_scored_schema(scored):
    """All Stage-3 columns survive and the SCORED_COLS are appended; scores are well-formed."""
    incidents_scored, events_scored = scored
    for col in SCORED_COLS:
        assert col in incidents_scored.columns, col
    assert incidents_scored["risk_score"].between(0.0, 1.0).all()
    assert incidents_scored["risk_band"].isin(BANDS).all()
    assert set(events_scored.columns) == {"record_id", "raw_risk", "p_event"}
    assert events_scored["p_event"].between(0.0, 1.0).all()


def test_floor_enforced(scored):
    """Every tripwire (severity_floor==HIGH) incident lands at band >= HIGH (recall protection)."""
    incidents_scored, _ = scored
    floored = incidents_scored[incidents_scored["severity_floor"] == "HIGH"]
    assert (floored["risk_score"] >= 0.60 - 1e-9).all()
    assert floored["risk_band"].isin(HIGH_OR_ABOVE).all()


def test_isotonic_monotonic(detected):
    """The calibrator is monotone in raw_risk by construction (a higher raw score never calibrates
    to a lower probability)."""
    scored_events = add_raw_risk(detected)
    y = np.zeros(len(scored_events), dtype=int)
    # any labelling works for a monotonicity check; use a simple threshold to get both classes.
    y[scored_events["raw_risk"] > scored_events["raw_risk"].median()] = 1
    cal = fit_full(scored_events["raw_risk"], y)
    grid = np.linspace(scored_events["raw_risk"].min(), scored_events["raw_risk"].max(), 50)
    preds = cal.predict(grid)
    assert (np.diff(preds) >= -1e-9).all(), "isotonic output must be non-decreasing in raw_risk"


def test_rank_is_permutation(scored):
    """risk_rank is 1..N and orders incidents by descending risk_score."""
    incidents_scored, _ = scored
    n = len(incidents_scored)
    assert sorted(incidents_scored["risk_rank"].tolist()) == list(range(1, n + 1))
    ordered = incidents_scored.sort_values("risk_rank")
    assert ordered["risk_score"].is_monotonic_decreasing


def test_canonical_incidents_high(scored, correlated, labels):
    """The crypto burst (INC-A), exposed debug pod (INC-B), and cross-source compromised session
    (INC-C) all score HIGH or CRITICAL."""
    incidents_scored, _ = scored
    by_id = incidents_scored.set_index("incident_id")
    for tid in ("INC-A", "INC-B", "INC-C"):
        iids = _incident_ids_for(tid, correlated, labels)
        assert iids, f"{tid} has no scored incident"
        bands = set(by_id.loc[iids, "risk_band"])
        assert bands <= HIGH_OR_ABOVE, f"{tid} bands {bands} not all >= HIGH"


def test_inc_d_credential_abuse(scored, correlated, labels):
    """INC-D's cluster-admin credential-abuse event, buried in the 40-pod autoscaler burst, surfaces
    as a HIGH/CRITICAL incident (it splits from the autoscaler noise by design — context.md). At least
    one of its incidents must be HIGH or above."""
    incidents_scored, _ = scored
    by_id = incidents_scored.set_index("incident_id")
    iids = _incident_ids_for("INC-D", correlated, labels)
    assert iids, "INC-D has no scored incident"
    bands = set(by_id.loc[iids, "risk_band"])
    assert bands & HIGH_OR_ABOVE, f"INC-D credential abuse must surface HIGH/CRITICAL, got {bands}"


def test_precision_recovery_at_k(detected):
    """Ranking incidents by risk_score recovers precision: precision@50 > 75% (vs ~24% event-level
    after correlation). This is the §13 risk-quality metric."""
    m = evaluate(detected)
    assert m["at_k"][50]["precision"] > 0.75, m["at_k"]
    assert m["at_k"][20]["precision"] > 0.75


def test_label_isolation(detected, correlated):
    """fusion (score.py) and aggregation (aggregate.py) never read labels: they run to completion on a
    fabricated p_event with no is_risky present. Only calibrate.py touches labels."""
    incidents, _ = correlated
    events = add_raw_risk(detected)                 # label-free
    assert "is_risky" not in events.columns
    events["p_event"] = 0.5                          # stand in for the calibrated score
    out = aggregate_incidents(incidents, events)     # label-free
    assert "risk_score" in out.columns
    assert len(out) == len(incidents)
