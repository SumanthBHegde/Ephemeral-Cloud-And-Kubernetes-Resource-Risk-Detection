"""Build the ground-truth label sidecar (kept out of the raw records).

One row per event, keyed by the record's authentic id (CloudTrail eventID /
K8s auditID / IdP uuid), so the pipeline can join labels for evaluation while the
raw log files stay byte-authentic.
"""
from __future__ import annotations

from modules.data_simulation.generator.model import Event
from modules.data_simulation.generator.util import iso_ms

ID_FIELD = {"cloudtrail": "eventID", "k8s_audit": "auditID", "idp_session": "uuid"}


def build_labels(events: list[Event]) -> list[dict]:
    rows = []
    for ev in events:
        rows.append({
            "record_id": ev.record_id,
            "id_field": ID_FIELD[ev.source],
            "source": ev.source,
            "action": ev.action,
            "timestamp": iso_ms(ev.timestamp),
            "is_risky": int(ev.is_risky),
            "scenario_type": ev.scenario_type,
            "cohort": ev.cohort,
            "campaign_id": ev.campaign_id,
            "true_incident_id": ev.true_incident_id,
            "severity": ev.severity,
            "anomaly_type": ev.anomaly_type,
            "pair_id": ev.pair_id,
        })
    return rows
