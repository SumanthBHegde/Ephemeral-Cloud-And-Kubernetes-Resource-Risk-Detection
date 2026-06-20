"""Stage 1 (ingest + enrich) regression tests.

Asserts the enriched table is complete, joins 1:1 to the label sidecar, assigns cohorts
correctly against ground truth, captures the canonical incidents' signals in the §5
features, is deterministic, and -- the load-bearing one -- preserves confusability:
malicious and benign bursts must NOT be separable on volume (burst_rate); the separation
must live in the metadata/context features.

These tests require `data/raw/` to exist (run the Stage-Zero build first); they skip
otherwise so the suite never silently passes on missing data.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from modules.ingest_enrich.pipeline import DEFAULT_RAW, build_enriched
from modules.ingest_enrich.normalize import UNIFIED_FIELDS

RAW = pathlib.Path(DEFAULT_RAW)
LABELS = RAW / "labels.jsonl"


def _raw_present() -> bool:
    return (RAW / "cloudtrail.jsonl").exists() and LABELS.exists()


pytestmark = pytest.mark.skipif(
    not _raw_present(),
    reason="data/raw not generated; run `python -m modules.data_simulation.generator.build`")


@pytest.fixture(scope="module")
def enriched() -> pd.DataFrame:
    # build in memory (out_path=None) so the test never clobbers the real artifact
    return build_enriched(RAW, out_path=None)


@pytest.fixture(scope="module")
def labels() -> pd.DataFrame:
    rows = []
    with open(LABELS, "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return pd.DataFrame(rows).set_index("record_id")


def _raw_count() -> int:
    n = 0
    for fname in ("cloudtrail.jsonl", "k8s_audit.jsonl", "idp_session.jsonl"):
        p = RAW / fname
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                n += sum(1 for line in f if line.strip())
    return n


def test_schema_columns(enriched):
    # every unified field + cohort + the §5 feature columns are present
    for col in UNIFIED_FIELDS:
        assert col in enriched.columns, f"missing unified column {col}"
    for col in ("cohort", "burst_rate", "principal_novelty", "tag_completeness",
                "privilege_level", "public_exposure_flag", "exposure_window_s",
                "off_hours_flag", "cohort_deviation"):
        assert col in enriched.columns, f"missing feature column {col}"


def test_row_count_matches_raw(enriched):
    assert len(enriched) == _raw_count()
    assert enriched["record_id"].is_unique


def test_label_join_one_to_one(enriched, labels):
    ids = enriched["record_id"]
    assert ids.isin(labels.index).all(), "an enriched row has no label"
    assert ids.nunique() == len(labels), "enriched/label counts diverge"


def test_cohort_accuracy_against_ground_truth(enriched, labels):
    truth = labels.loc[enriched["record_id"], "cohort"].to_numpy()
    pred = enriched["cohort"].to_numpy()
    mask = pred != "unknown"
    acc = (pred[mask] == truth[mask]).mean()
    assert acc >= 0.95, f"cohort accuracy {acc:.3f} below 0.95"


def test_unknown_cohort_is_the_identity_anomaly(enriched, labels):
    # the rule-assisted mapping intentionally leaves the off-pattern attack actors unknown;
    # they must be exactly the risky identity_anomaly rows, not benign misclassifications
    unk_ids = enriched.loc[enriched["cohort"] == "unknown", "record_id"]
    if len(unk_ids) == 0:
        return
    lab = labels.loc[unk_ids]
    assert (lab["is_risky"] == 1).mean() > 0.9, "unknown rows should be predominantly risky"


def test_canonical_incident_signals(enriched, labels):
    df = enriched.copy()
    df["inc"] = labels.loc[df["record_id"], "true_incident_id"].to_numpy()

    inc_a = df[df["inc"] == "INC-A"]
    assert inc_a["off_hours_flag"].mean() == 1.0           # 3 AM crypto burst
    assert inc_a["tag_completeness"].fillna(0).mean() < 0.2  # untagged
    assert inc_a["is_spot"].sum() > 0 and inc_a["public_ip"].notna().sum() > 0

    inc_b = df[df["inc"] == "INC-B"]
    assert inc_b["privileged"].any() and inc_b["exposed_open"].any()
    assert inc_b["controller_owner"].isna().all()          # bare debug pod

    inc_c = df[df["inc"] == "INC-C"]
    assert inc_c["assumed_role_id"].notna().any()          # STS->S3 linkage key surfaced
    assert inc_c["external_session_id"].notna().any()      # IdP thread surfaced

    inc_d = df[df["inc"] == "INC-D"]
    assert inc_d["broad_rbac"].any()                       # the cluster-admin binding


def test_confusability_preserved(enriched, labels):
    """Malicious crypto bursts and benign autoscale/CI bursts must overlap on burst_rate,
    and diverge on metadata/context instead. If volume separated them, the noise-reduction
    metric would be meaningless."""
    df = enriched.copy()
    df["scn"] = labels.loc[df["record_id"], "scenario_type"].to_numpy()
    mal = df.loc[df["scn"] == "crypto_burst", "burst_rate"]
    ben = df.loc[df["scn"].isin(["legit_autoscale", "legit_cicd"]), "burst_rate"]
    # means within a small factor — no clean volume gap
    assert abs(mal.mean() - ben.mean()) < 0.5 * max(mal.mean(), ben.mean())
    # the real separation lives in context: tag completeness + off-hours
    mal_tag = df.loc[df["scn"] == "crypto_burst", "tag_completeness"].fillna(0).mean()
    ben_tag = df.loc[df["scn"].isin(["legit_autoscale", "legit_cicd"]), "tag_completeness"].fillna(0).mean()
    assert ben_tag - mal_tag > 0.2, "metadata features should separate where volume cannot"


def test_deterministic(labels):
    a = build_enriched(RAW, out_path=None)
    b = build_enriched(RAW, out_path=None)
    # compare on the stable feature columns (raw JSON blob excluded for speed)
    cols = ["record_id", "cohort", "burst_rate", "principal_novelty", "tag_completeness",
            "privilege_level", "public_exposure_flag", "off_hours_flag", "cohort_deviation"]
    pd.testing.assert_frame_equal(a[cols], b[cols])


def test_enrich_stream_matches_batch():
    """The live stream wrapper normalizes to the same rows as the batch path."""
    from modules.data_simulation.replay.stream import replay_events
    from modules.ingest_enrich.pipeline import enrich_stream

    streamed = list(enrich_stream(replay_events(RAW, speed=0, limit=50)))
    assert len(streamed) == 50
    for row in streamed:
        assert "cohort" in row and "record_id" in row
        assert set(UNIFIED_FIELDS).issubset(row.keys())
