"""Stage 5 (LLM triage) regression tests.

All tests run the full Stage 0->5 chain in-memory with use_llm=False (the deterministic templated
fallback), so they need NO API key and NO network. They assert the §10 contract: every triaged record
is schema-valid, only the CRITICAL/HIGH queue is triaged, the run is deterministic, the validator
rejects malformed output, the cache round-trips on its evidence hash, the four canonical incidents are
triaged, and the fallback is both schema-valid and label-free.

Requires `data/raw/` + the enriched table buildable from it; skips otherwise.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from modules.ingest_enrich.pipeline import DEFAULT_RAW, build_enriched
from modules.detection.pipeline import run_detection
from modules.correlation.pipeline import correlate
from modules.risk_fusion.pipeline import fuse
from modules.llm_triage.pipeline import run_triage
from modules.llm_triage.evaluate import evaluate
from modules.llm_triage.triage import BANDS_TO_TRIAGE, TRIAGE_COLS, TRIAGE_FIELDS
from modules.llm_triage.triage import cache as cache_mod
from modules.llm_triage.triage.evidence import build_evidence_bundle
from modules.llm_triage.triage.fallback import build_fallback
from modules.llm_triage.triage.schema import ValidationError, validate_triage

RAW = pathlib.Path(DEFAULT_RAW)
LABELS = RAW / "labels.jsonl"
MITRE_RE = re.compile(r"^T\d{4}(\.\d{3})?$")


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
    return run_detection(enriched, out_path=None)


@pytest.fixture(scope="module")
def scored(detected):
    incidents, _ = correlate(detected)
    return fuse(detected, incidents)  # (incidents_scored, events_scored)


@pytest.fixture(scope="module")
def triaged(scored, enriched) -> pd.DataFrame:
    incidents_scored, events_scored = scored
    return run_triage(incidents_scored, enriched, events_scored,
                      out_path=None, cache_dir=None, use_llm=False)


def test_triage_schema(triaged):
    """Every triaged row carries the full schema with well-formed fields."""
    assert list(triaged.columns) == TRIAGE_COLS
    assert triaged["confidence"].between(0.0, 1.0).all()
    for _, r in triaged.iterrows():
        for f in TRIAGE_FIELDS:
            assert f in r
        assert isinstance(r["likely_intent"], str) and r["likely_intent"].strip()
        assert isinstance(r["disambiguation"], str) and r["disambiguation"].strip()
        for lf in ("mitre", "key_evidence", "recommended_guardrails"):
            assert len(r[lf]) > 0
        assert all(MITRE_RE.match(t) for t in r["mitre"]), r["mitre"]


def test_scope_bands_only(triaged, scored):
    """Only CRITICAL/HIGH incidents are triaged; the count matches the band filter."""
    incidents_scored, _ = scored
    assert set(triaged["risk_band"]) <= set(BANDS_TO_TRIAGE)
    expected = int(incidents_scored["risk_band"].isin(BANDS_TO_TRIAGE).sum())
    assert len(triaged) == expected


def test_determinism(scored, enriched):
    """Same inputs -> identical triaged output (templated fallback is deterministic)."""
    incidents_scored, events_scored = scored
    a = run_triage(incidents_scored, enriched, events_scored, out_path=None, cache_dir=None, use_llm=False)
    b = run_triage(incidents_scored, enriched, events_scored, out_path=None, cache_dir=None, use_llm=False)
    pd.testing.assert_frame_equal(a, b)


def test_validation_rejects_bad():
    """The validator rejects malformed triage objects (drives the LLM retry/fallback)."""
    base = {
        "likely_intent": "x", "confidence": 0.5, "mitre": ["T1496"],
        "key_evidence": ["e"], "disambiguation": "d", "recommended_guardrails": ["g"],
    }
    validate_triage(dict(base))                               # the happy path is accepted
    for bad in (
        {**base, "confidence": 1.5},                          # out of range
        {**base, "mitre": ["not-a-technique"]},               # malformed MITRE id
        {**base, "mitre": []},                                # empty list
        {**base, "likely_intent": ""},                        # empty string
        {k: v for k, v in base.items() if k != "disambiguation"},  # missing field
    ):
        with pytest.raises(ValidationError):
            validate_triage(bad)


def test_cache_roundtrip(scored, enriched, tmp_path):
    """put() then get() returns the record under the same evidence hash; a changed hash misses."""
    incidents_scored, events_scored = scored
    row = incidents_scored.sort_values("risk_rank").iloc[0]
    bundle = build_evidence_bundle(row, enriched, events_scored)
    h = cache_mod.evidence_hash(bundle)
    rec = build_fallback(bundle)
    rec["triage_source"] = "template"

    cache_mod.put(tmp_path, row["incident_id"], h, rec)
    got = cache_mod.get(tmp_path, row["incident_id"], h)
    assert got is not None and got["likely_intent"] == rec["likely_intent"]
    assert cache_mod.get(tmp_path, row["incident_id"], "deadbeef") is None  # stale hash -> miss


def test_cache_hit_on_rerun(scored, enriched, tmp_path):
    """A second run against a populated cache produces only cache hits (offline-demo guarantee)."""
    incidents_scored, events_scored = scored
    run_triage(incidents_scored, enriched, events_scored, out_path=None, cache_dir=tmp_path, use_llm=False)
    again = run_triage(incidents_scored, enriched, events_scored, out_path=None, cache_dir=tmp_path, use_llm=False)
    assert (again["triage_source"] == "cache").all()


def test_existence_based_reuse_and_force_refresh(scored, enriched, tmp_path):
    """An existing cache file is reused on rerun even if hand-edited (existence-based cost guard); it
    is NOT regenerated unless force_refresh=True."""
    import json
    incidents_scored, events_scored = scored
    subset = (incidents_scored[incidents_scored["risk_band"].isin(("CRITICAL", "HIGH"))]
              .sort_values("risk_rank").head(2))

    run_triage(subset, enriched, events_scored, out_path=None, cache_dir=tmp_path, use_llm=False)

    iid = subset.iloc[0]["incident_id"]
    p = tmp_path / f"{iid}.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec["likely_intent"] = "SENTINEL-DO-NOT-REGENERATE"   # still schema-valid (non-empty string)
    p.write_text(json.dumps(rec), encoding="utf-8")

    # rerun without force_refresh -> the edited file is reused, NOT regenerated
    keep = run_triage(subset, enriched, events_scored, out_path=None, cache_dir=tmp_path, use_llm=False)
    assert keep.set_index("incident_id").loc[iid, "likely_intent"] == "SENTINEL-DO-NOT-REGENERATE"

    # rerun WITH force_refresh -> the file is regenerated, sentinel overwritten
    refreshed = run_triage(subset, enriched, events_scored, out_path=None, cache_dir=tmp_path,
                           use_llm=False, force_refresh=True)
    assert refreshed.set_index("incident_id").loc[iid, "likely_intent"] != "SENTINEL-DO-NOT-REGENERATE"


def test_canonical_incidents_triaged(triaged, detected):
    """INC-A (crypto), INC-B (debug pod), INC-C (cross-source session), INC-D (buried credential
    abuse) each receive a triage record with a non-empty intent + disambiguation."""
    import json
    labels = pd.DataFrame(
        [json.loads(l) for l in LABELS.read_text(encoding="utf-8").splitlines() if l.strip()]
    ).set_index("record_id")
    incidents, event_map = correlate(detected)
    triaged_ids = set(triaged["incident_id"])
    by_id = triaged.set_index("incident_id")
    for tid in ("INC-A", "INC-B", "INC-C", "INC-D"):
        rids = labels[labels["true_incident_id"] == tid].index
        iids = event_map[event_map["record_id"].isin(rids)]["incident_id"].dropna().unique()
        hit = [i for i in iids if i in triaged_ids]
        assert hit, f"{tid} not represented in the triaged queue"
        assert all(str(by_id.loc[i, "likely_intent"]).strip() for i in hit)
        assert all(str(by_id.loc[i, "disambiguation"]).strip() for i in hit)


def test_fallback_is_schema_valid_and_label_free(scored, enriched):
    """The templated fallback passes the same validator as the LLM path, and never touches a label
    column (scenario_type / is_risky are absent from the runtime incident frame)."""
    incidents_scored, events_scored = scored
    assert "scenario_type" not in incidents_scored.columns
    assert "is_risky" not in incidents_scored.columns
    for _, row in incidents_scored.sort_values("risk_rank").head(20).iterrows():
        bundle = build_evidence_bundle(row, enriched, events_scored)
        validate_triage(build_fallback(bundle))   # raises if invalid


def test_evaluate_coverage(detected, enriched):
    """evaluate() reports full coverage of the CRITICAL+HIGH queue and appends the triage ablation row."""
    m = evaluate(detected, enriched=enriched)
    assert m["coverage"] == 1.0
    assert m["n_triaged"] == m["n_target"]
    assert m["ablation"][-1]["configuration"].startswith("+ LLM triage")
    assert all(c["triaged"] for c in m["canonical"].values())
