"""Per-source normalizers: one authentic record -> one unified-schema row dict.

Every parser returns a dict with exactly the keys in `UNIFIED_FIELDS` so the three
sources stack into one homogeneous table. Detection-relevant signals are lifted to
top-level columns; the untouched original is preserved in `raw` for forensic snapshots.
"""
from __future__ import annotations

# The unified event schema. Every normalizer emits these keys (None where N/A) so the
# three sources concatenate cleanly. Feature columns (§5) are added later by enrich/.
UNIFIED_FIELDS = (
    # identity / provenance
    "record_id",          # authentic id: eventID / auditID / uuid (joins to labels.jsonl)
    "source",             # cloudtrail | k8s_audit | idp_session
    "event_time",         # tz-aware UTC datetime
    "action",             # semantic action (RunInstances, pod_create, sso, ...)
    # actor
    "principal_id",       # stable-ish actor key (derived for service principals)
    "principal_type",     # AssumedRole | IAMUser | AWSService | FederatedUser | User
    "principal_arn",
    "role_name",          # role behind an assumed-role / service principal
    "source_ip",
    # placement
    "region",             # cloud region (cloudtrail)
    "namespace",          # k8s namespace
    "resource_id",        # instance id / bucket / pod name / service name
    "resource_type",      # AWS::EC2::Instance / pod / service / rbac / session ...
    # cross-source linkage keys (graph stage joins on these; we only surface them)
    "session_name",       # roleSessionName / IdP displayName
    "external_session_id",  # IdP authenticationContext.externalSessionId
    "assumed_role_id",    # STS assumedRoleId == later S3 caller principalId
    "shared_event_id",    # CloudTrail sharedEventID
    # raw detection signals (booleans/values lifted from the nested record)
    "tags",               # dict of resource tags (EC2) — {} if none
    "is_spot",            # bool — spot instance
    "public_ip",          # public IP string or None
    "controller_owner",   # K8s controller kind or None (None == bare-pod signal)
    "privileged",         # bool — privileged container
    "host_network",       # bool
    "service_type",       # ClusterIP | NodePort | LoadBalancer | None
    "exposed_open",       # bool — exposed to 0.0.0.0/0
    "rbac_change",        # bool — RBAC mutation
    "broad_rbac",         # bool — cluster-admin / wildcard binding
    "is_proxy",           # IdP — anonymizing proxy / VPN
    "outcome",            # SUCCESS / FAILURE / api outcome
    "read_only",          # cloudtrail readOnly
    "session_ttl",        # STS/session duration seconds (None if N/A)
    "labels",             # k8s pod/service labels dict — {} if none
    # forensic
    "raw",                # JSON string of the untouched original record
)
