"""Stage 4 evaluation against held-out ground truth (design doc §9, §13).

Risk fusion is judged on **risk-ranking quality**, not event-level flags:

  1. **precision/recall@K** — rank incidents by `risk_score`; "relevant" = an incident whose
     ground-truth severity is HIGH or CRITICAL (§13 prioritizes recall on the severe end).
  2. **Precision recovery** — at the shipping operating point (`risk_band >= HIGH`), incident-level
     precision; this is where the event-level precision that dropped to ~24% at correlation is won
     back (target >75%).
  3. **Calibration reliability** — events binned by predicted `p_event`; observed `is_risky` rate per
     bin should track the predicted probability (the "calibration plot" extra).
  4. **Extended ablation** — the Stage 0–3 rows plus a `+ risk fusion` row (incident-level, band>=HIGH).

Incident ground-truth severity = max `severity` over the incident's `is_risky=1` members; benign-only
incidents are `none`. Labels are read ONLY here (and in calibrate.py's fit).

    python -m modules.risk_fusion.evaluate
"""
from __future__ import annotations

import pathlib

import pandas as pd

from modules.correlation.evaluate import evaluate as correlation_eval
from modules.correlation.pipeline import correlate
from modules.detection.evaluate import _load_labels
from modules.risk_fusion.pipeline import DEFAULT_DETECTIONS, fuse

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# severity ordinal (labels use none/high/critical; the rest kept for forward-compat).
SEV_ORD = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
RELEVANT_MIN = SEV_ORD["high"]   # an incident is "relevant" if GT severity >= HIGH
K_VALUES = (10, 20, 50, 100)
HIGH_BANDS = ("HIGH", "CRITICAL")


def _load_detections(detections: pd.DataFrame | None) -> pd.DataFrame:
    if detections is not None:
        return detections
    if not DEFAULT_DETECTIONS.exists():
        raise FileNotFoundError(
            f"{DEFAULT_DETECTIONS} not found; run `python -m modules.detection.build` first")
    return pd.read_parquet(DEFAULT_DETECTIONS)


def _incident_gt_severity(event_map: pd.DataFrame, labels: pd.DataFrame) -> pd.Series:
    """incident_id -> max severity ordinal over its is_risky=1 members (answer 4)."""
    m = event_map.dropna(subset=["incident_id"]).copy()
    m["is_risky"] = labels.loc[m["record_id"], "is_risky"].to_numpy()
    m["sev_ord"] = labels.loc[m["record_id"], "severity"].map(SEV_ORD).fillna(0).astype(int).to_numpy()
    risky = m[m["is_risky"] == 1]
    return risky.groupby("incident_id")["sev_ord"].max()


def evaluate(detections: pd.DataFrame | None = None) -> dict:
    """Score incidents, join labels, return a metrics dict (also used by the tests)."""
    det = _load_detections(detections)
    incidents, event_map = correlate(det)
    incidents_scored, events_scored = fuse(det, incidents)
    labels = _load_labels()

    gt = _incident_gt_severity(event_map, labels)
    relevant_ids = set(gt[gt >= RELEVANT_MIN].index)
    total_relevant = len(relevant_ids)

    # --- 1. precision/recall@K (ranked by risk_score) ---
    order = incidents_scored.sort_values("risk_rank")["incident_id"].tolist()
    at_k = {}
    for k in K_VALUES:
        topk = order[:k]
        hits = sum(i in relevant_ids for i in topk)
        denom = min(k, len(order))
        at_k[k] = {
            "precision": hits / denom if denom else 0.0,
            "recall": hits / total_relevant if total_relevant else 0.0,
        }

    # --- 2. precision recovery at the shipping operating point (band >= HIGH) ---
    pred_ids = set(incidents_scored.loc[incidents_scored["risk_band"].isin(HIGH_BANDS), "incident_id"])
    tp = len(pred_ids & relevant_ids)
    op = {
        "n_flagged_incidents": len(pred_ids),
        "precision": tp / len(pred_ids) if pred_ids else 0.0,
        "recall": tp / total_relevant if total_relevant else 0.0,
    }

    # --- 3. calibration reliability (events binned by predicted p_event) ---
    ev = events_scored.copy()
    ev["is_risky"] = labels.loc[ev["record_id"], "is_risky"].astype(int).to_numpy()
    try:
        ev["bin"] = pd.qcut(ev["p_event"], 10, duplicates="drop")
        rel = ev.groupby("bin", observed=True).agg(
            mean_pred=("p_event", "mean"), obs_risky=("is_risky", "mean"), n=("is_risky", "size"))
        reliability = rel.reset_index(drop=True).to_dict("records")
    except (ValueError, IndexError):
        reliability = []

    # --- 4. extended ablation: Stage 0-3 rows + a fusion row (incident-level, band>=HIGH) ---
    ablation = correlation_eval(det)["ablation"]
    ablation.append({
        "configuration": "+ risk fusion (incident, band>=HIGH)",
        "precision": op["precision"], "recall": op["recall"], "f1": 0.0,
        "flagged": op["n_flagged_incidents"], "alert_reduction": ablation[-1]["alert_reduction"],
    })

    return {
        "n_incidents": len(incidents_scored),
        "total_relevant": total_relevant,
        "at_k": at_k,
        "operating_point": op,
        "reliability": reliability,
        "ablation": ablation,
        "band_counts": incidents_scored["risk_band"].value_counts().to_dict(),
    }


def main() -> None:
    m = evaluate()
    print("Stage 4 risk fusion — evaluation vs ground truth (severity)\n")
    print(f"Incidents scored: {m['n_incidents']}   "
          f"relevant (GT severity >= HIGH): {m['total_relevant']}")
    print(f"Bands: " + "  ".join(f"{b}={m['band_counts'].get(b,0)}"
                                  for b in ("CRITICAL", "HIGH", "MEDIUM", "LOW")) + "\n")

    print("precision/recall @ K (incidents ranked by risk_score):")
    for k, v in m["at_k"].items():
        print(f"  @{k:<4} P={v['precision']:.2%}  R={v['recall']:.2%}")

    op = m["operating_point"]
    print(f"\nOperating point (risk_band >= HIGH): {op['n_flagged_incidents']} incidents  "
          f"P={op['precision']:.2%}  R={op['recall']:.2%}   "
          f"[precision target >75%, recovered from ~24% event-level]")

    print("\nCalibration reliability (predicted vs observed malicious rate):")
    for r in m["reliability"]:
        print(f"  pred={r['mean_pred']:.2f}  observed={r['obs_risky']:.2f}  n={int(r['n'])}")

    print("\nFull ablation table:")
    for row in m["ablation"]:
        print(f"  {row['configuration']:<38} "
              f"P={row['precision']:.2%}  R={row['recall']:.2%}  "
              f"flagged={int(row['flagged'])}  alert_reduction={row['alert_reduction']:.0%}")


if __name__ == "__main__":
    main()
