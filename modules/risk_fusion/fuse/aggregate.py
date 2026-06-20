"""Aggregate per-event calibrated scores into incident-level risk (design doc §9) — LABEL-FREE.

Each incident's score is a max+mean blend of its member events' `p_event`
(`MAX_MEAN_BLEND*max + (1-blend)*mean`) — the max lets one decisive event drive the incident while
the mean dampens noise. The tripwire `severity_floor` then forces a minimum score (`FLOOR_THRESHOLDS`),
and `risk_score` is banded and ranked into the analyst queue.

Evidence columns (`max_exposure_window_s`, `max_privilege_level`, `max_novelty`, `any_privileged`,
`mean_p_event`) are surfaced for the LLM triage bundle and the dashboard.
"""
from __future__ import annotations

import pandas as pd

from modules.risk_fusion.fuse import BAND_THRESHOLDS, FLOOR_THRESHOLDS, MAX_MEAN_BLEND, SCORED_COLS

# per-member columns pulled from the scored detections table for aggregation.
_EVIDENCE = ["p_event", "privileged", "exposure_window_s", "privilege_level", "principal_novelty"]


def _band(score: float) -> str:
    for name, threshold in BAND_THRESHOLDS:
        if score >= threshold:
            return name
    return BAND_THRESHOLDS[-1][0]


def aggregate_incidents(incidents: pd.DataFrame, scored_events: pd.DataFrame) -> pd.DataFrame:
    """incidents (Stage-3 schema) + per-event scores -> incidents + `SCORED_COLS`.

    `scored_events` must carry `record_id`, `raw_risk`, `p_event`, and the §5 evidence columns.
    """
    out = incidents.copy()
    lookup = scored_events.set_index("record_id")

    # explode members -> one row per (incident, member record), then join evidence.
    members = out[["incident_id", "member_record_ids"]].explode("member_record_ids")
    members = members.rename(columns={"member_record_ids": "record_id"})
    members = members.join(lookup[_EVIDENCE], on="record_id")

    grp = members.groupby("incident_id")
    agg = pd.DataFrame({
        "_p_max": grp["p_event"].max(),
        "mean_p_event": grp["p_event"].mean(),
        "max_exposure_window_s": grp["exposure_window_s"].max(),
        "max_privilege_level": grp["privilege_level"].max(),
        "max_novelty": grp["principal_novelty"].max(),
        "any_privileged": grp["privileged"].any(),
    })
    agg["risk_score"] = MAX_MEAN_BLEND * agg["_p_max"] + (1.0 - MAX_MEAN_BLEND) * agg["mean_p_event"]

    out = out.join(agg, on="incident_id")

    # tripwire severity floor forces a minimum score (HIGH today; CRITICAL forward-compatible).
    floor = out["severity_floor"].map(FLOOR_THRESHOLDS).fillna(0.0)
    out["risk_score"] = pd.concat([out["risk_score"], floor], axis=1).max(axis=1)

    out["risk_band"] = out["risk_score"].apply(_band)
    # rank: highest score first; ties broken by incident_id for determinism.
    order = out.sort_values(["risk_score", "incident_id"], ascending=[False, True])
    out["risk_rank"] = pd.Series(range(1, len(order) + 1), index=order.index)

    out = out.drop(columns=["_p_max"])
    return out[list(incidents.columns) + SCORED_COLS]
