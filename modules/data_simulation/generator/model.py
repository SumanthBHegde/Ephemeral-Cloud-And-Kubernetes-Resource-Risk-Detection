"""Internal semantic model used before rendering to authentic provider schemas.

An ``Event`` is a source-agnostic description of one logged action plus its
ground-truth labels. A ``Campaign`` groups events that share a ``campaign_id``
(one attack, or one coherent benign burst). The schema renderers turn each
``Event`` into an authentic CloudTrail / audit.k8s.io / IdP record; ``labels.py``
extracts the ground-truth fields into the sidecar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

# --- severity levels ---------------------------------------------------------
SEV_NONE = "none"
SEV_LOW = "low"
SEV_MEDIUM = "medium"
SEV_HIGH = "high"
SEV_CRITICAL = "critical"

# --- scenario types (also the ground-truth `scenario_type` label) ------------
SCN_CRYPTO = "crypto_burst"
SCN_EXPOSURE = "public_exposure"
SCN_IDENTITY = "identity_anomaly"
SCN_LEGIT_AUTOSCALE = "legit_autoscale"
SCN_LEGIT_CICD = "legit_cicd"
SCN_ROUTINE = "routine"

RISKY_SCENARIOS = frozenset({SCN_CRYPTO, SCN_EXPOSURE, SCN_IDENTITY})
ALL_SCENARIOS = (
    SCN_CRYPTO, SCN_EXPOSURE, SCN_IDENTITY,
    SCN_LEGIT_AUTOSCALE, SCN_LEGIT_CICD, SCN_ROUTINE,
)

# --- sources -----------------------------------------------------------------
SRC_CLOUDTRAIL = "cloudtrail"
SRC_K8S = "k8s_audit"
SRC_IDP = "idp_session"
ALL_SOURCES = (SRC_CLOUDTRAIL, SRC_K8S, SRC_IDP)

# --- timing hints consumed by timeline.py ------------------------------------
TIMING_ANY = "any"
TIMING_BUSINESS = "business"
TIMING_OFF_HOURS = "off_hours"
TIMING_FIXED = "fixed"


@dataclass
class Principal:
    """An actor. AssumedRole/IAMUser map to CloudTrail userIdentity; AWSService is
    a service principal (autoscaler, lambda); FederatedUser comes via an IdP."""
    principal_id: str
    principal_type: str            # AssumedRole | IAMUser | AWSService | FederatedUser
    arn: str
    account_id: str
    access_key_id: Optional[str] = None
    user_name: Optional[str] = None
    session_name: Optional[str] = None
    role_name: Optional[str] = None
    invoked_by: Optional[str] = None
    email: Optional[str] = None     # for IdP actors


@dataclass
class Event:
    source: str                    # one of ALL_SOURCES
    action: str                    # semantic action, e.g. "RunInstances", "pod_create"
    cohort: str
    principal: Principal
    attrs: dict[str, Any] = field(default_factory=dict)

    # timing: scenarios set rel_offset from the campaign anchor; timeline sets timestamp
    rel_offset: timedelta = timedelta(0)
    timestamp: Optional[datetime] = None

    # ground truth (copied from the owning campaign, overridable per event)
    is_risky: bool = False
    scenario_type: str = SCN_ROUTINE
    campaign_id: Optional[str] = None
    true_incident_id: Optional[str] = None
    severity: str = SEV_NONE
    anomaly_type: Optional[str] = None
    pair_id: Optional[str] = None   # ties a malicious campaign to its benign look-alike

    # authentic cross-source linkage (recoverable WITHOUT the label sidecar)
    shared_event_id: Optional[str] = None
    external_session_id: Optional[str] = None

    # filled at render time with the record's real id (eventID / auditID / uuid)
    record_id: Optional[str] = None


@dataclass
class Campaign:
    campaign_id: str
    scenario_type: str
    is_risky: bool
    severity: str
    events: list[Event] = field(default_factory=list)
    true_incident_id: Optional[str] = None
    anomaly_type: Optional[str] = None
    pair_id: Optional[str] = None
    timing: str = TIMING_ANY
    fixed_anchor: Optional[datetime] = None
    anchor: Optional[datetime] = None   # set by timeline.py

    def duration(self) -> timedelta:
        if not self.events:
            return timedelta(0)
        offs = [e.rel_offset for e in self.events]
        return max(offs) - min(offs)
