"""Normalize one authentic AWS CloudTrail record into a unified-schema row.

Field paths verified against `modules/data_simulation/generator/schemas/cloudtrail.py`.
Service principals (AWSService) carry no `principalId`, so we synthesize a stable actor
key from `invokedBy` + role so burst/novelty features can group them.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _role_name_from_arn(arn: Optional[str]) -> Optional[str]:
    if not arn:
        return None
    # arn:aws:iam::acct:role/NAME  or  arn:aws:sts::acct:assumed-role/NAME/session
    if ":role/" in arn:
        return arn.split(":role/", 1)[1].split("/")[0]
    if ":assumed-role/" in arn:
        return arn.split(":assumed-role/", 1)[1].split("/")[0]
    return None


def _identity(rec: dict) -> dict:
    """Return principal_id/type/arn/role_name, synthesizing a key for AWSService."""
    ui = rec.get("userIdentity", {}) or {}
    ptype = ui.get("type")
    arn = ui.get("arn")
    pid = ui.get("principalId")
    role_name = None
    sc = ui.get("sessionContext", {}) or {}
    issuer = sc.get("sessionIssuer", {}) or {}
    if issuer:
        role_name = issuer.get("userName") or _role_name_from_arn(issuer.get("arn"))
    if ptype == "AWSService":
        invoked = ui.get("invokedBy", "AWS Internal")
        # roleArn (request) is the most stable role hint for a service principal
        role_arn = (rec.get("requestParameters") or {}).get("roleArn")
        role_name = role_name or _role_name_from_arn(role_arn)
        pid = f"service:{invoked}" + (f":{role_name}" if role_name else "")
        arn = arn or role_arn
    role_name = role_name or _role_name_from_arn(arn)
    return {"principal_id": pid, "principal_type": ptype,
            "principal_arn": arn, "role_name": role_name}


def _tags(req: dict) -> dict:
    items = (((req.get("tagSpecificationSet") or {}).get("items")) or [])
    out: dict[str, str] = {}
    for spec in items:
        for t in spec.get("tags", []):
            out[t.get("key")] = t.get("value")
    return out


def _public_ip(resp: dict) -> Optional[str]:
    for inst in (((resp or {}).get("instancesSet") or {}).get("items") or []):
        for nif in ((inst.get("networkInterfaceSet") or {}).get("items") or []):
            assoc = nif.get("association") or {}
            if assoc.get("publicIp"):
                return assoc["publicIp"]
    return None


def _instance_id(resp: dict, req: dict) -> Optional[str]:
    for inst in (((resp or {}).get("instancesSet") or {}).get("items") or []):
        if inst.get("instanceId"):
            return inst["instanceId"]
    return None


def _resource(rec: dict, action: str) -> tuple[Optional[str], Optional[str]]:
    """(resource_id, resource_type) from the resources[] block or request params."""
    for r in rec.get("resources", []) or []:
        arn = r.get("ARN", "")
        rid = arn.rsplit("/", 1)[-1] or arn.rsplit(":", 1)[-1]
        return rid, r.get("type")
    req = rec.get("requestParameters") or {}
    if req.get("bucketName"):
        return req["bucketName"], "AWS::S3::Bucket"
    return None, None


def normalize(rec: dict) -> dict:
    action = rec.get("eventName")
    req = rec.get("requestParameters") or {}
    resp = rec.get("responseElements") or {}
    ident = _identity(rec)
    assumed = ((resp.get("assumedRoleUser") or {}).get("assumedRoleId"))
    resource_id, resource_type = _resource(rec, action)
    # EC2-specific signals
    is_spot = bool(((req.get("instanceMarketOptions") or {}).get("marketType")) == "spot")
    public_ip = _public_ip(resp)
    if action in ("RunInstances", "TerminateInstances"):
        resource_id = _instance_id(resp, req) or resource_id
        resource_type = "AWS::EC2::Instance"
    # S3 public policy
    exposed_open = False
    if action == "PutBucketPolicy":
        pol = req.get("bucketPolicy") or {}
        for stmt in pol.get("Statement", []):
            if stmt.get("Principal") == "*":
                exposed_open = True

    return {
        "record_id": rec.get("eventID"),
        "source": "cloudtrail",
        "event_time": _parse_ts(rec["eventTime"]),
        "action": action,
        "principal_id": ident["principal_id"],
        "principal_type": ident["principal_type"],
        "principal_arn": ident["principal_arn"],
        "role_name": ident["role_name"],
        "source_ip": rec.get("sourceIPAddress"),
        "region": rec.get("awsRegion"),
        "namespace": None,
        "resource_id": resource_id,
        "resource_type": resource_type,
        "session_name": req.get("roleSessionName"),
        "external_session_id": None,
        "assumed_role_id": assumed,
        "shared_event_id": rec.get("sharedEventID"),
        "tags": _tags(req),
        "is_spot": is_spot,
        "public_ip": public_ip,
        "controller_owner": None,
        "privileged": False,
        "host_network": False,
        "service_type": None,
        "exposed_open": exposed_open,
        "rbac_change": False,
        "broad_rbac": False,
        "is_proxy": None,
        "outcome": "SUCCESS",
        "read_only": bool(rec.get("readOnly", False)),
        "session_ttl": req.get("durationSeconds"),
        "labels": {},
        "raw": json.dumps(rec, separators=(",", ":")),
    }
