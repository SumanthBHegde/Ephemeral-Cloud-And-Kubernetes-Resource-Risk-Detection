"""Normalize one authentic Kubernetes audit.k8s.io/v1 record into a unified-schema row.

Field paths verified against `modules/data_simulation/generator/schemas/k8s_audit.py`.
The detection signals live exactly where they do in a real audit log:
- metadata.ownerReferences ABSENT        -> controller_owner=None (bare-pod signal)
- spec.containers[].securityContext.privileged -> privileged
- Service type NodePort/LoadBalancer + 0.0.0.0/0 -> exposed_open
Note: pod_delete records carry no requestObject, so create-only signals stay falsy there.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

_ACTION = {
    ("create", "pods"): "pod_create",
    ("delete", "pods"): "pod_delete",
    ("create", "services"): "service_expose",
}
_RBAC_RESOURCES = {"roles", "clusterroles", "rolebindings", "clusterrolebindings"}


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _action(verb: str, resource: str) -> str:
    if resource in _RBAC_RESOURCES:
        return "rbac_change"
    return _ACTION.get((verb, resource), f"{verb}_{resource}")


def _controller_owner(req_obj: dict) -> Optional[str]:
    refs = (req_obj.get("metadata") or {}).get("ownerReferences") or []
    for ref in refs:
        if ref.get("controller"):
            return ref.get("kind")
    return refs[0].get("kind") if refs else None


def _privileged(req_obj: dict) -> bool:
    for c in (req_obj.get("spec") or {}).get("containers", []) or []:
        if (c.get("securityContext") or {}).get("privileged"):
            return True
    return False


def _exposure(req_obj: dict) -> tuple[Optional[str], bool]:
    """(service_type, exposed_open) for a Service object; (None, False) otherwise."""
    spec = req_obj.get("spec") or {}
    svc_type = spec.get("type")
    if not svc_type or req_obj.get("kind") != "Service":
        return None, False
    ranges = list(spec.get("loadBalancerSourceRanges") or [])
    ann = (req_obj.get("metadata") or {}).get("annotations") or {}
    if ann.get("sim.exposure/source-ranges"):
        ranges.append(ann["sim.exposure/source-ranges"])
    exposed_open = "0.0.0.0/0" in ranges
    return svc_type, exposed_open


def _broad_rbac(req_obj: dict) -> bool:
    """cluster-admin binding or a wildcard rule == privilege escalation signal."""
    role_ref = req_obj.get("roleRef") or {}
    if role_ref.get("name") == "cluster-admin":
        return True
    for rule in req_obj.get("rules") or []:
        if "*" in (rule.get("verbs") or []) or "*" in (rule.get("resources") or []):
            return True
    return False


def normalize(rec: dict) -> dict:
    verb = rec.get("verb")
    obj_ref = rec.get("objectRef") or {}
    resource = obj_ref.get("resource", "")
    action = _action(verb, resource)
    req_obj = rec.get("requestObject") or {}
    user = rec.get("user") or {}
    subject = user.get("username")
    src_ips = rec.get("sourceIPs") or []

    is_rbac = action == "rbac_change"
    svc_type, exposed_open = _exposure(req_obj)
    labels = ((req_obj.get("metadata") or {}).get("labels")) or {}

    return {
        "record_id": rec.get("auditID"),
        "source": "k8s_audit",
        "event_time": _parse_ts(rec["requestReceivedTimestamp"]),
        "action": action,
        "principal_id": subject,
        "principal_type": "ServiceAccount" if subject and subject.startswith(
            "system:serviceaccount:") else "User",
        "principal_arn": None,
        "role_name": None,
        "source_ip": src_ips[0] if src_ips else None,
        "region": None,
        "namespace": obj_ref.get("namespace"),
        "resource_id": obj_ref.get("name"),
        "resource_type": resource.rstrip("s") if resource else None,
        "session_name": None,
        "external_session_id": None,
        "assumed_role_id": None,
        "shared_event_id": None,
        "tags": {},
        "is_spot": False,
        "public_ip": None,
        "controller_owner": _controller_owner(req_obj) if action == "pod_create" else None,
        "privileged": _privileged(req_obj),
        "host_network": bool((req_obj.get("spec") or {}).get("hostNetwork", False)),
        "service_type": svc_type,
        "exposed_open": exposed_open,
        "rbac_change": is_rbac,
        "broad_rbac": _broad_rbac(req_obj) if is_rbac else False,
        "is_proxy": None,
        "outcome": str((rec.get("responseStatus") or {}).get("code", "")),
        "read_only": verb in ("get", "list", "watch"),
        "session_ttl": None,
        "labels": labels,
        "raw": json.dumps(rec, separators=(",", ":")),
    }
