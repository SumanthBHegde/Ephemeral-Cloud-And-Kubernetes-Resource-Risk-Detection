"""Per-incident triage cache (design doc §10: "cache responses so the live demo never depends on a
network call").

One JSON file per incident at `data/processed/triage_cache/INC-XXXX.json`.

Two reuse modes:
- **Existence-based (default in the pipeline):** if a file already exists for the incident, reuse it
  and never re-call the LLM. This is the cost guard — a rerun never re-spends the paid API on an
  incident already triaged. `--force-refresh` overrides it to regenerate.
- **Hash-checked (`get`):** reuse only if the stored `evidence_hash` matches the current bundle's
  hash; the `evidence_hash` is always stored so staleness (data changed since triage) is detectable.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Optional


def evidence_hash(bundle: dict) -> str:
    """Order-stable short hash of an evidence bundle.

    `sort_keys=True` is essential: build_evidence_bundle may add fields conditionally, and without a
    canonical key order the same data could hash differently and miss the cache.
    """
    blob = json.dumps(bundle, sort_keys=True, default=str).encode("utf-8")
    return hashlib.md5(blob).hexdigest()[:8]


def _path(cache_dir: pathlib.Path | str, incident_id: str) -> pathlib.Path:
    return pathlib.Path(cache_dir) / f"{incident_id}.json"


def read(cache_dir: pathlib.Path | str, incident_id: str) -> Optional[dict]:
    """Return the cached triage record for an incident (no hash check), or None if absent/unreadable.

    This is the existence-based reuse path: if the file is here, hand it back as-is.
    """
    p = _path(cache_dir, incident_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def get(cache_dir: pathlib.Path | str, incident_id: str, ev_hash: str) -> Optional[dict]:
    """Return the cached triage record if present AND its evidence hash matches; else None."""
    rec = read(cache_dir, incident_id)
    if rec is None or rec.get("evidence_hash") != ev_hash:
        return None
    return rec


def put(cache_dir: pathlib.Path | str, incident_id: str, ev_hash: str, record: dict) -> None:
    """Persist a triage record (the 7 fields + provenance) under its evidence hash."""
    cache_dir = pathlib.Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = dict(record)
    payload["incident_id"] = incident_id
    payload["evidence_hash"] = ev_hash
    _path(cache_dir, incident_id).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
