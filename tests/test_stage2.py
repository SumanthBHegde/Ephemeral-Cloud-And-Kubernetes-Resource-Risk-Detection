"""Stage 2 (two-stage detection) regression tests.

Asserts the detector produces a complete flag schema, is deterministic, hits the recall floor
against ground truth, and that the two-stage design behaves: cohort suppression cuts the
candidate count and lifts precision, the `unknown` cohort is never suppressed, and a tripwire
hit is always promoted to risky.

Requires `data/raw/` + the enriched table buildable from it; skips otherwise so the suite never
silently passes on missing data.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from modules.ingest_enrich.pipeline import DEFAULT_RAW, build_enriched
from modules.detection.pipeline import DETECTION_COLS, run_detection

RAW = pathlib.Path(DEFAULT_RAW)
LABELS = RAW / "labels.jsonl"


def _raw_present() -> bool:
    return (RAW / "cloudtrail.jsonl").exists() and LABELS.exists()


pytestmark = pytest.mark.skipif(
    not _raw_present(),
    reason="data/raw not generated; run `python -m modules.data_simulation.generator.build`")


@pytest.fixture(scope="module")
def enriched() -> pd.DataFrame:
    return build_enriched(RAW, out_path=None)


@pytest.fixture(scope="module")
def detected(enriched) -> pd.DataFrame:
    # run in memory so the test never clobbers the real artifact
    return run_detection(enriched, out_path=None)


@pytest.fixture(scope="module")
def labels() -> pd.DataFrame:
    rows = []
    with open(LABELS, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return pd.DataFrame(rows).set_index("record_id")


def test_detection_schema(detected):
    for col in DETECTION_COLS:
        assert col in detected.columns, f"missing detection column {col}"
    assert detected["predicted_risky"].dtype == bool
    # scores are normalized to [0, 1]
    for col in ("if_score", "ecod_score", "ensemble_score"):
        assert detected[col].between(0.0, 1.0).all()


def test_row_count_preserved(detected, enriched):
    assert len(detected) == len(enriched)
    assert detected["record_id"].is_unique


def test_deterministic(enriched):
    a = run_detection(enriched, out_path=None)
    b = run_detection(enriched, out_path=None)
    cols = ["record_id", "ensemble_score", "is_candidate", "is_suppressed", "predicted_risky"]
    pd.testing.assert_frame_equal(a[cols], b[cols])


def test_recall_floor(detected, labels):
    y_true = labels.loc[detected["record_id"], "is_risky"].astype(int).to_numpy()
    y_pred = detected["predicted_risky"].astype(int).to_numpy()
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    assert recall >= 0.70, f"recall {recall:.3f} below the 0.70 target"


def test_suppression_reduces_candidates(detected):
    # Stage 2 must drop at least some Stage-1 candidates (the whole point of suppression)
    assert int(detected["is_suppressed"].sum()) > 0
    raw = int((detected["is_candidate"] | detected["tripwire_hit"]).sum())
    pred = int(detected["predicted_risky"].sum())
    assert pred < raw, "suppression did not reduce the raw flag count"


def test_suppression_improves_precision(detected, labels):
    y_true = labels.loc[detected["record_id"], "is_risky"].astype(int).to_numpy()
    y_true = pd.Series(y_true, index=detected.index)

    def precision(pred: pd.Series) -> float:
        pred = pred.astype(int)
        tp = int(((pred == 1) & (y_true == 1)).sum())
        fp = int(((pred == 1) & (y_true == 0)).sum())
        return tp / (tp + fp) if (tp + fp) else 0.0

    no_suppression = detected["is_candidate"] | detected["tripwire_hit"]
    full = detected["predicted_risky"]
    assert precision(full) >= precision(no_suppression), \
        "suppression should not lower precision"


def test_unknown_cohort_never_suppressed(detected):
    unk = detected[detected["cohort"] == "unknown"]
    if len(unk):
        assert not unk["is_suppressed"].any(), "unknown-cohort rows must never be suppressed"


def test_tripwire_always_risky(detected):
    trip = detected[detected["tripwire_hit"]]
    if len(trip):
        assert trip["predicted_risky"].all(), "a tripwire hit must force predicted_risky"
        assert (trip["severity_floor"] == "HIGH").all()
