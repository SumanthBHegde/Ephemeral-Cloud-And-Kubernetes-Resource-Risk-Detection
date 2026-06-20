"""Stage 3 evaluation against ground truth (design doc §13).

Reports the three things correlation is judged on:

  1. **Alert reduction** — raw rule/ML flags collapsed into incidents, against the *same*
     denominator Stage 2 used (`tripwire_hit | is_candidate`), so the 8% -> X% jump is
     apples-to-apples. Target >=40%.
  2. **Correlation accuracy vs `campaign_id`** — homogeneity / completeness / V-measure of the
     incident assignment against the injected campaign labels (member events only), plus a
     per-canonical-incident recovery check (does each true incident land in one cluster).
  3. **The extended ablation table** — the Stage-2 rows (tripwires / +ensemble / +suppression)
     with a `+ graph correlation` row appended, showing the alert-reduction jump.

Labels are read ONLY here; the correlator never sees them.

    python -m modules.correlation.evaluate
"""
from __future__ import annotations

import pathlib

import pandas as pd
from sklearn.metrics import homogeneity_completeness_v_measure

from modules.correlation.pipeline import DEFAULT_IN, correlate
from modules.detection.evaluate import _load_labels, _prf
from modules.detection.evaluate import evaluate as detection_ablation

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# the four canonical incidents and a human label for the recovery check.
CANONICAL = {
    "INC-A": "crypto burst (40x RunInstances)",
    "INC-B": "exposed debug pod",
    "INC-C": "compromised session -> PII (cross-source)",
    "INC-D": "credential abuse buried in autoscaler noise",
}


def _load_detections(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is not None:
        return df
    if not DEFAULT_IN.exists():
        raise FileNotFoundError(
            f"{DEFAULT_IN} not found; run `python -m modules.detection.build` first")
    return pd.read_parquet(DEFAULT_IN)


def evaluate(df: pd.DataFrame | None = None) -> dict:
    """Correlate detections, join labels, return a metrics dict (also used by the tests)."""
    df = _load_detections(df)
    incidents, event_map = correlate(df)
    labels = _load_labels()

    # --- 1. alert reduction (Stage-2 denominator, locked) ---
    raw_flagged = int((df["tripwire_hit"] | df["is_candidate"]).sum())
    n_incidents = len(incidents)
    alert_reduction = 1 - n_incidents / raw_flagged if raw_flagged else 0.0

    # --- 2. correlation accuracy vs campaign_id (member events with a campaign label) ---
    members = event_map.dropna(subset=["incident_id"]).copy()
    members["campaign_id"] = labels.loc[members["record_id"], "campaign_id"].to_numpy()
    scored = members.dropna(subset=["campaign_id"])
    if len(scored):
        homo, compl, vmeasure = homogeneity_completeness_v_measure(
            scored["campaign_id"].to_numpy(), scored["incident_id"].to_numpy())
    else:
        homo = compl = vmeasure = 0.0

    # per-canonical recovery: how many incidents does each true incident scatter into?
    members["true_incident_id"] = labels.loc[members["record_id"], "true_incident_id"].to_numpy()
    canonical = {}
    for tid in CANONICAL:
        rows = members[members["true_incident_id"] == tid]
        canonical[tid] = {
            "events_in_incidents": int(len(rows)),
            "n_incidents": int(rows["incident_id"].nunique()),
        }

    # --- 3. extended ablation: Stage-2 rows + a graph-correlation row (event level) ---
    y_true = labels.loc[df["record_id"], "is_risky"].astype(int).to_numpy()
    in_incident = df["record_id"].isin(members["record_id"]).astype(int).to_numpy()
    p, r, f1 = _prf(pd.Series(y_true), pd.Series(in_incident))
    ablation = detection_ablation(df).to_dict("records")
    ablation.append({
        "configuration": "+ graph correlation", "precision": p, "recall": r, "f1": f1,
        "flagged": n_incidents, "alert_reduction": alert_reduction,
    })

    return {
        "raw_flagged": raw_flagged,
        "n_incidents": n_incidents,
        "alert_reduction": alert_reduction,
        "homogeneity": homo,
        "completeness": compl,
        "v_measure": vmeasure,
        "canonical": canonical,
        "ablation": ablation,
    }


def main() -> None:
    m = evaluate()
    print("Stage 3 correlation — evaluation vs ground truth\n")
    print(f"Alert reduction:  {m['raw_flagged']} raw flags -> {m['n_incidents']} incidents "
          f"({m['alert_reduction']:.0%})   [target >=40%]")
    print(f"Correlation acc:  homogeneity={m['homogeneity']:.2f}  "
          f"completeness={m['completeness']:.2f}  V-measure={m['v_measure']:.2f}  "
          f"(vs campaign_id)\n")

    print("Canonical incident recovery (events -> # incidents):")
    for tid, label in CANONICAL.items():
        c = m["canonical"][tid]
        flag = "OK" if c["n_incidents"] <= 1 else f"split x{c['n_incidents']}"
        print(f"  {tid:6} {label:42} {c['events_in_incidents']:2} ev -> "
              f"{c['n_incidents']} inc  [{flag}]")

    print("\nAblation table (precision/recall on events, alert reduction on flags):")
    for row in m["ablation"]:
        print(f"  {row['configuration']:<30} "
              f"P={row['precision']:.2%}  R={row['recall']:.2%}  F1={row['f1']:.2f}  "
              f"flagged={int(row['flagged'])}  alert_reduction={row['alert_reduction']:.0%}")


if __name__ == "__main__":
    main()
