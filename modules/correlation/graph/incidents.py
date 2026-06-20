"""Connected components -> incident rows (design doc §8).

`extract_incidents(g, df)` walks the graph's connected components — each one is an incident — and
returns:
  - `incidents`: one row per incident (the `INCIDENT_COLS` schema, primary artifact for risk_fusion).
  - `event_map`: every input event's `record_id` -> `incident_id`, with `None` for the ~8k events
    that are neither seed nor bridge (risk_fusion's timeline + the dashboard inventory need them).

Incidents are numbered `INC-0001…` deterministically by (start_time, smallest record_id) so the
output is stable across runs. Ground-truth columns are never added here — that join lives in
`evaluate.py`.
"""
from __future__ import annotations

import networkx as nx
import pandas as pd

# the three event sources, mapped to the flat per-incident count columns.
_SOURCE_COUNT_COLS = {
    "cloudtrail": "source_cloudtrail_count",
    "k8s_audit": "source_k8s_count",
    "idp_session": "source_idp_count",
}

INCIDENT_COLS = [
    "incident_id",
    "member_record_ids",
    "event_count",
    "n_flagged",
    "n_bridge",
    "principal_ids",
    "namespaces",
    "resource_ids",
    "source_cloudtrail_count",
    "source_k8s_count",
    "source_idp_count",
    "edge_types",
    "start_time",
    "end_time",
    "window_s",
    "severity_floor",
    "max_ensemble_score",
    "tripwire_hits",
]


def _sorted_unique(series: pd.Series) -> list:
    return sorted(series.dropna().unique().tolist())


def _component_edge_types(g: nx.MultiGraph, members: list[str]) -> list[str]:
    sub = g.subgraph(members)
    return sorted({data["etype"] for _, _, data in sub.edges(data=True)})


def extract_incidents(g: nx.MultiGraph, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregate connected components into incident rows + a full event->incident map."""
    by_id = df.set_index("record_id")

    # build (sort_key, members) so numbering is deterministic.
    comps = []
    for comp in nx.connected_components(g):
        members = list(comp)
        start = by_id.loc[members, "event_time"].min()
        comps.append((start, min(members), members))
    comps.sort(key=lambda t: (t[0], t[1]))

    rows = []
    mapping: dict[str, str] = {}
    for i, (start, _, members) in enumerate(comps, start=1):
        iid = f"INC-{i:04d}"
        m = by_id.loc[members]
        for rid in members:
            mapping[rid] = iid

        src_counts = m["source"].value_counts()
        end = m["event_time"].max()
        n_flagged = int(m["is_seed"].sum())
        rows.append({
            "incident_id": iid,
            "member_record_ids": sorted(members),
            "event_count": len(members),
            "n_flagged": n_flagged,
            "n_bridge": len(members) - n_flagged,
            "principal_ids": _sorted_unique(m["principal_id"]),
            "namespaces": _sorted_unique(m["namespace"]),
            "resource_ids": _sorted_unique(m["resource_id"]),
            "source_cloudtrail_count": int(src_counts.get("cloudtrail", 0)),
            "source_k8s_count": int(src_counts.get("k8s_audit", 0)),
            "source_idp_count": int(src_counts.get("idp_session", 0)),
            "edge_types": _component_edge_types(g, members),
            "start_time": start,
            "end_time": end,
            "window_s": float((end - start).total_seconds()),
            "severity_floor": "HIGH" if (m["severity_floor"] == "HIGH").any() else "NONE",
            "max_ensemble_score": float(m["ensemble_score"].max()),
            "tripwire_hits": int(m["tripwire_hit"].sum()),
        })

    incidents = pd.DataFrame(rows, columns=INCIDENT_COLS)

    event_map = df[["record_id"]].copy()
    event_map["incident_id"] = event_map["record_id"].map(mapping)  # NaN/None for non-members
    return incidents, event_map
