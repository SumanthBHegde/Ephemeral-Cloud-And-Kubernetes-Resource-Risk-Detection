"""The four canonical demo incidents (INC-A..INC-D), forced in at fixed times so the
dashboard/replay always has the brief's signature cases to show.
"""
from __future__ import annotations

from datetime import timedelta

from modules.data_simulation.generator.context import SimContext
from modules.data_simulation.generator.model import Campaign
from modules.data_simulation.generator.scenarios import (
    crypto_burst, identity_anomaly, legit_autoscale, public_exposure,
)


def all_incidents(ctx: SimContext) -> list[Campaign]:
    s = ctx.span_start
    out: list[Campaign] = []
    out += crypto_burst.incident(ctx, s + timedelta(days=1, hours=3, minutes=14))     # INC-A 03:14
    out += public_exposure.incident(ctx, s + timedelta(days=2, hours=15, minutes=30))  # INC-B daytime
    out += identity_anomaly.incident(ctx, s + timedelta(days=3, hours=3, minutes=2))   # INC-C 03:02
    out += legit_autoscale.incident(ctx, s + timedelta(days=3, hours=14))              # INC-D daytime
    return out
