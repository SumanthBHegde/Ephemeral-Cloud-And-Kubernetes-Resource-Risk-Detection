"""Edge definitions for Stage 3 entity graph — inverted from design §8.

**Design §8 specifies:** entity multigraph (principals/sessions/resources as nodes, events as edges).
**We implement:** event multigraph (events as nodes, shared entities as time-gated edges).

**Why the inversion:** design §8's entity model cannot enforce the identity+namespace+time envelope
(§18) because nodes have no temporal scope. One service account (`replicaset-controller`) would
produce one timeless principal node, and all autoscaler bursts across all namespaces and all time
would chain into one mega-incident. The time envelope can only be enforced *at edge-creation time*
— so edges, not nodes, must carry the temporal gate. The event-node model lets us enforce
`cluster_only_if(same_entity AND within_time_window AND same_namespace)` directly in the graph
construction, making the envelope a structural property instead of a wish.

**Output equivalence:** the connected-component result is functionally identical to the §8 entity
model; the incident artifact still surffaces the entity view (`principal_ids`, `namespaces`,
`resource_ids`, `edge_types`).

Each `EdgeSpec` links events that share an exact value on `group_cols`, optionally constrained to
a time window (`window_s`); `None` window = ungated (used only for keys that are near-unique per
real event, so they cannot chain unrelated activity).

The edge rules are grounded in the actual linkage values present in `detections.parquet`:
  - same_principal     one identity's activity — gated by W *and* namespace (web/prod bursts stay
                       separate; cloud events have no namespace so group on identity alone).
  - same_session       `session_name` — the ONLY link from INC-C's IdP login to its AssumeRole.
  - external_session   IdP-internal `externalSessionId`.
  - shared_event       `sharedEventID` — one API call fanned across services (AssumeRole→GetObject);
                       a UUID, so safe to leave ungated.
  - same_resource      same resource touched by the same identity — bridges INC-A's RunInstances→
                       TerminateInstances on one instance id (a 91-min gap), so the window is wide
                       (2h) but still bounded to avoid merging across days.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import pandas as pd

# --- envelope tunables (design doc §18: the knob that prevents over-merging) ---
TIME_WINDOW_S = 1800        # 30 min — weak-key (identity/session) merge window
RESOURCE_WINDOW_S = 7200    # 2 h    — same-resource+identity bridge (covers INC-A create→terminate)

# sentinel so cloud events (namespace == None) still group by identity alone.
_CLOUD_NS = "__cloud__"


@dataclass(frozen=True)
class EdgeSpec:
    etype: str
    group_cols: Sequence[str]   # events sharing exact values on ALL of these are linkable
    window_s: Optional[int]     # None = ungated; else max gap between consecutive members


EDGE_SPECS: tuple[EdgeSpec, ...] = (
    EdgeSpec("same_principal", ("principal_id", "ns_part"), TIME_WINDOW_S),
    EdgeSpec("same_session", ("session_name",), TIME_WINDOW_S),
    EdgeSpec("external_session", ("external_session_id",), TIME_WINDOW_S),
    EdgeSpec("shared_event", ("shared_event_id",), None),
    EdgeSpec("same_resource", ("resource_id", "principal_id"), RESOURCE_WINDOW_S),
)

EDGE_TYPES: tuple[str, ...] = tuple(s.etype for s in EDGE_SPECS)


def add_partition_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add helper columns the edge specs reference (namespace partition for cloud events)."""
    df = df.copy()
    df["ns_part"] = df["namespace"].where(df["namespace"].notna(), _CLOUD_NS)
    return df


def time_cluster_ids(times: pd.Series, window_s: Optional[int]) -> pd.Series:
    """Sessionize a time-sorted series: a new cluster starts whenever the gap to the previous
    event exceeds `window_s`. `None` window => everything is one cluster (ungated)."""
    if window_s is None:
        return pd.Series(0, index=times.index)
    gap = times.diff().dt.total_seconds().fillna(0.0)
    return (gap > window_s).cumsum()
