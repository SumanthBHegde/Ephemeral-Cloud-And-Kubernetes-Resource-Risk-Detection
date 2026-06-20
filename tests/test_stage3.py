"""Stage 3 (graph correlation) regression tests.

Asserts the correlator produces a complete incident schema, enforces seed-originated 1-hop
expansion (no bridge ever originates an edge), recovers the canonical incidents (crypto burst
collapses to one; the cross-source compromised-session chain lands in one incident), respects the
identity+namespace+time envelope (web/prod bursts never merge), hits the alert-reduction target,
and that the per-event map is complete and joinable.

Requires `data/raw/` + the enriched table buildable from it; skips otherwise.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from modules.ingest_enrich.pipeline import DEFAULT_RAW, build_enriched
from modules.detection.pipeline import run_detection
from modules.correlation.graph import INCIDENT_COLS, build_graph
from modules.correlation.pipeline import correlate

RAW = pathlib.Path(DEFAULT_RAW)
LABELS = RAW / "labels.jsonl"


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
    # run in memory so the test never clobbers the real artifact
    return correlate(detected)


@pytest.fixture(scope="module")
def labels() -> pd.DataFrame:
    rows = []
    with open(LABELS, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return pd.DataFrame(rows).set_index("record_id")


def _members_of(true_incident_id, correlated, labels) -> pd.DataFrame:
    """event_map rows whose record belongs to a given canonical true incident."""
    _, event_map = correlated
    ids = labels[labels["true_incident_id"] == true_incident_id].index
    return event_map[event_map["record_id"].isin(ids)]


def test_incident_schema(correlated):
    incidents, event_map = correlated
    assert list(incidents.columns) == INCIDENT_COLS
    assert incidents["incident_id"].is_unique
    # flat source counts are ints; list columns hold python lists
    for col in ("source_cloudtrail_count", "source_k8s_count", "source_idp_count",
                "event_count", "n_flagged", "n_bridge", "tripwire_hits"):
        assert pd.api.types.is_integer_dtype(incidents[col]), col
    assert incidents["edge_types"].apply(lambda v: isinstance(v, list)).all()
    assert incidents["member_record_ids"].apply(lambda v: isinstance(v, list)).all()
    # event_count == flagged + bridge, always
    assert (incidents["event_count"] == incidents["n_flagged"] + incidents["n_bridge"]).all()
    assert event_map.columns.tolist() == ["record_id", "incident_id"]


def test_one_hop_only(detected):
    """No bridge (unflagged) event may originate an edge: every edge touches >=1 seed. This is the
    build-time guarantee that bridges are leaves and 2-hop expansion can never happen."""
    df = detected.copy()
    df["is_seed"] = df["predicted_risky"].astype(bool)
    g = build_graph(df)
    seeds = set(df.loc[df["is_seed"], "record_id"])
    for u, v in g.edges():
        assert (u in seeds) or (v in seeds), f"edge {u}-{v} has no seed endpoint (bridge-originated)"
    # corollary: every non-seed node's neighbours are all seeds (a bridge never touches a bridge)
    for node in g.nodes():
        if node not in seeds:
            assert all(nbr in seeds for nbr in g.neighbors(node))


def test_autoscaler_collapse(correlated, labels):
    """INC-A's 40-event crypto burst collapses to exactly one incident (noise reduction made
    literal)."""
    inc_a = _members_of("INC-A", correlated, labels)
    assert len(inc_a) == 40
    assert inc_a["incident_id"].nunique() == 1, "INC-A must collapse to a single incident"


def test_cross_source_chain(correlated, labels):
    """INC-C's IdP login + AssumeRole + S3 GetObjects land in one incident spanning >=2 sources."""
    incidents, _ = correlated
    inc_c = _members_of("INC-C", correlated, labels)
    assert inc_c["incident_id"].nunique() == 1, "INC-C cross-source chain must be one incident"
    iid = inc_c["incident_id"].iloc[0]
    row = incidents.set_index("incident_id").loc[iid]
    sources_present = sum(int(row[c] > 0) for c in
                          ("source_cloudtrail_count", "source_k8s_count", "source_idp_count"))
    assert sources_present >= 2, "INC-C incident must span more than one source"
    assert row["severity_floor"] == "HIGH"


def test_credential_abuse_captured(correlated, labels):
    """The real credential-abuse event buried in INC-D's autoscaler noise is not dropped: it is a
    flagged member of a HIGH-severity incident."""
    incidents, _ = correlated
    inc_d = _members_of("INC-D", correlated, labels)
    assert len(inc_d) == 2
    iids = inc_d["incident_id"].dropna().unique()
    assert len(iids) >= 1
    sev = incidents.set_index("incident_id").loc[iids, "severity_floor"]
    assert (sev == "HIGH").any(), "INC-D's credential-abuse event must surface as HIGH"


def test_envelope_no_overmerge(correlated):
    """Namespace partitioning holds: a Kubernetes-only incident never mixes namespaces (e.g. a
    `web` autoscaler burst can't merge with a `prod` one just by sharing the controller identity)."""
    incidents, _ = correlated
    k8s_only = incidents[incidents["source_k8s_count"] == incidents["event_count"]]
    bad = k8s_only[k8s_only["namespaces"].apply(len) > 1]
    assert bad.empty, f"{len(bad)} k8s-only incidents merged across namespaces"


def test_alert_reduction_target(detected, correlated):
    """Raw flags collapse into incidents by >=40% (same denominator as Stage 2)."""
    incidents, _ = correlated
    raw_flagged = int((detected["tripwire_hit"] | detected["is_candidate"]).sum())
    reduction = 1 - len(incidents) / raw_flagged
    assert reduction >= 0.40, f"alert reduction {reduction:.0%} below the 40% target"


def test_event_map_complete(detected, correlated, labels):
    """Every input event appears in the map exactly once; members reference real records;
    non-members carry a null incident_id (risk_fusion needs the full event set)."""
    incidents, event_map = correlated
    assert len(event_map) == len(detected)
    assert event_map["record_id"].is_unique
    assert set(event_map["record_id"]) == set(detected["record_id"])
    # every member_record_id is a real detection record
    all_members = {rid for lst in incidents["member_record_ids"] for rid in lst}
    assert all_members <= set(detected["record_id"])
    # the map's non-null incident_ids are exactly the union of member lists
    mapped = set(event_map.dropna(subset=["incident_id"])["record_id"])
    assert mapped == all_members
