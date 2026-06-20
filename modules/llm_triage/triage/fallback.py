"""Deterministic, LABEL-FREE templated triage (design doc §10: "provide a templated fallback").

Used when the LLM is disabled (`--no-llm`, tests) or the API is unavailable/returns invalid output.
Guarantees a valid §10 record from the incident bundle ALONE, with no network. It derives intent from
runtime signals only — `edge_types`, `risk_band`, `severity_floor`, `any_privileged`, the source mix,
`max_privilege_level`, exposure, and member-event context. It NEVER reads `scenario_type` or any other
label column (those live in labels.jsonl and are absent at runtime).

Records produced here are tagged `triage_source="template"` by the caller and carry a deliberately
modest `confidence`, so they are distinguishable from real LLM output.
"""
from __future__ import annotations

from typing import Any

# static catalogue of preventative controls, selected by signal.
_GUARDRAILS = {
    "exposure": [
        "Deny 0.0.0.0/0 ingress on new services/security groups by policy (admission webhook / SCP)",
        "Require an explicit exposure justification tag before assigning a public IP",
    ],
    "privilege": [
        "Gate cluster-admin / broad RBAC grants behind just-in-time approval",
        "Alert on privilege escalation by ephemeral (CI/job/SA) cohorts",
    ],
    "session": [
        "Shorten AssumeRole TTLs and scope session policies to least privilege",
        "Correlate federated/assumed-role sessions to their originating principal and pipeline",
    ],
    "burst": [
        "Enforce per-service-account spot/RunInstances quotas via SCP",
        "Require cost-center tags at provisioning; deny untagged compute creation",
    ],
    "default": [
        "Enforce mandatory ownership tags on ephemeral resources",
        "Alert on off-hours activity by automation cohorts",
    ],
}


def _truthy_member(members: list[dict], field: str) -> bool:
    return any(bool(m.get(field)) for m in members)


def _signals(bundle: dict) -> dict[str, Any]:
    """Reduce the bundle to the boolean signals the template branches on (all runtime, LABEL-FREE)."""
    members = bundle.get("member_events") or []
    edges = [str(e) for e in (bundle.get("edge_types") or [])]
    return {
        "exposed": (bundle.get("max_exposure_window_s") or 0) > 0
                   or _truthy_member(members, "public_exposure_flag")
                   or _truthy_member(members, "exposed_open"),
        "privileged": bool(bundle.get("any_privileged"))
                      or (bundle.get("max_privilege_level") or 0) >= 0.8
                      or _truthy_member(members, "privileged"),
        "cross_source": (bundle.get("source_idp_count") or 0) > 0
                        and (bundle.get("source_cloudtrail_count") or 0) > 0,
        "session_edge": any("session" in e or "assumed" in e for e in edges),
        "debug_pod": any(m.get("source") == "k8s_audit" and m.get("controller_owner") in (None, "None")
                         for m in members),
        "off_hours": _truthy_member(members, "off_hours_flag"),
        "novel": _truthy_member(members, "is_novel_principal"),
        "many_events": (bundle.get("event_count") or 0) >= 10,
    }


def build_fallback(bundle: dict) -> dict:
    """Return a valid §10 triage dict (7 fields) derived deterministically from the bundle."""
    sig = _signals(bundle)
    band = str(bundle.get("risk_band") or "HIGH")

    # pick the dominant scenario by signal precedence; each sets intent + MITRE + guardrail bucket.
    if sig["cross_source"] or sig["session_edge"]:
        intent = "Compromised/abused session pivoting across cloud and identity sources"
        mitre = ["T1078.004", "T1550"]
        bucket = "session"
    elif sig["privileged"]:
        intent = "Privilege escalation / credential abuse by an ephemeral principal"
        mitre = ["T1078", "T1098"]
        bucket = "privilege"
    elif sig["debug_pod"]:
        intent = "Unmanaged (orphan-controller) pod, possible exposed debug workload"
        mitre = ["T1610", "T1496"]
        bucket = "exposure" if sig["exposed"] else "default"
    elif sig["exposed"]:
        intent = "Publicly exposed resource at risk of external access"
        mitre = ["T1190", "T1133"]
        bucket = "exposure"
    elif sig["many_events"]:
        intent = "Resource provisioning burst, possible compute hijack for mining"
        mitre = ["T1496", "T1578"]
        bucket = "burst"
    else:
        intent = "Anomalous ephemeral activity requiring analyst review"
        mitre = ["T1496"]
        bucket = "default"

    # evidence bullets, all sourced from bundle fields (never invented).
    evidence = [
        f"Risk band {band} (score {round(float(bundle.get('risk_score') or 0), 3)}), "
        f"{int(bundle.get('event_count') or 0)} events over {round(float(bundle.get('window_s') or 0), 1)}s",
        f"Sources: cloudtrail={int(bundle.get('source_cloudtrail_count') or 0)}, "
        f"k8s={int(bundle.get('source_k8s_count') or 0)}, idp={int(bundle.get('source_idp_count') or 0)}",
    ]
    if bundle.get("severity_floor") == "HIGH":
        evidence.append(f"Tripwire severity floor fired ({int(bundle.get('tripwire_hits') or 0)} hits)")
    if sig["novel"]:
        evidence.append("Principal is novel for its behavioral cohort")
    if sig["off_hours"]:
        evidence.append("Activity occurred off-hours")
    if sig["exposed"]:
        evidence.append(f"Public exposure observed (max window "
                        f"{int(bundle.get('max_exposure_window_s') or 0)}s)")
    if sig["privileged"]:
        evidence.append(f"Privileged action present (max privilege level "
                        f"{round(float(bundle.get('max_privilege_level') or 0), 2)})")

    # disambiguation: name the contextual signals that separate this from the benign look-alike.
    ctx = []
    if sig["novel"]:
        ctx.append("principal novel for cohort")
    if sig["off_hours"]:
        ctx.append("off-hours timing")
    if sig["exposed"]:
        ctx.append("public exposure")
    if sig["privileged"]:
        ctx.append("privileged/credential action")
    if sig["cross_source"] or sig["session_edge"]:
        ctx.append("cross-source session linkage")
    if ctx:
        disambiguation = ("Burst volume alone resembles a benign autoscaler/CI run, but "
                          + ", ".join(ctx) + " separate it from the benign look-alike.")
    else:
        disambiguation = ("Volume resembles a benign autoscaler/CI burst; elevated risk score and "
                          "tag/ownership gaps warrant analyst confirmation.")

    # confidence: modest by design (template, not a reasoning model); CRITICAL slightly higher.
    confidence = 0.55 if band == "CRITICAL" else 0.45

    return {
        "likely_intent": intent,
        "confidence": confidence,
        "mitre": mitre,
        "key_evidence": evidence,
        "disambiguation": disambiguation,
        "recommended_guardrails": list(_GUARDRAILS[bucket]),
    }
