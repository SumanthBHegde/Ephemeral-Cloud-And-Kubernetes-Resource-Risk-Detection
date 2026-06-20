"""Scenario: legitimate CI/CD pipeline activity (noise to suppress).

A pipeline run = a CI service-account token grant (IdP) + a burst of Job-owned build
pods (K8s) that create and then complete/delete, optionally a build VM. Short-lived and
bursty like an attack, but controller-owned, fully tagged, and from a known service
account -- the benign half of the confusability problem.
"""
from __future__ import annotations

from datetime import timedelta

from modules.data_simulation.generator.context import SimContext
from modules.data_simulation.generator.helpers import (
    add_event, burst_offsets, gen_labels, new_campaign, node_name, pod_name, source_ip,
)
from modules.data_simulation.generator.model import (
    SCN_LEGIT_CICD, SEV_NONE, SRC_CLOUDTRAIL, SRC_IDP, SRC_K8S, TIMING_BUSINESS, Campaign,
)


def _pipeline(ctx: SimContext) -> Campaign:
    cohort = "ci_runner"
    ns = ctx.rng.choice(list(ctx.cohorts[cohort].namespaces) or ["ci"])
    subject = ctx.cohorts[cohort].k8s_subject
    ip = source_ip(ctx, cohort)
    app = ctx.rng.choice(["web", "api", "worker", "payments"])
    job = f"build-{app}-{ctx.b32(4).lower()}"
    camp = new_campaign(ctx, SCN_LEGIT_CICD, is_risky=False, severity=SEV_NONE,
                        timing=TIMING_BUSINESS)

    # 1) CI bot obtains an OAuth token (IdP feed)
    bot = ctx.mint_principal(cohort)
    bot.email = "ci-bot@example.com"
    add_event(camp, source=SRC_IDP, action="token_grant", principal=bot, cohort=cohort,
              rel_offset=timedelta(0),
              attrs={"okta_event_type": "app.oauth2.token.grant", "source_ip": ip,
                     "as_org": "amazon.com", "isp": "amazon.com",
                     "display_message": "OAuth2.0 access token is granted",
                     "auth_provider": "OKTA_AUTHENTICATION_PROVIDER"})

    # 2) Job-owned build pods create then complete (K8s feed)
    n = ctx.rng.randint(3, 10)
    offs = burst_offsets(ctx, n, 1, 5)
    pods = []
    for i in range(n):
        pod = pod_name(ctx, job)
        pods.append(pod)
        add_event(camp, source=SRC_K8S, action="pod_create", principal=ctx.mint_principal(cohort),
                  cohort=cohort, rel_offset=offs[i] + timedelta(seconds=2),
                  attrs={"namespace": ns, "pod_name": pod, "k8s_subject": subject,
                         "controller_owner": ctx.rng.choice(["Job", "CronJob"]),
                         "controller_name": job, "privileged": False,
                         "image": f"registry.example.com/ci/{app}-builder:latest",
                         "labels": gen_labels(ctx, cohort, app=app, managed=True),
                         "node": node_name(ctx), "source_ip": ip,
                         "restart_policy": "Never", "user_agent": "ci-runner/1.0"})
    base = timedelta(minutes=ctx.rng.randint(2, 12))
    for i in range(n):
        add_event(camp, source=SRC_K8S, action="pod_delete", principal=ctx.mint_principal(cohort),
                  cohort=cohort, rel_offset=base + timedelta(seconds=i * 2),
                  attrs={"namespace": ns, "pod_name": pods[i], "k8s_subject": subject,
                         "source_ip": ip, "user_agent": "ci-runner/1.0"})
    return camp


def generate(ctx: SimContext, target_events: int) -> list[Campaign]:
    out: list[Campaign] = []
    made = 0
    while made < target_events:
        camp = _pipeline(ctx)
        out.append(camp)
        made += len(camp.events)
    return out
