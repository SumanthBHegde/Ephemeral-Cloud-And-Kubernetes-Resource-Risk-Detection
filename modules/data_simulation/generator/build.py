"""Stage Zero orchestrator: ground-truth-first telemetry generation.

Pipeline: load config -> build campaigns (canonical incidents, risky scenarios with
benign twins, legit noise, routine topup) -> lay on the timeline -> render to authentic
schemas -> write JSONL + label sidecar + data dictionary.

Run:  python -m modules.data_simulation.generator.build  [--config PATH] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter

import yaml

# allow `python modules/data_simulation/generator/build.py` as well as `-m`
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from modules.data_simulation.generator import timeline  # noqa: E402
from modules.data_simulation.generator.context import SimContext, build_context  # noqa: E402
from modules.data_simulation.generator.data_dictionary import write_data_dictionary  # noqa: E402
from modules.data_simulation.generator.labels import build_labels  # noqa: E402
from modules.data_simulation.generator.model import (  # noqa: E402
    ALL_SOURCES, SCN_LEGIT_AUTOSCALE, SCN_LEGIT_CICD, SRC_CLOUDTRAIL, SRC_IDP, SRC_K8S,
    Campaign,
)
from modules.data_simulation.generator.schemas.render import render_event  # noqa: E402
from modules.data_simulation.generator.scenarios import (  # noqa: E402
    canonical, crypto_burst, identity_anomaly, legit_autoscale, legit_cicd,
    public_exposure, routine,
)

PKG_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = PKG_ROOT / "config" / "simulation.yaml"


def load_config(path: str | None = None) -> dict:
    p = pathlib.Path(path) if path else DEFAULT_CONFIG
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _count(campaigns: list[Campaign], key) -> Counter:
    c: Counter = Counter()
    for camp in campaigns:
        for ev in camp.events:
            c[key(ev)] += 1
    return c


def generate_all(ctx: SimContext, cfg: dict) -> list[Campaign]:
    total = sum(cfg["volumes"].values())
    mix = cfg["anomaly_mix"]
    campaigns: list[Campaign] = []

    if cfg.get("canonical_incidents", True):
        campaigns += canonical.all_incidents(ctx)

    # risky scenarios (each emits its benign look-alike twin too)
    campaigns += crypto_burst.generate(ctx, int(mix["crypto_burst"] * total))
    campaigns += public_exposure.generate(ctx, int(mix["public_exposure"] * total))
    campaigns += identity_anomaly.generate(ctx, int(mix["identity_anomaly"] * total))

    # legit noise, discounting the twins already produced above
    made = _count(campaigns, lambda e: e.scenario_type)
    auto_target = int(mix["legit_autoscale"] * total) - made.get(SCN_LEGIT_AUTOSCALE, 0)
    if auto_target > 0:
        campaigns += legit_autoscale.generate(ctx, auto_target)
    cicd_target = int(mix["legit_cicd"] * total) - made.get(SCN_LEGIT_CICD, 0)
    if cicd_target > 0:
        campaigns += legit_cicd.generate(ctx, cicd_target)

    # routine topup to reach each source's volume target
    by_src = _count(campaigns, lambda e: e.source)
    remaining = {s: max(0, cfg["volumes"][s] - by_src.get(s, 0)) for s in cfg["volumes"]}
    campaigns += routine.fill(ctx, remaining)
    return campaigns


def write_jsonl(path: pathlib.Path, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")


def _print_summary(cfg: dict, events, records) -> None:
    total = len(events)
    scn = Counter(e.scenario_type for e in events)
    risky = sum(1 for e in events if e.is_risky)
    inc = Counter(e.true_incident_id for e in events if e.true_incident_id)
    print(f"Generated {total} events "
          f"({len(records[SRC_CLOUDTRAIL])} cloudtrail, "
          f"{len(records[SRC_K8S])} k8s_audit, {len(records[SRC_IDP])} idp_session)")
    print(f"Risky: {risky} ({risky / total:.1%})")
    print("Anomaly mix (realized vs target):")
    for k, target in cfg["anomaly_mix"].items():
        print(f"  {k:18s} {scn.get(k, 0):5d}  {scn.get(k, 0) / total:6.2%}  (target {target:.2%})")
    print("Canonical incidents:", {i: inc.get(i, 0) for i in ("INC-A", "INC-B", "INC-C", "INC-D")})


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Stage Zero telemetry generator")
    ap.add_argument("--config", default=None, help="path to simulation.yaml")
    ap.add_argument("--out", default=None, help="output dir override")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    ctx = build_context(cfg)
    campaigns = generate_all(ctx, cfg)
    events = timeline.assign(ctx, campaigns)

    records = {s: [] for s in ALL_SOURCES}
    for ev in events:
        rec, _ = render_event(ev, ctx)
        records[ev.source].append(rec)
    labels = build_labels(events)

    out_dir = pathlib.Path(args.out) if args.out else (REPO_ROOT / cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "cloudtrail.jsonl", records[SRC_CLOUDTRAIL])
    write_jsonl(out_dir / "k8s_audit.jsonl", records[SRC_K8S])
    write_jsonl(out_dir / "idp_session.jsonl", records[SRC_IDP])
    write_jsonl(out_dir / "labels.jsonl", labels)
    write_data_dictionary(out_dir / "data_dictionary.md", cfg, events, records)

    _print_summary(cfg, events, records)
    print(f"Wrote artifacts to {out_dir}")


if __name__ == "__main__":
    main()
