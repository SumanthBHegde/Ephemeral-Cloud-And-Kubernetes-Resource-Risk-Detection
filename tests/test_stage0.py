"""Stage Zero regression tests: determinism, mix, replay ordering, canonical incidents.

The determinism test is the important one -- a fixed seed must reproduce the dataset
byte for byte, otherwise no downstream metric is reproducible.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from modules.data_simulation.generator import timeline
from modules.data_simulation.generator.build import generate_all, load_config
from modules.data_simulation.generator.context import build_context
from modules.data_simulation.generator.labels import build_labels
from modules.data_simulation.generator.schemas.render import render_event
from modules.data_simulation.replay.stream import replay_events


def _build(cfg):
    ctx = build_context(cfg)
    campaigns = generate_all(ctx, cfg)
    events = timeline.assign(ctx, campaigns)
    records = []
    for ev in events:
        rec, _ = render_event(ev, ctx)
        records.append(rec)
    return events, records


def _digest(records, n=500):
    h = hashlib.sha256()
    for rec in records[:n]:
        h.update(json.dumps(rec, sort_keys=True, ensure_ascii=False).encode())
    return h.hexdigest()


def test_deterministic_same_seed():
    cfg = load_config()
    _, recs1 = _build(cfg)
    _, recs2 = _build(cfg)
    assert len(recs1) == len(recs2)
    assert _digest(recs1) == _digest(recs2)


def test_seed_changes_output():
    cfg = load_config()
    _, recs1 = _build(cfg)
    cfg2 = dict(cfg, seed=cfg["seed"] + 1)
    _, recs2 = _build(cfg2)
    assert _digest(recs1) != _digest(recs2)


def test_anomaly_mix_within_tolerance():
    cfg = load_config()
    events, _ = _build(cfg)
    total = len(events)
    tol = cfg["tolerance"]
    counts = {}
    for ev in events:
        counts[ev.scenario_type] = counts.get(ev.scenario_type, 0) + 1
    for scenario, target in cfg["anomaly_mix"].items():
        realized = counts.get(scenario, 0) / total
        assert abs(realized - target) <= tol, (scenario, realized, target)


def test_canonical_incidents_present():
    cfg = load_config()
    events, _ = _build(cfg)
    incidents = {ev.true_incident_id for ev in events if ev.true_incident_id}
    assert {"INC-A", "INC-B", "INC-C", "INC-D"} <= incidents


def test_labels_join_one_to_one():
    cfg = load_config()
    events, records = _build(cfg)
    labels = build_labels(events)
    rec_ids = {r.get("eventID") or r.get("auditID") or r.get("uuid") for r in records}
    label_ids = {row["record_id"] for row in labels}
    assert len(labels) == len(records)
    assert rec_ids == label_ids


def test_replay_is_time_ordered(tmp_path):
    """Build a dataset to tmp, then confirm the replay stream is globally time-ordered."""
    from modules.data_simulation.generator.build import main as build_main
    build_main(["--out", str(tmp_path)])
    times = [ev["_event_ts"] if "_event_ts" in ev else
             (ev.get("eventTime") or ev.get("requestReceivedTimestamp") or ev.get("published"))
             for ev in replay_events(tmp_path, speed=0, limit=2000)]
    # normalize to comparable strings via fromisoformat
    from datetime import timezone
    from datetime import datetime as dt
    parsed = [dt.fromisoformat(t.replace("Z", "+00:00")).astimezone(timezone.utc) for t in times]
    assert parsed == sorted(parsed)
