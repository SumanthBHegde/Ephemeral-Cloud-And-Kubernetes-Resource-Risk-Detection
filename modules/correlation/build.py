"""CLI entrypoint for Stage 3.

    python -m modules.correlation.build                 # detections.parquet -> incidents.parquet (+ map)
    python -m modules.correlation.build --in FILE --out FILE --map FILE
"""
from __future__ import annotations

import argparse
import pathlib

from modules.correlation.pipeline import (
    DEFAULT_IN,
    DEFAULT_MAP_OUT,
    DEFAULT_OUT,
    run_correlation,
)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Stage 3 graph correlation")
    ap.add_argument("--in", dest="in_path", default=str(DEFAULT_IN),
                    help="detections Parquet from Stage 2")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output incidents Parquet path")
    ap.add_argument("--map", dest="map_out", default=str(DEFAULT_MAP_OUT),
                    help="output per-event incident-map Parquet path")
    args = ap.parse_args(argv)

    incidents = run_correlation(args.in_path, args.out, args.map_out)

    n_inc = len(incidents)
    members = int(incidents["event_count"].sum())
    seeds = int(incidents["n_flagged"].sum())
    bridges = int(incidents["n_bridge"].sum())
    high = int((incidents["severity_floor"] == "HIGH").sum())
    multi = int((incidents["event_count"] > 1).sum())
    cross = int(((incidents["source_cloudtrail_count"] > 0).astype(int)
                 + (incidents["source_k8s_count"] > 0).astype(int)
                 + (incidents["source_idp_count"] > 0).astype(int) > 1).sum())
    print(f"Correlation over {seeds} flagged events:")
    print(f"  incidents:          {n_inc}  (alert reduction {seeds} flagged -> {n_inc} incidents)")
    print(f"  member events:      {members}  ({seeds} flagged + {bridges} bridge)")
    print(f"  multi-event:        {multi}   high-severity: {high}   cross-source: {cross}")
    print(f"Wrote {pathlib.Path(args.out).resolve()}")
    print(f"Wrote {pathlib.Path(args.map_out).resolve()}")


if __name__ == "__main__":
    main()
