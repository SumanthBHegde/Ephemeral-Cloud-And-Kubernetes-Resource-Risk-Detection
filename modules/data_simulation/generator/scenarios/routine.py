"""Scenario: routine ephemeral lifecycle (normal background, per-source topup).

`fill` tops each source up to its configured volume target with ordinary,
non-risky activity: normal S3/STS/EC2 calls, controller-owned pod churn, and
human dev logins. These are the benign baseline the model learns "normal" from.
"""
from __future__ import annotations

from datetime import timedelta

from modules.data_simulation.generator.context import SimContext
from modules.data_simulation.generator.helpers import (
    add_event, bucket_name, gen_labels, gen_tags, new_campaign, node_name, pod_name, source_ip,
)
from modules.data_simulation.generator.model import (
    SCN_ROUTINE, SEV_NONE, SRC_CLOUDTRAIL, SRC_IDP, SRC_K8S, TIMING_ANY, Campaign,
)


def _new(ctx: SimContext) -> Campaign:
    return new_campaign(ctx, SCN_ROUTINE, is_risky=False, severity=SEV_NONE, timing=TIMING_ANY)


def _cloudtrail_event(ctx: SimContext, camp: Campaign, off: timedelta) -> None:
    cohort = ctx.rng.choice(["ci_runner", "scheduled_lambda", "human_dev"])
    ip = source_ip(ctx, cohort)
    region = ctx.region()
    kind = ctx.rng.choices(
        ["GetObject", "AssumeRole", "RunInstances", "CreateBucket", "PutBucketPolicy",
         "GetCallerIdentity"],
        weights=[40, 20, 12, 8, 8, 12])[0]
    p = ctx.mint_principal(cohort)
    attrs = {"source_ip": ip, "region": region, "user_agent": "aws-sdk-go/1.44.0"}
    if kind == "GetObject":
        attrs |= {"bucket_name": bucket_name(ctx, "app-data"),
                  "key": f"objects/{ctx.b32(6).lower()}.json"}
    elif kind == "AssumeRole":
        assumed = ctx.mint_principal_for_role(ctx.cohorts[cohort].role_name, "auto")
        attrs |= {"role_arn": f"arn:aws:iam::{ctx.account_id}:role/{ctx.cohorts[cohort].role_name}",
                  "role_session_name": "auto", "result_assumed_role_id": assumed.principal_id,
                  "result_assumed_role_arn": assumed.arn,
                  "result_access_key_id": assumed.access_key_id}
    elif kind == "RunInstances":
        attrs |= {"instance_type": "m5.large", "spot": False, "public_ip": None,
                  "tags": gen_tags(ctx, cohort), "instance_id": "i-" + ctx.hex(17)}
    elif kind in ("CreateBucket", "PutBucketPolicy"):
        attrs |= {"bucket_name": bucket_name(ctx, "app"), "policy_public": False}
    add_event(camp, source=SRC_CLOUDTRAIL, action=kind, principal=p, cohort=cohort, rel_offset=off,
              attrs=attrs)


def _k8s_event(ctx: SimContext, camp: Campaign, off: timedelta) -> None:
    cohort = ctx.rng.choice(["hpa_autoscaler", "ci_runner"])
    ns = ctx.rng.choice(list(ctx.cohorts[cohort].namespaces) or ["prod"])
    ip = source_ip(ctx, cohort)
    app = ctx.rng.choice(["web", "api", "worker"])
    action = ctx.rng.choices(["pod_create", "pod_delete", "rbac_change"], weights=[55, 35, 10])[0]
    attrs = {"namespace": ns, "k8s_subject": ctx.cohorts[cohort].k8s_subject, "source_ip": ip,
             "user_agent": "kube-controller-manager/v1.29.0"}
    if action in ("pod_create", "pod_delete"):
        attrs |= {"pod_name": pod_name(ctx, app), "controller_owner": "ReplicaSet",
                  "controller_name": f"{app}-{ctx.b32(4).lower()}", "privileged": False,
                  "image": f"registry.example.com/{app}:2.1.0",
                  "labels": gen_labels(ctx, cohort, app=app, managed=True), "node": node_name(ctx)}
    else:
        attrs |= {"rbac_kind": "RoleBinding", "rbac_name": f"{app}-read",
                  "subjects": [{"kind": "ServiceAccount", "name": f"{app}-sa", "namespace": ns}],
                  "role_ref": {"kind": "Role", "name": f"{app}-reader",
                               "apiGroup": "rbac.authorization.k8s.io"}}
    add_event(camp, source=SRC_K8S, action=action, principal=ctx.mint_principal(cohort),
              cohort=cohort, rel_offset=off, attrs=attrs)


def _idp_event(ctx: SimContext, camp: Campaign, off: timedelta) -> None:
    cohort = "human_dev"
    p = ctx.mint_principal(cohort)
    p.email = f"{p.user_name}@example.com"
    add_event(camp, source=SRC_IDP, action="session_start", principal=p, cohort=cohort,
              rel_offset=off,
              attrs={"okta_event_type": ctx.rng.choice(
                         ["user.session.start", "user.authentication.sso"]),
                     "source_ip": source_ip(ctx, cohort), "as_org": "Corp ISP",
                     "isp": "Corp ISP", "domain": "corp.example",
                     "display_message": "User single sign on to app"})


_BUILDERS = {SRC_CLOUDTRAIL: _cloudtrail_event, SRC_K8S: _k8s_event, SRC_IDP: _idp_event}


def fill(ctx: SimContext, remaining: dict[str, int]) -> list[Campaign]:
    """Top each source up to its target with small routine campaigns (1-4 events each)."""
    out: list[Campaign] = []
    for source, need in remaining.items():
        builder = _BUILDERS[source]
        made = 0
        while made < need:
            camp = _new(ctx)
            k = min(ctx.rng.randint(1, 4), need - made)
            off = timedelta(0)
            for _ in range(k):
                builder(ctx, camp, off)
                off += timedelta(seconds=ctx.rng.randint(5, 120))
            out.append(camp)
            made += k
    return out
