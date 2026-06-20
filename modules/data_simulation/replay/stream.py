"""Real-time replay of the generated telemetry.

Merges the three JSONL source files into one time-ordered, source-interleaved stream
and emits it to stdout (one JSON line per event, with a small `_source`/`_seq` envelope
added so a downstream consumer knows which schema each line is). A speed multiplier maps
simulated inter-event gaps onto wall-clock sleeps so the pipeline can ingest "live".

Run:
    python modules/data_simulation/replay/stream.py --instant | head
    python modules/data_simulation/replay/stream.py --speed 60 --limit 50

Also importable:
    from modules.data_simulation.replay.stream import replay_events
    for ev in replay_events(speed=0):
        ...
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from modules.data_simulation.generator.model import SRC_CLOUDTRAIL, SRC_IDP, SRC_K8S  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_OUT = REPO_ROOT / "data" / "raw"

# (source, filename, timestamp field)
_SOURCES = [
    (SRC_CLOUDTRAIL, "cloudtrail.jsonl", "eventTime"),
    (SRC_K8S, "k8s_audit.jsonl", "requestReceivedTimestamp"),
    (SRC_IDP, "idp_session.jsonl", "published"),
]


def _parse_ts(value: str) -> datetime:
    """Parse both second- and millisecond-precision trailing-Z UTC timestamps."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _load(out_dir: pathlib.Path):
    items = []
    for src, fname, tfield in _SOURCES:
        path = out_dir / fname
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                items.append((_parse_ts(rec[tfield]), src, rec))
    items.sort(key=lambda x: (x[0], x[1]))
    return items


def replay_events(out_dir: pathlib.Path | str = DEFAULT_OUT, *, speed: float = 0.0,
                  start: datetime | None = None, until: datetime | None = None,
                  limit: int | None = None, max_gap: float = 2.0):
    """Yield time-ordered events as `{"_source","_seq", ...record}` dicts.

    speed: 0 = no sleeping (as fast as possible); N = N x real-time pacing.
    max_gap: cap (seconds) on any single inter-event sleep so demos stay snappy.
    """
    items = _load(pathlib.Path(out_dir))
    prev: datetime | None = None
    seq = 0
    for ts, src, rec in items:
        if start and ts < start:
            continue
        if until and ts > until:
            continue
        if speed and prev is not None:
            gap = (ts - prev).total_seconds() / speed
            if gap > 0:
                time.sleep(min(gap, max_gap))
        prev = ts
        yield {"_source": src, "_seq": seq, **rec}
        seq += 1
        if limit is not None and seq >= limit:
            return


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Replay Stage Zero telemetry to stdout")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="dir with the generated JSONL")
    ap.add_argument("--speed", type=float, default=0.0,
                    help="pacing multiplier (0=instant, 1=real-time, 60=60x)")
    ap.add_argument("--instant", action="store_true", help="alias for --speed 0")
    ap.add_argument("--start", default=None, help="ISO time: skip events before this")
    ap.add_argument("--until", default=None, help="ISO time: stop after this")
    ap.add_argument("--limit", type=int, default=None, help="max events to emit")
    ap.add_argument("--max-gap", type=float, default=2.0, help="cap on per-event sleep (s)")
    args = ap.parse_args(argv)

    speed = 0.0 if args.instant else args.speed
    start = _parse_ts(args.start) if args.start else None
    until = _parse_ts(args.until) if args.until else None

    try:
        for ev in replay_events(args.out, speed=speed, start=start, until=until,
                                limit=args.limit, max_gap=args.max_gap):
            sys.stdout.write(json.dumps(ev, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    except (BrokenPipeError, KeyboardInterrupt):
        try:
            sys.stdout.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
