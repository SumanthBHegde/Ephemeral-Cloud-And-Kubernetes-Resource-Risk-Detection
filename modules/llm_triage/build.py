"""CLI entrypoint for Stage 5.

    python -m modules.llm_triage.build                 # live gpt-4o-mini triage (needs OPENAI_API_KEY)
    python -m modules.llm_triage.build --no-llm        # offline: templated fallback only, no network
    python -m modules.llm_triage.build --bands CRITICAL # narrow the band filter
"""
from __future__ import annotations

import argparse
import pathlib

from modules.llm_triage.pipeline import (
    DEFAULT_CACHE_DIR,
    DEFAULT_ENRICHED,
    DEFAULT_EVENTS_SCORED,
    DEFAULT_INCIDENTS,
    DEFAULT_OUT,
    run_triage,
)
from modules.llm_triage.triage import BANDS_TO_TRIAGE


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Stage 5 LLM triage agent")
    ap.add_argument("--in", dest="in_path", default=str(DEFAULT_INCIDENTS),
                    help="scored-incidents Parquet from Stage 4")
    ap.add_argument("--enriched", default=str(DEFAULT_ENRICHED),
                    help="enriched-events Parquet from Stage 1")
    ap.add_argument("--events-scored", dest="events_scored", default=str(DEFAULT_EVENTS_SCORED),
                    help="per-event scored Parquet from Stage 4")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output triaged-incidents Parquet path")
    ap.add_argument("--cache-dir", dest="cache_dir", default=str(DEFAULT_CACHE_DIR),
                    help="per-incident triage JSON cache directory")
    ap.add_argument("--bands", default=",".join(BANDS_TO_TRIAGE),
                    help="comma-separated risk bands to triage (default CRITICAL,HIGH)")
    ap.add_argument("--no-llm", dest="use_llm", action="store_false",
                    help="skip the API; produce deterministic templated triage only")
    ap.add_argument("--force-refresh", dest="force_refresh", action="store_true",
                    help="ignore existing cache files and regenerate every incident (re-spends the API)")
    args = ap.parse_args(argv)

    bands = tuple(b.strip() for b in args.bands.split(",") if b.strip())
    triaged = run_triage(args.in_path, args.enriched, args.events_scored,
                         args.out, args.cache_dir, bands=bands, use_llm=args.use_llm,
                         force_refresh=args.force_refresh)

    n = len(triaged)
    src = triaged["triage_source"].value_counts()
    print(f"Triaged {n} incidents (bands: {', '.join(bands)}):")
    band_counts = triaged["risk_band"].value_counts()
    for band in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        if band in band_counts:
            print(f"  {band:<9} {int(band_counts[band])}")
    print("  provenance: " + "  ".join(f"{k}={int(v)}" for k, v in src.items()))
    print("  top 5 triaged incidents:")
    for _, r in triaged.head(5).iterrows():
        print(f"    #{int(r['risk_rank']):<3} {r['incident_id']}  {r['risk_band']:<8} "
              f"{r['likely_intent']}  mitre={list(r['mitre'])}")
    print(f"Wrote {pathlib.Path(args.out).resolve()}")
    print(f"Cache: {pathlib.Path(args.cache_dir).resolve()}")


if __name__ == "__main__":
    main()
