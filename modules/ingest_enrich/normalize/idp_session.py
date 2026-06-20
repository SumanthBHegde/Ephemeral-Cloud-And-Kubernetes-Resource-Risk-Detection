"""Normalize one Okta-style IdP System Log record into a unified-schema row.

Field paths verified against `modules/data_simulation/generator/schemas/idp_session.py`.
The actor key is the email (alternateId); `externalSessionId` and the displayName/session
name are the cross-source thread to the AssumeRoleWithWebIdentity it triggers in CloudTrail.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def normalize(rec: dict) -> dict:
    actor = rec.get("actor") or {}
    client = rec.get("client") or {}
    auth = rec.get("authenticationContext") or {}
    sec = rec.get("securityContext") or {}
    outcome = (rec.get("outcome") or {}).get("result")

    return {
        "record_id": rec.get("uuid"),
        "source": "idp_session",
        "event_time": _parse_ts(rec["published"]),
        "action": rec.get("eventType"),
        "principal_id": actor.get("alternateId"),
        "principal_type": actor.get("type", "User"),
        "principal_arn": None,
        "role_name": None,
        "source_ip": client.get("ipAddress"),
        "region": None,
        "namespace": None,
        "resource_id": None,
        "resource_type": "session",
        "session_name": actor.get("displayName"),
        "external_session_id": auth.get("externalSessionId"),
        "assumed_role_id": None,
        "shared_event_id": None,
        "tags": {},
        "is_spot": False,
        "public_ip": None,
        "controller_owner": None,
        "privileged": False,
        "host_network": False,
        "service_type": None,
        "exposed_open": False,
        "rbac_change": False,
        "broad_rbac": False,
        "is_proxy": bool(sec.get("isProxy", False)),
        "outcome": outcome,
        "read_only": True,
        "session_ttl": None,
        "labels": {},
        "raw": json.dumps(rec, separators=(",", ":")),
    }
