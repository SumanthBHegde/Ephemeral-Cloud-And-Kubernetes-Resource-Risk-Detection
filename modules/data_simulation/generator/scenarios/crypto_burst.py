"""Scenario: resource-hijacking crypto-mining burst (+ its benign autoscale twin).

Malicious: a compromised CI session spins up a burst of spot VMs off-hours, with
public IPs, NO tags, then terminates them ~90 min later to cover tracks (MITRE
T1496 / T1578). Benign twin: a cluster-autoscaler RunInstances burst of the SAME
size, during business hours, on-demand, fully tagged -- structurally identical in
volume/timing, separable only by context.
"""
from __future__ import annotations

from datetime import timedelta

from modules.data_simulation.generator.context import SimContext
from modules.data_simulation.generator.helpers import (
    add_event, burst_offsets, gen_tags, new_campaign, source_ip,
)
from modules.data_simulation.generator.model import (
    SCN_CRYPTO, SCN_LEGIT_AUTOSCALE, SEV_HIGH, SEV_NONE, SRC_CLOUDTRAIL,
    TIMING_BUSINESS, TIMING_FIXED, TIMING_OFF_HOURS, Campaign,
)
from modules.data_simulation.generator.util import public_ip

_MINING_TYPES = ["c5.2xlarge", "c5.4xlarge", "g4dn.xlarge", "p3.2xlarge"]
_NORMAL_TYPES = ["m5.large", "m5.xlarge", "c5.large"]


def _malicious(ctx: SimContext, pair_id: str, n: int, *, incident_id=None, anchor=None) -> Campaign:
    cohort = "ci_runner"
    principal = ctx.mint_principal(cohort, session_label="ci-deploy")
    camp = new_campaign(
        ctx, SCN_CRYPTO, is_risky=True, severity=SEV_HIGH,
        timing=TIMING_FIXED if anchor else TIMING_OFF_HOURS,
        incident_id=incident_id, anomaly_type="resource_hijacking",
        pair_id=pair_id, fixed_anchor=anchor,
    )
    ip = source_ip(ctx, cohort)
    region = ctx.region()
    offs = burst_offsets(ctx, n, 2, 9)
    instance_ids = ["i-" + ctx.hex(17) for _ in range(n)]
    for i in range(n):
        add_event(camp, source=SRC_CLOUDTRAIL, action="RunInstances", principal=principal,
                  cohort=cohort, rel_offset=offs[i],
                  attrs={"instance_type": ctx.rng.choice(_MINING_TYPES), "spot": True,
                         "public_ip": public_ip(ctx.rng), "tags": {},  # deliberately untagged
                         "source_ip": ip, "region": region, "instance_id": instance_ids[i],
                         "user_agent": "aws-cli/2.13.0 Python/3.11"})
    # cover tracks: terminate the same instances ~90 min later
    term_base = timedelta(minutes=ctx.rng.randint(70, 100))
    for i in range(n):
        add_event(camp, source=SRC_CLOUDTRAIL, action="TerminateInstances", principal=principal,
                  cohort=cohort, rel_offset=term_base + timedelta(seconds=i * ctx.rng.randint(1, 4)),
                  attrs={"source_ip": ip, "region": region, "instance_id": instance_ids[i],
                         "user_agent": "aws-cli/2.13.0 Python/3.11"})
    return camp


def _benign_twin(ctx: SimContext, pair_id: str, n: int, region: str) -> Campaign:
    cohort = "hpa_autoscaler"
    principal = ctx.mint_principal(cohort)
    camp = new_campaign(ctx, SCN_LEGIT_AUTOSCALE, is_risky=False, severity=SEV_NONE,
                        timing=TIMING_BUSINESS, pair_id=pair_id)
    ip = source_ip(ctx, cohort)
    offs = burst_offsets(ctx, n, 2, 9)
    for i in range(n):
        add_event(camp, source=SRC_CLOUDTRAIL, action="RunInstances", principal=principal,
                  cohort=cohort, rel_offset=offs[i],
                  attrs={"instance_type": ctx.rng.choice(_NORMAL_TYPES), "spot": False,
                         "public_ip": None, "tags": gen_tags(ctx, cohort),  # fully tagged
                         "source_ip": ip, "region": region,
                         "instance_id": "i-" + ctx.hex(17),
                         "user_agent": "aws-sdk-go/1.44.0"})
    return camp


def _pair(ctx: SimContext, *, n=None, incident_id=None, anchor=None) -> list[Campaign]:
    pair_id = "PAIR-" + ctx.b32(6)
    n = n or ctx.rng.randint(15, 24)
    mal = _malicious(ctx, pair_id, n, incident_id=incident_id, anchor=anchor)
    region = mal.events[0].attrs["region"]
    twin = _benign_twin(ctx, pair_id, n, region)
    return [mal, twin]


def generate(ctx: SimContext, target_events: int) -> list[Campaign]:
    out: list[Campaign] = []
    risky = 0
    while risky < target_events:
        camps = _pair(ctx)
        out.extend(camps)
        risky += sum(len(c.events) for c in camps if c.is_risky)
    return out


def incident(ctx: SimContext, anchor) -> list[Campaign]:
    """Canonical INC-A: 20x RunInstances by ci-runner ~03:14, untagged spot, off-hours."""
    return _pair(ctx, n=20, incident_id="INC-A", anchor=anchor)
