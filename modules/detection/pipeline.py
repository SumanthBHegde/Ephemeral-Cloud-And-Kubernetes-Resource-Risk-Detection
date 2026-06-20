"""Stage 2 orchestrator: enriched events -> detection flags (Parquet).

    run_detection()   read data/processed/events_enriched.parquet (or accept a DataFrame),
                      run tripwires -> anomaly ensemble -> cohort suppression, append the
                      detection columns, and (optionally) write data/processed/detections.parquet.

The three layers run in pipeline order: always-on tripwires set a severity floor first, the
recall-first ensemble flags candidates, then cohort suppression trims them. Risk *scoring* is a
later stage (after clustering) — this stage only produces candidate/suppressed/predicted flags.
"""
from __future__ import annotations

import pathlib
from typing import Optional

import pandas as pd

from modules.detection.detect.anomaly import score_anomaly
from modules.detection.detect.suppression import apply_suppression
from modules.detection.detect.tripwires import apply_tripwires

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_IN = REPO_ROOT / "data" / "processed" / "events_enriched.parquet"
DEFAULT_OUT = REPO_ROOT / "data" / "processed" / "detections.parquet"

# columns this stage appends to the enriched table.
DETECTION_COLS = [
    "if_score", "ecod_score", "ensemble_score", "is_candidate",
    "tripwire_hit", "is_suppressed", "predicted_risky", "severity_floor",
]


def run_detection(source: pd.DataFrame | pathlib.Path | str = DEFAULT_IN,
                  out_path: Optional[pathlib.Path | str] = DEFAULT_OUT) -> pd.DataFrame:
    """Run the full two-stage detector. `source` is an enriched df or a Parquet path."""
    if isinstance(source, pd.DataFrame):
        df = source.copy()
    else:
        path = pathlib.Path(source)
        if not path.exists():
            raise FileNotFoundError(
                f"enriched table not found at {path}; run "
                f"`python -m modules.ingest_enrich.build` first")
        df = pd.read_parquet(path)

    df = apply_tripwires(df)      # tripwire_hit, severity_floor
    df = score_anomaly(df)        # if/ecod/ensemble scores, is_candidate
    df = apply_suppression(df)    # is_suppressed, predicted_risky

    if out_path is not None:
        out_path = pathlib.Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_path, engine="pyarrow", index=False)
    return df
