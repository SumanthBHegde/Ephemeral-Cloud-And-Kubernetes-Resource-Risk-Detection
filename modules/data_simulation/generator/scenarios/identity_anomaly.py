"""Scenario: compromised session -> PII access (+ benign scheduled-Lambda twin).

Malicious (the graph-only catch): an unusual federated IdP login issues a web-identity
session; that session assumes a sensitive data-access role and reads PII from S3 at
~03:00, with no scheduled trigger behind it (MITRE T1578; GDPR Art.32). The chain spans
all three feeds and is recoverable via authentic fields: IdP actor email == STS
roleSessionName, and STS assumedRoleUser.assumedRoleId == the S3 caller principalId.

Benign twin: a scheduled Lambda does the same 03:00 S3 read, but it is a known service
principal with a real trigger lineage -- identical surface, different lineage.
"""
from __future__ import annotations

from datetime import timedelta

from modules.data_simulation.generator.context import SimContext
from modules.data_simulation.generator.helpers import (
    add_event, bucket_name, new_campaign, source_ip,
)
from modules.data_simulation.generator.model import (
    SCN_IDENTITY, SCN_ROUTINE, SEV_CRITICAL, SEV_NONE, SRC_CLOUDTRAIL, SRC_IDP,
    TIMING_FIXED, TIMING_OFF_HOURS, Campaign,
)
from modules.data_simulation.generator.util import public_ip

_FOREIGN_GEO = [
    {"city": "Sofia", "state": "Sofia-grad", "country": "Bulgaria", "postalCode": "1000",
     "lat": 42.69, "lon": 23.32},
    {"city": "Lagos", "state": "Lagos", "country": "Nigeria", "postalCode": "100001",
     "lat": 6.45, "lon": 3.39},
    {"city": "Hong Kong", "state": "HK", "country": "Hong Kong", "postalCode": "999077",
     "lat": 22.32, "lon": 114.17},
]
_DATA_ROLE = "data-access-role"


def _malicious(ctx: SimContext, pair_id: str, *, incident_id=None, anchor=None) -> Campaign:
    timing = TIMING_FIXED if anchor else TIMING_OFF_HOURS
    camp = new_campaign(ctx, SCN_IDENTITY, is_risky=True, severity=SEV_CRITICAL,
                        timing=timing, incident_id=incident_id,
                        anomaly_type="identity_session_abuse", pair_id=pair_id,
                        fixed_anchor=anchor)
    email = f"contractor-{ctx.b32(4).lower()}@partner.example"
    subject = email.split("@")[0]
    fed = ctx.federated_principal(email)
    ext_session = "trs" + ctx.b32(20).lower()
    geo = ctx.rng.choice(_FOREIGN_GEO)
    ext_ip = public_ip(ctx.rng)

    # 1) unusual federated IdP login (IdP feed)
    add_event(camp, source=SRC_IDP, action="idp_login", principal=fed, cohort="human_dev",
              rel_offset=timedelta(0), external_session_id=ext_session,
              attrs={"okta_event_type": "user.authentication.auth_via_IDP",
                     "okta_severity": "WARN", "source_ip": ext_ip, "is_proxy": True,
                     "geo": geo, "auth_provider": "FEDERATION", "as_org": "Hosting LLC",
                     "isp": "Hosting LLC", "domain": "vpn.example",
                     "display_message": "Authentication of user via inbound SAML",
                     "result": "SUCCESS"})

    # 2) AssumeRoleWithWebIdentity using that login (CloudTrail STS feed)
    assumed = ctx.mint_principal_for_role(_DATA_ROLE, subject)
    role_arn = f"arn:aws:iam::{ctx.account_id}:role/{_DATA_ROLE}"
    shared = ctx.uuid()
    add_event(camp, source=SRC_CLOUDTRAIL, action="AssumeRoleWithWebIdentity", principal=fed,
              cohort="human_dev", rel_offset=timedelta(seconds=ctx.rng.randint(3, 20)),
              shared_event_id=shared,
              attrs={"role_arn": role_arn, "role_session_name": subject,
                     "provider": "okta.com/saml", "web_subject": subject,
                     "duration_seconds": 900, "source_ip": ext_ip, "region": ctx.region(),
                     "result_assumed_role_id": assumed.principal_id,
                     "result_assumed_role_arn": assumed.arn,
                     "result_access_key_id": assumed.access_key_id,
                     "user_agent": "aws-sdk-js/2.x"})

    # 3) PII reads from S3 by the assumed role (CloudTrail S3 feed)
    bucket = "prod-pii-customers-" + ctx.b32(5).lower()
    n_reads = ctx.rng.randint(2, 5)
    for i in range(n_reads):
        add_event(camp, source=SRC_CLOUDTRAIL, action="GetObject", principal=assumed,
                  cohort="human_dev",
                  rel_offset=timedelta(seconds=ctx.rng.randint(25, 60) + i * 5),
                  shared_event_id=shared,
                  attrs={"bucket_name": bucket, "key": f"pii/customers/part-{i:04d}.parquet",
                         "pii": True, "source_ip": ext_ip, "region": ctx.region(),
                         "user_agent": "aws-sdk-js/2.x"})
    return camp


