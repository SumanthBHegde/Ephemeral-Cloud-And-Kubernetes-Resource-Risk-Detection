"""Construction helpers shared by scenario generators.

Keeps scenarios short and consistent: campaign/event factories that copy
ground-truth labels down from the campaign, plus cohort-aware tag, IP, name and
burst-timing generators that encode the *confusability* contract (legit bursts get
complete tags + a controller; malicious ones don't).
"""
from __future__ import annotations

from datetime import timedelta

from modules.data_simulation.generator.context import SimContext
from modules.data_simulation.generator.model import (
    SEV_NONE, Campaign, Event, Principal,
)
from modules.data_simulation.generator.util import private_ip

# cohort -> the `environment` tag value / namespace flavour
_ENV = {"ci_runner": "ci", "hpa_autoscaler": "prod", "human_dev": "dev",
        "scheduled_lambda": "prod"}
_MANAGED_BY = {"ci_runner": "github-actions", "hpa_autoscaler": "cluster-autoscaler",
               "human_dev": "manual", "scheduled_lambda": "terraform"}


# --- campaign / event factories ---------------------------------------------
def new_campaign(ctx: SimContext, scenario_type: str, *, is_risky: bool, severity: str,
                 timing: str, incident_id: str | None = None,
                 anomaly_type: str | None = None, pair_id: str | None = None,
                 fixed_anchor=None) -> Campaign:
    return Campaign(
        campaign_id="CMP-" + ctx.b32(8),
        scenario_type=scenario_type,
        is_risky=is_risky,
        severity=severity,
        true_incident_id=incident_id,
        anomaly_type=anomaly_type,
        pair_id=pair_id,
        timing=timing,
        fixed_anchor=fixed_anchor,
    )


def add_event(camp: Campaign, *, source: str, action: str, principal: Principal,
              cohort: str, attrs: dict | None = None, rel_offset: timedelta = timedelta(0),
              anomaly_type: str | None = None, shared_event_id: str | None = None,
              external_session_id: str | None = None) -> Event:
    ev = Event(
        source=source, action=action, cohort=cohort, principal=principal,
        attrs=attrs or {}, rel_offset=rel_offset,
        is_risky=camp.is_risky, scenario_type=camp.scenario_type,
        campaign_id=camp.campaign_id, true_incident_id=camp.true_incident_id,
        severity=camp.severity, anomaly_type=anomaly_type or camp.anomaly_type,
        pair_id=camp.pair_id,
        shared_event_id=shared_event_id, external_session_id=external_session_id,
    )
    camp.events.append(ev)
    return ev


# --- cohort-aware value generators ------------------------------------------
def source_ip(ctx: SimContext, cohort: str) -> str:
    return private_ip(ctx.cohorts[cohort].source_ip_cidr, ctx.rng)


def _tag_value(ctx: SimContext, key: str, cohort: str) -> str:
    if key == "owner":
        return ctx.cohorts[cohort].role_name
    if key == "environment":
        return _ENV.get(cohort, "prod")
    if key == "cost-center":
        return "CC-" + str(ctx.rng.randint(1000, 9999))
    if key == "managed-by":
        return _MANAGED_BY.get(cohort, "terraform")
    if key == "app":
        return ctx.rng.choice(["web", "api", "worker", "checkout", "payments"])
    if key == "pipeline":
        return "pipe-" + ctx.b32(5).lower()
    return ctx.b32(4).lower()


def gen_tags(ctx: SimContext, cohort: str, completeness: float | None = None) -> dict:
    """Build a tag dict; each expected tag is present with prob `completeness`.

    Pass completeness=0.0 for the deliberately-untagged malicious resources."""
    c = ctx.cohorts[cohort]
    comp = c.tag_completeness if completeness is None else completeness
    return {k: _tag_value(ctx, k, cohort)
            for k in c.expected_tags if ctx.rng.random() < comp}


def gen_labels(ctx: SimContext, cohort: str, app: str | None = None,
               managed: bool = True) -> dict:
    """Kubernetes pod/service labels (the K8s analogue of tags)."""
    labels = {"app": app or ctx.rng.choice(["web", "api", "worker"])}
    if managed:
        labels["app.kubernetes.io/managed-by"] = _MANAGED_BY.get(cohort, "argocd")
        labels["environment"] = _ENV.get(cohort, "prod")
        labels["pod-template-hash"] = ctx.b32(9).lower()
    return labels


def pod_name(ctx: SimContext, base: str) -> str:
    return f"{base}-{ctx.b32(5).lower()}"


def node_name(ctx: SimContext) -> str:
    return f"ip-10-0-{ctx.rng.randint(1, 250)}-{ctx.rng.randint(1, 250)}.ec2.internal"


def bucket_name(ctx: SimContext, base: str = "data") -> str:
    return f"{base}-{ctx.b32(8).lower()}"


def burst_offsets(ctx: SimContext, n: int, lo: int = 2, hi: int = 12) -> list[timedelta]:
    """Cumulative second-level gaps for an n-event burst (events seconds apart,
    grounded in real cluster-trace arrival timing)."""
    offs, t = [], 0.0
    for _ in range(n):
        offs.append(timedelta(seconds=t))
        t += ctx.rng.randint(lo, hi) + ctx.rng.random()
    return offs
