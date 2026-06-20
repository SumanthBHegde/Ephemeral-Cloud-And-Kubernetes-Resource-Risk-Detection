"""Stage 3 entity graph: event-node MultiGraph + connected-component incidents."""
from __future__ import annotations

from modules.correlation.graph.build_graph import build_graph
from modules.correlation.graph.entities import (
    EDGE_SPECS,
    EDGE_TYPES,
    RESOURCE_WINDOW_S,
    TIME_WINDOW_S,
)
from modules.correlation.graph.incidents import INCIDENT_COLS, extract_incidents

__all__ = [
    "build_graph",
    "extract_incidents",
    "INCIDENT_COLS",
    "EDGE_SPECS",
    "EDGE_TYPES",
    "TIME_WINDOW_S",
    "RESOURCE_WINDOW_S",
]
