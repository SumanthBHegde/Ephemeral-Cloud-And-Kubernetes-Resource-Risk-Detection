"""Scenario: public exposure of ephemeral compute (+ benign LoadBalancer twin).

Malicious: a bare (no controller) privileged debug pod in `dev`, exposed via NodePort
to 0.0.0.0/0, alive ~11 minutes then deleted (MITRE T1190). Benign twin: a normal
controller-owned app fronted by a LoadBalancer with a public IP -- public exposure
is *normal* for a load balancer, *dangerous* for a controllerless privileged pod.
"""
from __future__ import annotations

from datetime import timedelta

from modules.data_simulation.generator.context import SimContext
from modules.data_simulation.generator.helpers import (
    add_event, gen_labels, new_campaign, node_name, pod_name, source_ip,
)
from modules.data_simulation.generator.model import (
    SCN_EXPOSURE, SCN_ROUTINE, SEV_HIGH, SEV_NONE, SRC_K8S,
    TIMING_ANY, TIMING_FIXED, Campaign,
)

_DEBUG_IMAGES = ["nicolaka/netshoot:latest", "ubuntu:22.04", "alpine:latest", "busybox:latest"]


def _malicious(ctx: SimContext, pair_id: str, n_pods: int, *, incident_id=None, anchor=None,
               lifetime_min: int | None = None) -> Campaign:
    cohort = "human_dev"
    ns = "dev"
    subject = ctx.cohorts[cohort].k8s_subject
    ip = source_ip(ctx, cohort)
    camp = new_campaign(ctx, SCN_EXPOSURE, is_risky=True, severity=SEV_HIGH,
                        timing=TIMING_FIXED if anchor else TIMING_ANY,
                        incident_id=incident_id, anomaly_type="public_exposure",
                        pair_id=pair_id, fixed_anchor=anchor)
    base = timedelta(0)
    for _ in range(n_pods):
        pod = pod_name(ctx, "debug")
        node = node_name(ctx)
        common = {"namespace": ns, "pod_name": pod, "k8s_subject": subject,
                  "source_ip": ip, "node": node, "user_agent": "kubectl/v1.29.0 (linux/amd64)"}
        add_event(camp, source=SRC_K8S, action="pod_create", principal=ctx.mint_principal(cohort),
                  cohort=cohort, rel_offset=base,
                  attrs={**common, "controller_owner": None,  # bare pod -> Case-2 signal
                         "privileged": True, "host_network": True,
                         "image": ctx.rng.choice(_DEBUG_IMAGES),
                         "labels": gen_labels(ctx, cohort, managed=False),
                         "restart_policy": "Never"})
        add_event(camp, source=SRC_K8S, action="service_expose",
                  principal=ctx.mint_principal(cohort), cohort=cohort,
                  rel_offset=base + timedelta(seconds=ctx.rng.randint(3, 20)),
                  attrs={**common, "service_name": f"{pod}-svc", "service_type": "NodePort",
                         "node_port": ctx.rng.randint(30000, 32767), "exposed_cidr": "0.0.0.0/0",
                         "labels": gen_labels(ctx, cohort, managed=False)})
        life = lifetime_min or ctx.rng.randint(4, 14)
        add_event(camp, source=SRC_K8S, action="pod_delete", principal=ctx.mint_principal(cohort),
                  cohort=cohort, rel_offset=base + timedelta(minutes=life),
                  attrs={**common})
        base += timedelta(minutes=ctx.rng.randint(15, 90))
    return camp


def _benign_twin(ctx: SimContext, pair_id: str) -> Campaign:
    cohort = "ci_runner"
    ns = "prod"
    subject = ctx.cohorts[cohort].k8s_subject
    ip = source_ip(ctx, cohort)
    app = ctx.rng.choice(["web", "api", "checkout"])
    camp = new_campaign(ctx, SCN_ROUTINE, is_risky=False, severity=SEV_NONE,
                        timing=TIMING_ANY, pair_id=pair_id)
    pod = pod_name(ctx, app)
    common = {"namespace": ns, "k8s_subject": subject, "source_ip": ip,
              "node": node_name(ctx), "user_agent": "argocd/v2.9.0"}
    add_event(camp, source=SRC_K8S, action="pod_create", principal=ctx.mint_principal(cohort),
              cohort=cohort, rel_offset=timedelta(0),
              attrs={**common, "pod_name": pod, "controller_owner": "ReplicaSet",
                     "controller_name": f"{app}-7d9f", "privileged": False,
                     "image": f"registry.example.com/{app}:1.4.2",
                     "labels": gen_labels(ctx, cohort, app=app, managed=True)})
    add_event(camp, source=SRC_K8S, action="service_expose", principal=ctx.mint_principal(cohort),
              cohort=cohort, rel_offset=timedelta(seconds=ctx.rng.randint(2, 15)),
              attrs={**common, "service_name": f"{app}-lb", "service_type": "LoadBalancer",
                     "port": 443, "exposed_cidr": "0.0.0.0/0",  # public IP normal for an LB
                     "labels": gen_labels(ctx, cohort, app=app, managed=True)})
    return camp


def _pair(ctx: SimContext, *, n_pods=None, incident_id=None, anchor=None,
          lifetime_min=None) -> list[Campaign]:
    pair_id = "PAIR-" + ctx.b32(6)
    n_pods = n_pods or ctx.rng.randint(1, 3)
    mal = _malicious(ctx, pair_id, n_pods, incident_id=incident_id, anchor=anchor,
                     lifetime_min=lifetime_min)
    twin = _benign_twin(ctx, pair_id)
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
    """Canonical INC-B: bare privileged debug pod, NodePort 0.0.0.0/0, ~11-min lifetime."""
    return _pair(ctx, n_pods=1, incident_id="INC-B", anchor=anchor, lifetime_min=11)