def _benign_twin(ctx: SimContext, pair_id: str) -> Campaign:
    cohort = "scheduled_lambda"
    camp = new_campaign(ctx, SCN_ROUTINE, is_risky=False, severity=SEV_NONE,
                        timing=TIMING_OFF_HOURS, pair_id=pair_id)  # off-hours is NORMAL here
    svc = ctx.mint_principal(cohort)
    assumed = ctx.mint_principal_for_role("scheduled-lambda-role", "etl-nightly")
    ip = source_ip(ctx, cohort)
    role_arn = f"arn:aws:iam::{ctx.account_id}:role/scheduled-lambda-role"
    shared = ctx.uuid()
    # known trigger lineage: the scheduler service assumes the role
    add_event(camp, source=SRC_CLOUDTRAIL, action="AssumeRole", principal=svc, cohort=cohort,
              rel_offset=timedelta(0), shared_event_id=shared,
              attrs={"role_arn": role_arn, "role_session_name": "etl-nightly",
                     "duration_seconds": 3600, "source_ip": ip, "region": ctx.region(),
                     "result_assumed_role_id": assumed.principal_id,
                     "result_assumed_role_arn": assumed.arn,
                     "result_access_key_id": assumed.access_key_id,
                     "user_agent": "aws-internal/3 aws-sdk-java"})
    bucket = bucket_name(ctx, "prod-analytics")
    for i in range(ctx.rng.randint(2, 5)):
        add_event(camp, source=SRC_CLOUDTRAIL, action="GetObject", principal=assumed, cohort=cohort,
                  rel_offset=timedelta(seconds=ctx.rng.randint(20, 50) + i * 5),
                  shared_event_id=shared,
                  attrs={"bucket_name": bucket, "key": f"warehouse/day/part-{i:04d}.parquet",
                         "source_ip": ip, "region": ctx.region(),
                         "user_agent": "aws-internal/3 aws-sdk-java"})
    return camp


def _pair(ctx: SimContext, *, incident_id=None, anchor=None) -> list[Campaign]:
    pair_id = "PAIR-" + ctx.b32(6)
    return [_malicious(ctx, pair_id, incident_id=incident_id, anchor=anchor),
            _benign_twin(ctx, pair_id)]


def generate(ctx: SimContext, target_events: int) -> list[Campaign]:
    out: list[Campaign] = []
    risky = 0
    while risky < target_events:
        camps = _pair(ctx)
        out.extend(camps)
        risky += sum(len(c.events) for c in camps if c.is_risky)
    return out


def incident(ctx: SimContext, anchor) -> list[Campaign]:
    """Canonical INC-C: federated login -> web-identity session -> PII S3 read ~03:00."""
    return _pair(ctx, incident_id="INC-C", anchor=anchor)
