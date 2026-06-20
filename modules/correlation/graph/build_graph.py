"""Build the Stage 3 graph: events as nodes, shared entities as time-gated edges.

Inverts design §8's entity-node model (see entities.py docstring for the reasoning). This
event-node graph structurally enforces the identity+namespace+time envelope: edges exist only
between events within a time window AND in the same namespace (cloud events group by identity).

`build_graph(df)` returns a NetworkX `MultiGraph` whose nodes are event `record_id`s and whose
edges are typed entity links carrying the etype label (see `entities.EDGE_SPECS`). Two enforcement
rules are non-negotiable:

1. **Seed-originated edges only (1-hop, enforced at build time).** Seeds are `predicted_risky`
   events. Within each edge key, we keep only clusters that contain >=1 seed and star-connect
   their members from a seed; clusters with no seed are dropped entirely. So an unflagged
   "bridge" event only enters the graph when a seed reaches it, and it never pulls in *its* other
   neighbours (those live in a different key-cluster that has no seed unless another seed is
   there too). This is exactly seed -> bridge (1 hop), and the cross-source case seed -> bridge <-
   seed, while forbidding seed -> bridge -> bridge. The invariant **every edge has >=1 seed
   endpoint** holds. Connected-components alone could not make this distinction, which is why it
   is enforced here, not at component time.

2. **Isolated seeds are still incidents.** Every seed is added as a node up front, so a flagged
   event with no links becomes its own size-1 incident rather than vanishing.
"""
from __future__ import annotations

import networkx as nx
import pandas as pd

from modules.correlation.graph.entities import (
    EDGE_SPECS,
    EdgeSpec,
    add_partition_columns,
    time_cluster_ids,
)


def _add_spec_edges(g: nx.MultiGraph, df: pd.DataFrame, spec: EdgeSpec) -> None:
    """Add all edges for one EdgeSpec: group by its key, sessionize by time, star-connect every
    seed-containing cluster (rep = first seed in the cluster)."""
    cols = list(spec.group_cols)
    work = df.dropna(subset=cols)
    if work.empty:
        return

    for _, grp in work.groupby(cols, sort=False):
        if not grp["is_seed"].any():
            continue
        grp = grp.sort_values("event_time")
        clusters = time_cluster_ids(grp["event_time"], spec.window_s)
        for _, cluster in grp.groupby(clusters, sort=False):
            if not cluster["is_seed"].any():
                continue
            rids = cluster["record_id"].tolist()
            seeds = cluster.loc[cluster["is_seed"], "record_id"].tolist()
            rep = seeds[0]
            for other in rids:
                if other != rep:
                    g.add_edge(rep, other, etype=spec.etype)


def build_graph(df: pd.DataFrame) -> nx.MultiGraph:
    """Build the event graph. `df` must carry `record_id`, `event_time`, the linkage-key columns,
    and a boolean `is_seed` (= `predicted_risky`). A MultiGraph keeps one parallel edge per edge
    type so each incident can report the full set of link types in its component."""
    df = add_partition_columns(df)

    g = nx.MultiGraph()
    # every seed is a node, so isolated flagged events survive as size-1 incidents.
    g.add_nodes_from(df.loc[df["is_seed"], "record_id"].tolist())

    for spec in EDGE_SPECS:
        _add_spec_edges(g, df, spec)
    return g
