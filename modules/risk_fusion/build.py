"""CLI entrypoint for Stage 4.

    python -m modules.risk_fusion.build      # detections + incidents -> incidents_scored.parquet (+ events_scored)
    python -m modules.risk_fusion.build --detections FILE --incidents FILE --out FILE --events-out FILE
"""
from __future__ import annotations

import argparse
import pathlib

from modules.risk_fusion.pipeline import (
    DEFAULT_DETECTIONS,
    DEFAULT_EVENTS_OUT,
    DEFAULT_INCIDENTS,
    DEFAULT_OUT,
    run_fusion,
)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Stage 4 risk fusion & calibration")
    ap.add_argument("--detections", default=str(DEFAULT_DETECTIONS),
                    help="detections Parquet from Stage 2")
    ap.add_argument("--incidents", default=str(DEFAULT_INCIDENTS),
                    help="incidents Parquet from Stage 3")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output scored-incidents Parquet path")
    ap.add_argument("--events-out", dest="events_out", default=str(DEFAULT_EVENTS_OUT),
                    help="output per-event scored Parquet path")
    args = ap.parse_args(argv)

    inc = run_fusion(args.detections, args.incidents, args.out, args.events_out)

    n = len(inc)
    bands = inc["risk_band"].value_counts()
    print(f"Risk fusion over {n} incidents:")
    for band in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        print(f"  {band:<9} {int(bands.get(band, 0))}")
    print(f"  risk_score  min={inc['risk_score'].min():.3f}  "
          f"max={inc['risk_score'].max():.3f}  mean={inc['risk_score'].mean():.3f}")
    top = inc.sort_values("risk_rank").head(5)
    print("  top 5 incidents:")
    for _, r in top.iterrows():
        print(f"    #{int(r['risk_rank']):<3} {r['incident_id']}  "
              f"{r['risk_band']:<8} score={r['risk_score']:.3f}  events={int(r['event_count'])}")
    print(f"Wrote {pathlib.Path(args.out).resolve()}")
    print(f"Wrote {pathlib.Path(args.events_out).resolve()}")


if __name__ == "__main__":
    main()
