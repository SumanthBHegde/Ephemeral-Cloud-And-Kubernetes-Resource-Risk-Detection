"""Scenario: legitimate HPA / autoscaler pod bursts (noise to suppress).

These are the high-volume, near-identical bursts that must NOT fire: controller-owned
pods, full labels, business hours, matching scale-down. INC-D additionally embeds a
real credential-abuse incident inside one such burst's time window -- the Case-4 test
that suppression must not bury the genuine alert.
"""
from __future__ import annotations

from datetime import timedelta

from modules.data_simulation.generator.context import SimContext
from modules.data_simulation.generator.helpers import (
    add_event, burst_offsets, gen_labels, new_campaign, node_name, pod_name, source_ip,
)
from modules.data_simulation.generator.model import (
    SCN_IDENTITY, SCN_LEGIT_AUTOSCALE, SEV_HIGH, SEV_NONE, SRC_CLOUDTRAIL, SRC_K8S,
    TIMING_BUSINESS, TIMING_FIXED, Campaign,
)

_RS_SUBJECT = "system:serviceaccount:kube-system:replicaset-controller"


def _autoscale_burst(ctx: SimContext, n: int, *, incident_id=None, anchor=None) -> Campaign:
    cohort = "hpa_autoscaler"
    ns = ctx.rng.choice(list(ctx.cohorts[cohort].namespaces) or ["prod"])
    app = ctx.rng.choice(["web", "api", "checkout", "payments"])
    controller = f"{app}-{ctx.b32(4).lower()}"
    ip = source_ip(ctx, cohort)
    camp = new_campaign(ctx, SCN_LEGIT_AUTOSCALE, is_risky=False, severity=SEV_NONE,
                        timing=TIMING_FIXED if anchor else TIMING_BUSINESS,
                        incident_id=incident_id, fixed_anchor=anchor)
    offs = burst_offsets(ctx, n, 1, 6)
    pods = []
    for i in range(n):
        pod = pod_name(ctx, app)
        pods.append(pod)
        add_event(camp, source=SRC_K8S, action="pod_create",
                  principal=ctx.mint_principal(cohort), cohort=cohort, rel_offset=offs[i],
                  attrs={"namespace": ns, "pod_name": pod, "k8s_subject": _RS_SUBJECT,
                         "controller_owner": "ReplicaSet", "controller_name": controller,
                         "privileged": False, "image": f"registry.example.com/{app}:2.1.0",
                         "labels": gen_labels(ctx, cohort, app=app, managed=True),
                         "node": node_name(ctx), "source_ip": ip,
                         "user_agent": "kube-controller-manager/v1.29.0"})
    # scale-down after a few minutes (matching delete pattern)
    down = ctx.rng.randint(0, n // 2)
    base = timedelta(minutes=ctx.rng.randint(5, 25))
    for i in range(down):
        add_event(camp, source=SRC_K8S, action="pod_delete",
                  principal=ctx.mint_principal(cohort), cohort=cohort,
                  rel_offset=base + timedelta(seconds=i * 2),
                  attrs={"namespace": ns, "pod_name": pods[i], "k8s_subject": _RS_SUBJECT,
                         "source_ip": ip, "user_agent": "kube-controller-manager/v1.29.0"})
    return camp


def _embedded_credential_abuse(ctx: SimContext, anchor) -> Campaign:
    """The real INC-D alert hiding inside the burst window: a dev assumes an admin
    role (scope mismatch) and escalates via a cluster-admin binding."""
    cohort = "human_dev"
    dev = ctx.mint_principal(cohort, session_label="oncall")
    ip = source_ip(ctx, cohort)
    camp = new_campaign(ctx, SCN_IDENTITY, is_risky=True, severity=SEV_HIGH,
                        timing=TIMING_FIXED, incident_id="INC-D",
                        anomaly_type="credential_abuse",
                        fixed_anchor=anchor + timedelta(minutes=2))
    admin = ctx.mint_principal_for_role("admin-role", "oncall")
    shared = ctx.uuid()
    add_event(camp, source=SRC_CLOUDTRAIL, action="AssumeRole", principal=dev, cohort=cohort,
              rel_offset=timedelta(0), shared_event_id=shared,
              attrs={"role_arn": f"arn:aws:iam::{ctx.account_id}:role/admin-role",
                     "role_session_name": "oncall", "duration_seconds": 3600,
                     "source_ip": ip, "region": ctx.region(),
                     "result_assumed_role_id": admin.principal_id,
                     "result_assumed_role_arn": admin.arn,
                     "result_access_key_id": admin.access_key_id,
                     "user_agent": "aws-cli/2.13.0"})
    add_event(camp, source=SRC_K8S, action="rbac_change", principal=dev, cohort=cohort,
              rel_offset=timedelta(seconds=ctx.rng.randint(20, 90)),
              attrs={"namespace": "kube-system", "rbac_kind": "ClusterRoleBinding",
                     "rbac_name": "oncall-escalation", "k8s_subject": "dev-user",
                     "subjects": [{"kind": "User", "name": "dev-user",
                                   "apiGroup": "rbac.authorization.k8s.io"}],
                     "role_ref": {"kind": "ClusterRole", "name": "cluster-admin",
                                  "apiGroup": "rbac.authorization.k8s.io"},
                     "source_ip": ip, "user_agent": "kubectl/v1.29.0"})
    return camp


def generate(ctx: SimContext, target_events: int) -> list[Campaign]:
    out: list[Campaign] = []
    made = 0
    while made < target_events:
        c = ctx.cohorts["hpa_autoscaler"]
        camp = _autoscale_burst(ctx, ctx.rng.randint(c.burst_min, c.burst_max))
        out.append(camp)
        made += len(camp.events)
    return out


def incident(ctx: SimContext, anchor) -> list[Campaign]:
    """Canonical INC-D: a 40-pod autoscale burst with a real credential-abuse alert
    embedded in the same window."""
    noise = _autoscale_burst(ctx, 40, anchor=anchor)
    real = _embedded_credential_abuse(ctx, anchor)
    return [noise, real]
