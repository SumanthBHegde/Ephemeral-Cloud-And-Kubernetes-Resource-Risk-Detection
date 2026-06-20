"""Stage 4 orchestrator: detections + incidents -> scored incidents (Parquet).

    run_fusion()  read data/processed/detections.parquet + incidents.parquet (or accept DataFrames),
                  fuse a per-event raw_risk, calibrate it to p_event (out-of-fold isotonic), and
                  aggregate to incident-level risk_score + band + rank. Writes incidents_scored.parquet
                  (primary) + events_scored.parquet (per-event raw_risk/p_event for dashboard + LLM).

This is the "score AFTER clustering" stage (§3): incidents come pre-clustered from Stage 3; here we
only score them. Labels are touched ONLY by the calibration step (calibrate.py), never by fusion or
aggregation.
"""
from __future__ import annotations

import pathlib
from typing import Optional

import pandas as pd

from modules.risk_fusion.fuse.aggregate import aggregate_incidents
from modules.risk_fusion.fuse.calibrate import calibrate_events
from modules.risk_fusion.fuse.score import add_raw_risk

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_DETECTIONS = REPO_ROOT / "data" / "processed" / "detections.parquet"
DEFAULT_INCIDENTS = REPO_ROOT / "data" / "processed" / "incidents.parquet"
DEFAULT_OUT = REPO_ROOT / "data" / "processed" / "incidents_scored.parquet"
DEFAULT_EVENTS_OUT = REPO_ROOT / "data" / "processed" / "events_scored.parquet"


def fuse(detections: pd.DataFrame,
         incidents: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pure in-memory fusion: (detections, incidents) -> (incidents_scored, events_scored).

    Calibration reads labels internally (the one sanctioned touch); fusion + aggregation do not.
    """
    scored_events = add_raw_risk(detections)
    scored_events["p_event"] = calibrate_events(scored_events)
    incidents_scored = aggregate_incidents(incidents, scored_events)
    events_scored = scored_events[["record_id", "raw_risk", "p_event"]].copy()
    return incidents_scored, events_scored


def _read(source, what: str, builder_hint: str) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        return source.copy()
    path = pathlib.Path(source)
    if not path.exists():
        raise FileNotFoundError(f"{what} not found at {path}; run `{builder_hint}` first")
    return pd.read_parquet(path)


def run_fusion(detections: pd.DataFrame | pathlib.Path | str = DEFAULT_DETECTIONS,
               incidents: pd.DataFrame | pathlib.Path | str = DEFAULT_INCIDENTS,
               out_path: Optional[pathlib.Path | str] = DEFAULT_OUT,
               events_out: Optional[pathlib.Path | str] = DEFAULT_EVENTS_OUT) -> pd.DataFrame:
    """Run fusion. Sources are DataFrames or Parquet paths. Writes incidents_scored.parquet (primary)
    and events_scored.parquet when paths are given; returns the scored incidents df."""
    det = _read(detections, "detections table", "python -m modules.detection.build")
    inc = _read(incidents, "incidents table", "python -m modules.correlation.build")

    incidents_scored, events_scored = fuse(det, inc)

    if out_path is not None:
        out_path = pathlib.Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        incidents_scored.to_parquet(out_path, engine="pyarrow", index=False)
    if events_out is not None:
        events_out = pathlib.Path(events_out)
        events_out.parent.mkdir(parents=True, exist_ok=True)
        events_scored.to_parquet(events_out, engine="pyarrow", index=False)
    return incidents_scored
