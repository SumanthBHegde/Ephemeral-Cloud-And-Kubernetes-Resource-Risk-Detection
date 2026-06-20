"""CLI entrypoint for Stage 1.

    python -m modules.ingest_enrich.build                 # data/raw -> data/processed/events_enriched.parquet
    python -m modules.ingest_enrich.build --raw DIR --out FILE
"""
from __future__ import annotations

import argparse
import pathlib

from modules.ingest_enrich.pipeline import DEFAULT_OUT, DEFAULT_RAW, build_enriched


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Stage 1 ingest + enrich")
    ap.add_argument("--raw", default=str(DEFAULT_RAW), help="dir with the Stage-Zero JSONL")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output Parquet path")
    ap.add_argument("--config", default=None, help="path to simulation.yaml (cohort defs)")
    args = ap.parse_args(argv)

    df = build_enriched(args.raw, args.out, args.config)

    cohort_mix = df["cohort"].value_counts().to_dict()
    print(f"Enriched {len(df)} events from {args.raw}")
    print(f"  sources: {df['source'].value_counts().to_dict()}")
    print(f"  cohorts: {cohort_mix}")
    print(f"  features: burst_rate[max={df['burst_rate'].max()}], "
          f"off_hours={int(df['off_hours_flag'].sum())}, "
          f"novel_principals={int(df['is_novel_principal'].sum())}")
    print(f"Wrote {pathlib.Path(args.out).resolve()}")


if __name__ == "__main__":
    main()
