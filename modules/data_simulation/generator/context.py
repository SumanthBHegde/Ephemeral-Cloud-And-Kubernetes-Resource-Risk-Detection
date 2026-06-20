"""SimContext: the single carrier of deterministic randomness + shared identity factories.

Everything random in the generator flows through ``rng`` (stdlib) or ``np_rng``
(numpy), both seeded from config, so a given seed reproduces the dataset byte for
byte. ID/ARN/principal minting also lives here so every module produces authentic
AWS-shaped identifiers the same way.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from modules.data_simulation.generator.cohorts import Cohort, load_cohorts
from modules.data_simulation.generator.model import Principal

_B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


@dataclass
class SimContext:
    rng: random.Random
    np_rng: np.random.Generator
    account_id: str
    regions: list[str]
    span_start: datetime
    span_days: int
    cohorts: dict[str, Cohort]

    # --- deterministic primitives -------------------------------------------
    def b32(self, n: int) -> str:
        return "".join(self.rng.choice(_B32) for _ in range(n))

    def hex(self, n: int) -> str:
        return "".join(self.rng.choice("0123456789abcdef") for _ in range(n))

    def uuid(self) -> str:
        """Deterministic UUIDv4-shaped string (seeded, unlike uuid.uuid4())."""
        h = f"{self.rng.getrandbits(128):032x}"
        return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"

    def region(self) -> str:
        return self.rng.choice(self.regions)

    @property
    def span_end(self) -> datetime:
        return self.span_start + timedelta(days=self.span_days)

    # --- identity factories --------------------------------------------------
    def mint_principal(self, cohort_name: str, session_label: str | None = None) -> Principal:
        c = self.cohorts[cohort_name]
        acct = self.account_id
        if c.principal_type == "AssumedRole":
            role_id = "AROA" + self.b32(17)
            session = session_label or f"{cohort_name}-{self.b32(6).lower()}"
            return Principal(
                principal_id=f"{role_id}:{session}",
                principal_type="AssumedRole",
                arn=f"arn:aws:sts::{acct}:assumed-role/{c.role_name}/{session}",
                account_id=acct,
                access_key_id="ASIA" + self.b32(16),   # ASIA = temporary credentials
                session_name=session,
                role_name=c.role_name,
            )
        if c.principal_type == "IAMUser":
            uname = session_label or f"{cohort_name}-{self.b32(4).lower()}"
            return Principal(
                principal_id="AIDA" + self.b32(17),
                principal_type="IAMUser",
                arn=f"arn:aws:iam::{acct}:user/{uname}",
                account_id=acct,
                access_key_id="AKIA" + self.b32(16),
                user_name=uname,
                role_name=c.role_name,
                email=f"{uname}@example.com",
            )
        # AWSService
        invoked_by = "lambda.amazonaws.com" if "lambda" in cohort_name else "autoscaling.amazonaws.com"
        return Principal(
            principal_id=c.role_name,
            principal_type="AWSService",
            arn=f"arn:aws:iam::{acct}:role/{c.role_name}",
            account_id=acct,
            role_name=c.role_name,
            invoked_by=invoked_by,
        )

    def mint_principal_for_role(self, role_name: str, session_label: str) -> Principal:
        """An assumed-role principal for an arbitrary role (used for cross-source
        STS -> S3 linkage where the role isn't tied to a configured cohort)."""
        role_id = "AROA" + self.b32(17)
        return Principal(
            principal_id=f"{role_id}:{session_label}",
            principal_type="AssumedRole",
            arn=f"arn:aws:sts::{self.account_id}:assumed-role/{role_name}/{session_label}",
            account_id=self.account_id,
            access_key_id="ASIA" + self.b32(16),
            session_name=session_label,
            role_name=role_name,
        )

    def federated_principal(self, email: str, idp: str = "okta") -> Principal:
        """A federated/web-identity actor (drives the IdP feed and STS web-identity)."""
        sub = self.b32(20).lower()
        return Principal(
            principal_id=f"{idp}|{sub}",
            principal_type="FederatedUser",
            arn=f"arn:aws:sts::{self.account_id}:federated-user/{email}",
            account_id=self.account_id,
            user_name=email.split("@")[0],
            email=email,
        )


def build_context(cfg: dict) -> SimContext:
    seed = int(cfg["seed"])
    start = datetime.strptime(cfg["start_date"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return SimContext(
        rng=random.Random(seed),
        np_rng=np.random.default_rng(seed),
        account_id=str(cfg["account_id"]),
        regions=list(cfg["regions"]),
        span_start=start,
        span_days=int(cfg["span_days"]),
        cohorts=load_cohorts(cfg["cohorts"]),
    )
