"""CLI entrypoint for Stage 2.

    python -m modules.detection.build                 # enriched parquet -> data/processed/detections.parquet
    python -m modules.detection.build --in FILE --out FILE
"""
from __future__ import annotations

import argparse
import pathlib

from modules.detection.pipeline import DEFAULT_IN, DEFAULT_OUT, run_detection


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Stage 2 two-stage detection")
    ap.add_argument("--in", dest="in_path", default=str(DEFAULT_IN),
                    help="enriched Parquet from Stage 1")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output detections Parquet path")
    args = ap.parse_args(argv)

    df = run_detection(args.in_path, args.out)

    n = len(df)
    cand = int(df["is_candidate"].sum())
    trip = int(df["tripwire_hit"].sum())
    supp = int(df["is_suppressed"].sum())
    pred = int(df["predicted_risky"].sum())
    raw = int((df["is_candidate"] | df["tripwire_hit"]).sum())  # raw rule+ML flags
    print(f"Detection over {n} events:")
    print(f"  tripwire hits:     {trip}")
    print(f"  Stage-1 candidates:{cand}")
    print(f"  raw flags (trip|cand): {raw}")
    print(f"  suppressed (S2):   {supp}")
    if raw:
        reduction = (1 - pred / raw) * 100
        print(f"  predicted risky:   {pred}  "
              f"(alert reduction {raw} -> {pred}, {reduction:.0f}%)")
    else:
        print(f"  predicted risky:   {pred}")
    print(f"Wrote {pathlib.Path(args.out).resolve()}")


if __name__ == "__main__":
    main()
