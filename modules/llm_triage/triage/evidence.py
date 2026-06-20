"""Build the per-incident evidence bundle the triage agent reasons over (design doc §10).

The central thesis (CLAUDE.md): a legit autoscaler burst and a crypto hijack are identical at the
event level — the separating signal is *context*. So the bundle pairs incident-level aggregates
(score, exposure, novelty, source mix, graph edge types) with the most anomalous member events and
their confusability fields (cohort, tag completeness, controller_owner, exposure, off-hours). The LLM
gets enough context to disambiguate without us shipping every member row.

Everything in the bundle is plain JSON-serializable types so it hashes stably for the cache key.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# how many member events to include, most-anomalous-first. A named constant: the implementer choice
# the plan calls out. 5 keeps prompts cheap while covering the decisive events.
MAX_MEMBER_EVENTS = 5

# incident-row fields surfaced verbatim (all present in incidents_scored at runtime — LABEL-FREE).
_INCIDENT_SCALARS = [
    "risk_score", "risk_band", "risk_rank", "severity_floor", "event_count",
    "n_flagged", "n_bridge", "window_s", "tripwire_hits", "max_ensemble_score",
    "mean_p_event", "max_exposure_window_s", "max_privilege_level", "max_novelty",
    "any_privileged", "source_cloudtrail_count", "source_k8s_count", "source_idp_count",
]
_INCIDENT_LISTS = ["edge_types", "principal_ids", "namespaces", "resource_ids"]

# per-member confusability fields pulled from the enriched table.
_MEMBER_FIELDS = [
    "source", "action", "cohort", "principal_id", "namespace", "controller_owner",
    "tag_completeness", "privileged", "public_exposure_flag", "exposed_open",
    "off_hours_flag", "is_novel_principal", "principal_novelty", "privilege_level",
]


def _py(val: Any) -> Any:
    """Coerce a pandas/numpy scalar or array to a plain JSON-serializable Python value."""
    if val is None:
        return None
    if isinstance(val, (list, tuple)):
        return [_py(v) for v in val]
    if isinstance(val, np.ndarray):           # list columns come back as ndarray from parquet
        return [_py(v) for v in val.tolist()]
    if isinstance(val, pd.Timestamp):
        return val.isoformat()
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    if isinstance(val, np.generic):           # numpy scalar -> python scalar
        return val.item()
    # pd.isna only on true scalars (arrays handled above); guard against non-scalars defensively.
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    return val


def build_evidence_bundle(
    incident_row: pd.Series,
    enriched: pd.DataFrame,
    events_scored: pd.DataFrame,
) -> dict:
    """One incident row + the enriched + scored event tables -> a compact, JSON-serializable bundle.

    Member events are ranked by calibrated `p_event` (the runtime per-event anomaly signal; Stage 4
    wrote events_scored "for dashboard + LLM") and capped at MAX_MEMBER_EVENTS.
    """
    bundle: dict[str, Any] = {"incident_id": _py(incident_row["incident_id"])}
    for col in _INCIDENT_SCALARS:
        bundle[col] = _py(incident_row.get(col))
    for col in _INCIDENT_LISTS:
        bundle[col] = _py(incident_row.get(col))

    member_ids = _py(incident_row.get("member_record_ids")) or []

    # rank members by p_event desc, keep the top-N, then pull their confusability fields.
    p_lookup = events_scored.set_index("record_id")["p_event"]
    ranked = sorted(
        member_ids,
        key=lambda rid: float(p_lookup.get(rid, 0.0)),
        reverse=True,
    )[:MAX_MEMBER_EVENTS]

    enr = enriched.set_index("record_id")
    members: list[dict] = []
    for rid in ranked:
        if rid not in enr.index:
            continue
        row = enr.loc[rid]
        rec = {"record_id": rid, "p_event": round(float(p_lookup.get(rid, 0.0)), 4),
               "event_time": _py(row.get("event_time"))}
        for f in _MEMBER_FIELDS:
            rec[f] = _py(row.get(f))
        members.append(rec)
    bundle["member_events"] = members

    return bundle
