"""Stage 5 evaluation (design doc §10, §13).

Triage doesn't change which incidents are flagged — it annotates the CRITICAL/HIGH queue with
validated narratives. So its metrics are about *coverage and provenance*, plus a canonical spot-check
that the four hand-built incidents (INC-A crypto, INC-B debug pod, INC-C cross-source session,
INC-D buried credential abuse) each receive a triage record. The ablation table is extended with a
`+ LLM triage` row carrying the band>=HIGH operating point (the set triage covers).

Runs offline (use_llm=False) so the metric is deterministic and needs no API key:

    python -m modules.llm_triage.evaluate
"""
from __future__ import annotations

import pathlib

import pandas as pd

from modules.correlation.pipeline import correlate
from modules.detection.evaluate import _load_labels
from modules.llm_triage.pipeline import run_triage
from modules.llm_triage.triage import BANDS_TO_TRIAGE
from modules.risk_fusion.evaluate import evaluate as fusion_eval
from modules.risk_fusion.pipeline import DEFAULT_DETECTIONS, fuse

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CANONICAL = ("INC-A", "INC-B", "INC-C", "INC-D")


def _load_detections(detections: pd.DataFrame | None) -> pd.DataFrame:
    if detections is not None:
        return detections
    if not DEFAULT_DETECTIONS.exists():
        raise FileNotFoundError(
            f"{DEFAULT_DETECTIONS} not found; run `python -m modules.detection.build` first")
    return pd.read_parquet(DEFAULT_DETECTIONS)


def _incident_ids_for(true_incident_id, event_map, labels) -> list[str]:
    """Scored incident_ids whose members belong to a given ground-truth incident (test_stage4 helper)."""
    ids = labels[labels["true_incident_id"] == true_incident_id].index
    return event_map[event_map["record_id"].isin(ids)]["incident_id"].dropna().unique().tolist()


def evaluate(detections: pd.DataFrame | None = None,
             enriched: pd.DataFrame | None = None,
             events_scored: pd.DataFrame | None = None) -> dict:
    """Triage the CRITICAL/HIGH queue offline and return a metrics dict (also used by the tests)."""
    det = _load_detections(detections)
    incidents, event_map = correlate(det)
    incidents_scored, evs = fuse(det, incidents)
    if events_scored is not None:
        evs = events_scored

    if enriched is None:
        from modules.ingest_enrich.pipeline import DEFAULT_OUT as ENRICHED_OUT
        enriched = pd.read_parquet(ENRICHED_OUT)

    triaged = run_triage(incidents_scored, enriched, evs,
                         out_path=None, cache_dir=None, bands=BANDS_TO_TRIAGE, use_llm=False)

    n_target = int(incidents_scored["risk_band"].isin(BANDS_TO_TRIAGE).sum())
    coverage = len(triaged) / n_target if n_target else 0.0

    # canonical spot-check: each hand-built incident has at least one triaged record w/ non-empty intent.
    labels = _load_labels()
    triaged_ids = set(triaged["incident_id"])
    by_id = triaged.set_index("incident_id")
    canonical = {}
    for tid in CANONICAL:
        iids = _incident_ids_for(tid, event_map, labels)
        hit = [i for i in iids if i in triaged_ids]
        intents = [by_id.loc[i, "likely_intent"] for i in hit]
        canonical[tid] = {
            "triaged": bool(hit),
            "non_empty_intent": all(bool(str(s).strip()) for s in intents) if intents else False,
        }

    # extend the Stage 0-4 ablation with a triage row over the band>=HIGH operating point.
    f = fusion_eval(det)
    op = f["operating_point"]
    ablation = f["ablation"]
    ablation.append({
        "configuration": "+ LLM triage (CRITICAL+HIGH narratives)",
        "precision": op["precision"], "recall": op["recall"], "f1": 0.0,
        "flagged": len(triaged), "alert_reduction": ablation[-1]["alert_reduction"],
    })

    return {
        "n_triaged": len(triaged),
        "n_target": n_target,
        "coverage": coverage,
        "source_counts": triaged["triage_source"].value_counts().to_dict(),
        "mean_confidence": float(triaged["confidence"].mean()) if len(triaged) else 0.0,
        "mitre_coverage": float((triaged["mitre"].apply(len) > 0).mean()) if len(triaged) else 0.0,
        "canonical": canonical,
        "ablation": ablation,
    }


def main() -> None:
    m = evaluate()
    print("Stage 5 LLM triage — evaluation (offline / templated)\n")
    print(f"Triaged {m['n_triaged']}/{m['n_target']} CRITICAL+HIGH incidents "
          f"(coverage {m['coverage']:.0%})")
    print(f"Provenance: " + "  ".join(f"{k}={v}" for k, v in m["source_counts"].items()))
    print(f"Mean confidence: {m['mean_confidence']:.2f}   "
          f"MITRE coverage: {m['mitre_coverage']:.0%}\n")

    print("Canonical incident spot-check:")
    for tid, c in m["canonical"].items():
        print(f"  {tid}: triaged={c['triaged']}  non_empty_intent={c['non_empty_intent']}")

    print("\nFull ablation table:")
    for row in m["ablation"]:
        print(f"  {row['configuration']:<42} "
              f"P={row['precision']:.2%}  R={row['recall']:.2%}  "
              f"flagged={int(row['flagged'])}  alert_reduction={row['alert_reduction']:.0%}")


if __name__ == "__main__":
    main()
