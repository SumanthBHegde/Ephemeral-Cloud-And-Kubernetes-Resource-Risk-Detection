"""Stage 3 orchestrator: detection flags -> incidents (Parquet).

    run_correlation()  read data/processed/detections.parquet (or accept a DataFrame), build the
                       entity graph, collapse connected components into incidents, and (optionally)
                       write data/processed/incidents.parquet + the per-event incident map.

Clustering only — risk *scoring* is the next stage (after clustering, per the non-negotiable
ordering catch §3). Seeds are `predicted_risky` events; the graph expands one hop to pull in
directly-linked bridge events (see graph/build_graph.py).
"""
from __future__ import annotations

import pathlib
from typing import Optional

import pandas as pd

from modules.correlation.graph import INCIDENT_COLS, build_graph, extract_incidents

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_IN = REPO_ROOT / "data" / "processed" / "detections.parquet"
DEFAULT_OUT = REPO_ROOT / "data" / "processed" / "incidents.parquet"
DEFAULT_MAP_OUT = REPO_ROOT / "data" / "processed" / "event_incidents.parquet"


def correlate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pure in-memory correlation: detections df -> (incidents, event->incident map).

    Adds the boolean `is_seed = predicted_risky` the graph builder expects, builds the graph, and
    extracts incidents. Does not touch disk."""
    df = df.copy()
    df["is_seed"] = df["predicted_risky"].astype(bool)
    g = build_graph(df)
    return extract_incidents(g, df)


def run_correlation(source: pd.DataFrame | pathlib.Path | str = DEFAULT_IN,
                    out_path: Optional[pathlib.Path | str] = DEFAULT_OUT,
                    map_out: Optional[pathlib.Path | str] = DEFAULT_MAP_OUT) -> pd.DataFrame:
    """Run correlation. `source` is a detections df or a Parquet path. Writes incidents.parquet
    (primary) and the per-event incident map when paths are given; returns the incidents df."""
    if isinstance(source, pd.DataFrame):
        df = source.copy()
    else:
        path = pathlib.Path(source)
        if not path.exists():
            raise FileNotFoundError(
                f"detections table not found at {path}; run "
                f"`python -m modules.detection.build` first")
        df = pd.read_parquet(path)

    incidents, event_map = correlate(df)

    if out_path is not None:
        out_path = pathlib.Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        incidents.to_parquet(out_path, engine="pyarrow", index=False)
    if map_out is not None:
        map_out = pathlib.Path(map_out)
        map_out.parent.mkdir(parents=True, exist_ok=True)
        event_map.to_parquet(map_out, engine="pyarrow", index=False)
    return incidents
