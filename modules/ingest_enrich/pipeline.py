"""Stage 1 orchestrator: raw JSONL -> normalized + enriched event table (Parquet).

Two consumption modes (both produce the same unified rows):

  build_enriched()   batch path — read the three JSONL files directly, normalize, assign
                     cohorts, compute §5 features, return a DataFrame (and optionally write
                     data/processed/events_enriched.parquet). This is what detection reads.

  enrich_stream()    live path — wrap the Stage-Zero replay streamer so the dashboard can
                     normalize events one-by-one as they "arrive". Per-event normalization +
                     cohort only (windowed features need the batch view), matching the
                     score-after-clustering ordering: heavy features are a batch concern.

Labels stay in the sidecar — the enriched table carries `record_id` so evaluation can join
to labels.jsonl 1:1, but labels are never read into the runtime feature table.
"""
from __future__ import annotations

import json
import pathlib
from typing import Iterable, Iterator, Optional

import pandas as pd

from modules.data_simulation.generator.model import (
    SRC_CLOUDTRAIL, SRC_IDP, SRC_K8S,
)
from modules.ingest_enrich.enrich.cohorts import CohortResolver, assign_cohorts
from modules.ingest_enrich.enrich.features import add_features
from modules.ingest_enrich.normalize import UNIFIED_FIELDS
from modules.ingest_enrich.normalize.dispatch import normalize_record

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_RAW = REPO_ROOT / "data" / "raw"
DEFAULT_OUT = REPO_ROOT / "data" / "processed" / "events_enriched.parquet"

# (source, filename) — same trio the replay streamer reads
_SOURCES = [
    (SRC_CLOUDTRAIL, "cloudtrail.jsonl"),
    (SRC_K8S, "k8s_audit.jsonl"),
    (SRC_IDP, "idp_session.jsonl"),
]


def _read_raw(raw_dir: pathlib.Path) -> list[dict]:
    """Read + normalize every record from the three source files."""
    rows: list[dict] = []
    for src, fname in _SOURCES:
        path = raw_dir / fname
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(normalize_record(json.loads(line), source=src))
    return rows


def build_enriched(raw_dir: pathlib.Path | str = DEFAULT_RAW,
                   out_path: Optional[pathlib.Path | str] = DEFAULT_OUT,
                   config_path: str | None = None) -> pd.DataFrame:
    """Batch-normalize + enrich the raw dataset; write Parquet unless out_path is None."""
    rows = _read_raw(pathlib.Path(raw_dir))
    if not rows:
        raise FileNotFoundError(f"no source files found in {raw_dir}")

    assign_cohorts(rows, CohortResolver.from_config(config_path))

    df = pd.DataFrame(rows, columns=list(UNIFIED_FIELDS) + ["cohort"])
    # deterministic ordering: time, then source, then record_id (stable across runs)
    df = df.sort_values(["event_time", "source", "record_id"], kind="stable").reset_index(drop=True)
    df = add_features(df, config_path)

    if out_path is not None:
        out_path = pathlib.Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_path, engine="pyarrow", index=False)
    return df


def enrich_stream(events: Iterable[dict],
                  resolver: CohortResolver | None = None) -> Iterator[dict]:
    """Normalize + cohort-assign a live replay stream, event by event.

    `events` is the `{_source, _seq, ...record}` dicts yielded by
    `modules.data_simulation.replay.stream.replay_events`. Windowed features are NOT
    computed here (they need the batch view); the dashboard's live tile uses the batch
    Parquet for those and this stream for the as-it-arrives normalized view.
    """
    resolver = resolver or CohortResolver.from_config()
    for ev in events:
        row = normalize_record(ev)            # uses the _source envelope key
        row["cohort"] = resolver.resolve(row)
        row["_seq"] = ev.get("_seq")
        yield row
