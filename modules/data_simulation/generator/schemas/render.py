"""Dispatch a semantic Event to the renderer for its source."""
from __future__ import annotations

from modules.data_simulation.generator.context import SimContext
from modules.data_simulation.generator.model import (
    SRC_CLOUDTRAIL, SRC_IDP, SRC_K8S, Event,
)
from modules.data_simulation.generator.schemas import cloudtrail, idp_session, k8s_audit

_BY_SOURCE = {
    SRC_CLOUDTRAIL: cloudtrail.render,
    SRC_K8S: k8s_audit.render,
    SRC_IDP: idp_session.render,
}


def render_event(ev: Event, ctx: SimContext) -> tuple[dict, str]:
    """Return (authentic record dict, record_id). Also sets ev.record_id."""
    record, record_id = _BY_SOURCE[ev.source](ev, ctx)
    ev.record_id = record_id
    return record, record_id
