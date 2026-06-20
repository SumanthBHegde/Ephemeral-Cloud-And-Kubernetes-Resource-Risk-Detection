"""Place campaigns on the multi-day wall-clock and resolve absolute event times.

Each campaign gets an anchor (fixed for canonical incidents; otherwise drawn from a
diurnal distribution matching its timing hint). Every event's absolute timestamp is
anchor + its intra-campaign rel_offset, so bursts stay seconds-apart while landing at
realistic times of day (business hours, off-hours, or diurnal-weighted).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from modules.data_simulation.generator.context import SimContext
from modules.data_simulation.generator.model import (
    TIMING_BUSINESS, TIMING_OFF_HOURS, Campaign, Event,
)

# 24-hour weight profiles (index = UTC hour)
_BUSINESS = [1, 1, 1, 1, 1, 1, 2, 4, 8, 10, 10, 9, 8, 8, 9, 9, 8, 6, 4, 2, 1, 1, 1, 1]
_DIURNAL = [2, 1, 1, 1, 1, 2, 3, 5, 7, 8, 9, 9, 9, 9, 9, 8, 7, 6, 5, 4, 3, 3, 2, 2]
_OFF_HOURS = [0, 1, 2, 3, 4, 5, 22, 23]


def _pick_hour(ctx: SimContext, timing: str) -> int:
    if timing == TIMING_OFF_HOURS:
        return ctx.rng.choice(_OFF_HOURS)
    weights = _BUSINESS if timing == TIMING_BUSINESS else _DIURNAL
    return ctx.rng.choices(range(24), weights=weights)[0]


def _anchor_for(ctx: SimContext, camp: Campaign) -> datetime:
    if camp.fixed_anchor is not None:
        return camp.fixed_anchor
    day = ctx.rng.randrange(ctx.span_days)
    hour = _pick_hour(ctx, camp.timing)
    return ctx.span_start + timedelta(
        days=day, hours=hour, minutes=ctx.rng.randrange(60), seconds=ctx.rng.randrange(60),
    )


def assign(ctx: SimContext, campaigns: list[Campaign]) -> list[Event]:
    """Set anchors + absolute timestamps; return all events sorted by time."""
    for camp in campaigns:
        camp.anchor = _anchor_for(ctx, camp)
        for ev in camp.events:
            ev.timestamp = camp.anchor + ev.rel_offset
    events = [ev for camp in campaigns for ev in camp.events]
    events.sort(key=lambda e: (e.timestamp, e.source, e.action))
    return events
