"""Rule-assisted behavioral-cohort assignment (design doc §6).

Ephemeral identities have no stable history, so we assign each event's principal to one
of four behavioral cohorts using authentic naming/identity signals the simulator already
encodes, in priority order:

  1. K8s service-account / user subject          (most specific)
  2. CloudTrail role name / service invokedBy
  3. IdP actor email prefix
  4. source-IP CIDR                                (fallback)

Unmatched principals -> "unknown" (never silently forced into a wrong cohort — that would
poison the cohort baselines the deviation feature depends on).

The cohort *names*, active_hours, and expected_tags come from the simulator's config so
there is one source of truth, but the *matching rules* are grounded in the identity fields
that actually appear in the rendered records (e.g. the autoscale path surfaces as the
`replicaset-controller` K8s subject and the `autoscaling.amazonaws.com` service principal,
which the config's nominal `k8s_subject` does not capture).
"""
from __future__ import annotations

import ipaddress
from typing import Optional

from modules.data_simulation.generator.build import load_config
from modules.data_simulation.generator.cohorts import Cohort, load_cohorts

UNKNOWN = "unknown"

# --- explicit identity rules, grounded in the rendered records --------------------------
# K8s user.username -> cohort
_K8S_SUBJECTS = {
    "system:serviceaccount:ci:ci-runner-sa": "ci_runner",
    "dev-user": "human_dev",
    "system:serviceaccount:kube-system:replicaset-controller": "hpa_autoscaler",
    "system:serviceaccount:kube-system:cluster-autoscaler": "hpa_autoscaler",
}
# CloudTrail role name / sessionIssuer userName -> cohort
_ROLE_NAMES = {
    "ci-runner-role": "ci_runner",
    "developer": "human_dev",
    "scheduled-lambda-role": "scheduled_lambda",
    "cluster-autoscaler-role": "hpa_autoscaler",
}
# CloudTrail AWSService invokedBy -> cohort
_INVOKED_BY = {
    "lambda.amazonaws.com": "scheduled_lambda",
    "autoscaling.amazonaws.com": "hpa_autoscaler",
}
# IdP actor email prefix -> cohort
_IDP_PREFIXES = {
    "human_dev": "human_dev",
    "ci": "ci_runner",
}


class CohortResolver:
    """Holds the cohort definitions + compiled CIDR fallbacks; resolves one row at a time."""

    def __init__(self, cohorts: dict[str, Cohort]):
        self.cohorts = cohorts
        self._cidrs = [
            (ipaddress.ip_network(c.source_ip_cidr, strict=False), name)
            for name, c in cohorts.items()
        ]

    @classmethod
    def from_config(cls, config_path: str | None = None) -> "CohortResolver":
        cfg = load_config(config_path)
        return cls(load_cohorts(cfg["cohorts"]))

    def _by_cidr(self, ip: Optional[str]) -> Optional[str]:
        if not ip:
            return None
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return None
        for net, name in self._cidrs:
            if addr in net:
                return name
        return None

    def resolve(self, row: dict) -> str:
        """Assign a cohort to one normalized row using the priority chain."""
        source = row.get("source")
        pid = row.get("principal_id") or ""

        if source == "k8s_audit":
            hit = _K8S_SUBJECTS.get(pid)
            if hit:
                return hit
        elif source == "cloudtrail":
            role = row.get("role_name")
            if role and role in _ROLE_NAMES:
                return _ROLE_NAMES[role]
            if pid.startswith("service:"):
                for token, name in _INVOKED_BY.items():
                    if token in pid:
                        return name
        elif source == "idp_session":
            prefix = pid.split("@")[0].rsplit("-", 1)[0]
            if prefix in _IDP_PREFIXES:
                return _IDP_PREFIXES[prefix]

        # fallback: source-IP CIDR (covers controllerless/attacker rows that dodge naming)
        return self._by_cidr(row.get("source_ip")) or UNKNOWN


def assign_cohorts(rows: list[dict], resolver: CohortResolver | None = None) -> None:
    """Add a `cohort` key to each row in place."""
    resolver = resolver or CohortResolver.from_config()
    for row in rows:
        row["cohort"] = resolver.resolve(row)
