"""Stage 2 evaluation against held-out ground truth (design doc §13).

Joins `data/raw/labels.jsonl` to the detections on `record_id` (1:1) and reports
precision / recall / F1 of `predicted_risky` vs `is_risky`, the alert-reduction number, and the
**ablation table** rows available at this stage:

    tripwires only          -> rule layer alone
    + Stage-1 ensemble      -> tripwires OR anomaly candidates (no suppression)
    + Stage-2 suppression   -> the full two-stage detector (what ships)

(The +graph/+fusion row arrives with later stages.) Labels are read ONLY here — the detector
itself never sees them.

    python -m modules.detection.evaluate
"""
from __future__ import annotations

import json
import pathlib

import pandas as pd

from modules.detection.pipeline import DEFAULT_IN, run_detection

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
LABELS = REPO_ROOT / "data" / "raw" / "labels.jsonl"


def _load_labels(path: pathlib.Path = LABELS) -> pd.DataFrame:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return pd.DataFrame(rows).set_index("record_id")


def _prf(y_true: pd.Series, y_pred: pd.Series) -> tuple[float, float, float]:
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def evaluate(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Run detection (if no df given), join labels, return the ablation DataFrame."""
    if df is None:
        df = run_detection(DEFAULT_IN, out_path=None)
    labels = _load_labels()
    y_true = labels.loc[df["record_id"], "is_risky"].astype(int).to_numpy()
    y_true = pd.Series(y_true, index=df.index)

    # the three ablation configurations, as boolean predicted-risky series.
    configs = {
        "tripwires only": df["tripwire_hit"],
        "+ Stage-1 ensemble": df["tripwire_hit"] | df["is_candidate"],
        "+ Stage-2 suppression (full)": df["predicted_risky"],
    }

    raw_candidates = int((df["tripwire_hit"] | df["is_candidate"]).sum())
    out_rows = []
    for name, pred in configs.items():
        pred = pred.astype(int)
        p, r, f1 = _prf(y_true, pred)
        flagged = int(pred.sum())
        reduction = (1 - flagged / raw_candidates) if raw_candidates else 0.0
        out_rows.append({
            "configuration": name, "precision": p, "recall": r, "f1": f1,
            "flagged": flagged, "alert_reduction": reduction,
        })
    return pd.DataFrame(out_rows)


def main() -> None:
    table = evaluate()
    print("Stage 2 detection — evaluation vs ground truth (is_risky)\n")
    for _, row in table.iterrows():
        print(f"  {row['configuration']:<30} "
              f"P={row['precision']:.2%}  R={row['recall']:.2%}  F1={row['f1']:.2f}  "
              f"flagged={int(row['flagged'])}  "
              f"alert_reduction={row['alert_reduction']:.0%}")
    full = table.iloc[-1]
    print(f"\nTargets: precision >75%, recall >70%, alert reduction >=40%")
    print(f"Full pipeline: precision {full['precision']:.2%}, recall {full['recall']:.2%}, "
          f"alert reduction {full['alert_reduction']:.0%}")


if __name__ == "__main__":
    main()
