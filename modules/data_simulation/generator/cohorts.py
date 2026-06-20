"""Behavioural cohort definitions, loaded from config.

A cohort is a behavioural baseline shared by many ephemeral identities. The
generator uses these baselines to make legitimate bursts and malicious bursts
*structurally similar* (same actions, comparable size/timing) while differing in
tag completeness, controller ownership, off-hours activity, and novelty -- which
is exactly the separation the detection pipeline must learn.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Cohort:
    name: str
    principal_type: str            # AssumedRole | IAMUser | AWSService
    role_name: str
    k8s_subject: str               # K8s audit `user.username` for this cohort ("" if N/A)
    active_hours: tuple[int, int]  # [start, end) UTC hours considered normal
    burst_min: int
    burst_max: int
    tag_completeness: float        # 0..1 fraction of expected_tags typically present
    namespaces: tuple[str, ...]
    source_ip_cidr: str
    expected_tags: tuple[str, ...]


def load_cohorts(cfg: dict) -> dict[str, Cohort]:
    out: dict[str, Cohort] = {}
    for name, c in cfg.items():
        burst = c["burst"]
        out[name] = Cohort(
            name=name,
            principal_type=c["principal_type"],
            role_name=c["role_name"],
            k8s_subject=c.get("k8s_subject", ""),
            active_hours=(int(c["active_hours"][0]), int(c["active_hours"][1])),
            burst_min=int(burst[0]),
            burst_max=int(burst[1]),
            tag_completeness=float(c["tag_completeness"]),
            namespaces=tuple(c.get("namespaces", []) or []),
            source_ip_cidr=c["source_ip_cidr"],
            expected_tags=tuple(c.get("expected_tags", [])),
        )
    return out
