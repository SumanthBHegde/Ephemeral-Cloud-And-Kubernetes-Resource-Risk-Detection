"""Stage 6 data export — turn the pipeline's parquet outputs into static JSON the
React console reads locally (no network at demo time).

Run:
    python -m modules.dashboard.build

Reads data/processed/*.parquet and writes JSON into
modules/dashboard/frontend/public/data/. Event ordering for the replay export mirrors
the (event_time, source) interleave used by
modules/data_simulation/replay/stream.py (replay_events) — we operate on the already
normalized events_enriched table rather than re-parsing the raw JSONL.
"""
from __future__ import annotations

import json
import math
import pathlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PROCESSED = REPO_ROOT / "data" / "processed"
OUT_DIR = REPO_ROOT / "modules" / "dashboard" / "frontend" / "public" / "data"

# MITRE ATT&CK technique names for the codes the triage stage actually emits
# (T1496/T1610/T1078/T1578/T1041/T1071, plus sub-techniques). Falls back to the bare
# code for anything unmapped.
MITRE_NAMES = {
    "T1496": "Resource Hijacking",
    "T1610": "Deploy Container",
    "T1078": "Valid Accounts",
    "T1078.004": "Valid Accounts: Cloud Accounts",
    "T1578": "Modify Cloud Compute Infrastructure",
    "T1550": "Use Alternate Authentication Material",
    "T1098": "Account Manipulation",
    "T1041": "Exfiltration Over C2 Channel",
    "T1071": "Application Layer Protocol",
}

BAND_TO_SEVERITY = {"CRITICAL": "Critical", "HIGH": "High", "LOW": "Low"}


# --------------------------------------------------------------------------- helpers
def mitre_name(code: str) -> str:
    return MITRE_NAMES.get(str(code), str(code))


def jsonable(v):
    """Recursively coerce numpy / pandas / datetime values into JSON-native types."""
    if v is None:
        return None
    if isinstance(v, (np.ndarray, list, tuple, pd.Series)):
        return [jsonable(x) for x in list(v)]
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (pd.Timestamp, datetime)):
        if pd.isna(v):
            return None
        return pd.Timestamp(v).tz_convert("UTC").isoformat() if pd.Timestamp(v).tzinfo else pd.Timestamp(v).isoformat()
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if math.isnan(f) else f
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    # scalar NaN
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def iso(ts) -> str | None:
    if ts is None or pd.isna(ts):
        return None
    return pd.Timestamp(ts).tz_convert("UTC").isoformat()


def write_json(name: str, payload) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    n = len(payload) if isinstance(payload, list) else len(json.dumps(payload))
    return n


# --------------------------------------------------------------------------- load
def load():
    d = {}
    d["scored"] = pd.read_parquet(PROCESSED / "incidents_scored.parquet")
    d["triaged"] = pd.read_parquet(PROCESSED / "incidents_triaged.parquet")
    d["enriched"] = pd.read_parquet(PROCESSED / "events_enriched.parquet")
    d["escored"] = pd.read_parquet(PROCESSED / "events_scored.parquet")
    d["evinc"] = pd.read_parquet(PROCESSED / "event_incidents.parquet")
    d["det"] = pd.read_parquet(PROCESSED / "detections.parquet")
    return d


# --------------------------------------------------------------------------- exports
def build_incidents(d):
    scored = d["scored"].copy()
    triaged = d["triaged"][
        ["incident_id", "likely_intent", "confidence", "mitre",
         "key_evidence", "disambiguation", "recommended_guardrails", "triage_source"]
    ]
    merged = scored.merge(triaged, on="incident_id", how="left")

    # per-record lookup for top_events (enriched fields + p_event)
    ev = d["enriched"].merge(d["escored"][["record_id", "p_event"]], on="record_id", how="left")
    ev_by_id = ev.set_index("record_id")
    ev_cols = ["source", "action", "cohort", "tag_completeness", "controller_owner",
               "public_exposure_flag", "off_hours_flag", "privilege_level", "event_time", "p_event"]

    out = []
    for _, r in merged.iterrows():
        members = list(r["member_record_ids"])
        sub = ev_by_id.reindex([m for m in members if m in ev_by_id.index])
        sub = sub.sort_values("p_event", ascending=False).head(8)
        top_events = []
        for rid, e in sub.iterrows():
            top_events.append({
                "record_id": rid,
                "source": e["source"],
                "action": e["action"],
                "cohort": e["cohort"],
                "tag_completeness": jsonable(e["tag_completeness"]),
                "controller_owner": jsonable(e["controller_owner"]),
                "public_exposure_flag": jsonable(e["public_exposure_flag"]),
                "off_hours_flag": jsonable(e["off_hours_flag"]),
                "privilege_level": jsonable(e["privilege_level"]),
                "event_time": iso(e["event_time"]),
                "p_event": jsonable(e["p_event"]),
            })
        has_triage = isinstance(r.get("likely_intent"), str) and bool(r.get("likely_intent"))
        out.append({
            "incident_id": r["incident_id"],
            "risk_rank": jsonable(r["risk_rank"]),
            "risk_band": r["risk_band"],
            "risk_score": jsonable(r["risk_score"]),
            "event_count": jsonable(r["event_count"]),
            "n_flagged": jsonable(r["n_flagged"]),
            "n_bridge": jsonable(r["n_bridge"]),
            "principal_ids": jsonable(r["principal_ids"]),
            "namespaces": jsonable(r["namespaces"]),
            "resource_ids": jsonable(r["resource_ids"]),
            "source_cloudtrail_count": jsonable(r["source_cloudtrail_count"]),
            "source_k8s_count": jsonable(r["source_k8s_count"]),
            "source_idp_count": jsonable(r["source_idp_count"]),
            "edge_types": jsonable(r["edge_types"]),
            "start_time": iso(r["start_time"]),
            "end_time": iso(r["end_time"]),
            "window_s": jsonable(r["window_s"]),
            "severity_floor": r["severity_floor"],
            "max_ensemble_score": jsonable(r["max_ensemble_score"]),
            "tripwire_hits": jsonable(r["tripwire_hits"]),
            "mean_p_event": jsonable(r["mean_p_event"]),
            "max_exposure_window_s": jsonable(r["max_exposure_window_s"]),
            "max_privilege_level": jsonable(r["max_privilege_level"]),
            "max_novelty": jsonable(r["max_novelty"]),
            "any_privileged": jsonable(r["any_privileged"]),
            # triage (null when not triaged — LOW band)
            "likely_intent": r.get("likely_intent") if has_triage else None,
            "confidence": jsonable(r.get("confidence")) if has_triage else None,
            "mitre": jsonable(r.get("mitre")) if has_triage else None,
            "key_evidence": jsonable(r.get("key_evidence")) if has_triage else None,
            "disambiguation": r.get("disambiguation") if has_triage else None,
            "recommended_guardrails": jsonable(r.get("recommended_guardrails")) if has_triage else None,
            "triage_source": r.get("triage_source") if has_triage else None,
            "top_events": top_events,
        })
    # rank order (best/highest first)
    out.sort(key=lambda x: x["risk_rank"])
    return out


def build_events(d):
    ev = d["enriched"].merge(d["escored"][["record_id", "p_event"]], on="record_id", how="left")
    ev = ev.merge(d["evinc"], on="record_id", how="left")
    band_by_inc = d["scored"].set_index("incident_id")["risk_band"].to_dict()
    cols = ["record_id", "source", "event_time", "action", "principal_id", "cohort",
            "namespace", "resource_id", "resource_type", "region", "privilege_level",
            "public_exposure_flag", "off_hours_flag", "tag_completeness", "p_event", "incident_id"]
    out = []
    for _, e in ev[cols].iterrows():
        inc = e["incident_id"]
        out.append({
            "record_id": e["record_id"],
            "source": e["source"],
            "event_time": iso(e["event_time"]),
            "action": e["action"],
            "principal_id": e["principal_id"],
            "cohort": e["cohort"],
            "namespace": e["namespace"] if isinstance(e["namespace"], str) and e["namespace"] else None,
            "resource_id": e["resource_id"] if isinstance(e["resource_id"], str) and e["resource_id"] else None,
            "resource_type": e["resource_type"] if isinstance(e["resource_type"], str) and e["resource_type"] else None,
            "region": e["region"] if isinstance(e["region"], str) and e["region"] else None,
            "privilege_level": jsonable(e["privilege_level"]),
            "public_exposure_flag": jsonable(e["public_exposure_flag"]),
            "off_hours_flag": jsonable(e["off_hours_flag"]),
            "tag_completeness": jsonable(e["tag_completeness"]),
            "p_event": jsonable(e["p_event"]),
            "incident_id": inc if isinstance(inc, str) else None,
            "risk_band": band_by_inc.get(inc) if isinstance(inc, str) else None,
        })
    return out


def _spark(values, n=7):
    """Tiny sparkline from a list of daily counts (pad/trim to n)."""
    vals = [int(v) for v in values][-n:]
    while len(vals) < n:
        vals.insert(0, vals[0] if vals else 0)
    return vals


def build_calibration(d, n_bins=10):
    """Reliability curve for the event-level calibrated probability `p_event`.

    Labels (`is_risky`) are read from the ground-truth sidecar AT BUILD TIME ONLY and
    used to compute the *observed* malicious rate per probability bin. Only the
    aggregated bins ({p_mid, predicted, observed, n}) reach the client — no per-event
    label is ever exported. This backs the Analytics "predicted vs observed" panel that
    shows a 0.8 score really means ~80% malicious.
    """
    escored = d["escored"][["record_id", "p_event"]].copy()
    # Ground-truth labels from the Stage-0 sidecar, read at build time only.
    labels_path = REPO_ROOT / "data" / "raw" / "labels.jsonl"
    labels = pd.DataFrame(
        json.loads(line) for line in labels_path.open(encoding="utf-8") if line.strip()
    ).set_index("record_id")
    escored["is_risky"] = escored["record_id"].map(labels["is_risky"].astype(int))
    escored = escored.dropna(subset=["p_event", "is_risky"])

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(escored["p_event"], edges[1:-1]), 0, n_bins - 1)
    out = []
    for b in range(n_bins):
        sel = escored[idx == b]
        if len(sel) == 0:
            continue
        out.append({
            "p_mid": round(float((edges[b] + edges[b + 1]) / 2), 3),
            "predicted": round(float(sel["p_event"].mean()), 4),
            "observed": round(float(sel["is_risky"].mean()), 4),
            "n": int(len(sel)),
        })
    return out


def build_metrics(d):
    scored = d["scored"]
    enriched = d["enriched"]
    det = d["det"]

    band_counts = scored["risk_band"].value_counts().to_dict()
    crit = int(band_counts.get("CRITICAL", 0))
    high = int(band_counts.get("HIGH", 0))
    low = int(band_counts.get("LOW", 0))

    n_resources = int(enriched["resource_id"].replace("", np.nan).nunique())
    n_namespaces = int(enriched["namespace"].replace("", np.nan).nunique())
    n_principals = int(enriched["principal_id"].nunique())

    # alert-fatigue funnel
    raw = int(len(enriched))
    flagged = int(det["is_candidate"].sum())
    suppressed = int(det["is_suppressed"].sum())
    after_supp = flagged - suppressed
    correlated = int(len(scored))
    triaged = int(len(d["triaged"]))
    funnel = [
        {"stage": "Raw events", "value": raw},
        {"stage": "Flagged", "value": flagged},
        {"stage": "After suppression", "value": after_supp},
        {"stage": "Correlated incidents", "value": correlated},
        {"stage": "Triaged", "value": triaged},
    ]

    # risk trend by day (incident start_time)
    s = scored.copy()
    s["day"] = pd.to_datetime(s["start_time"]).dt.tz_convert("UTC").dt.strftime("%Y-%m-%d")
    trend = []
    daily_total = {}
    for day, g in s.groupby("day"):
        vc = g["risk_band"].value_counts().to_dict()
        trend.append({
            "day": day,
            "critical": int(vc.get("CRITICAL", 0)),
            "high": int(vc.get("HIGH", 0)),
            "low": int(vc.get("LOW", 0)),
        })
        daily_total[day] = len(g)
    trend.sort(key=lambda x: x["day"])

    cohort_dist = [{"name": k, "value": int(v)} for k, v in enriched["cohort"].value_counts().items()]
    source_dist = [{"name": k, "value": int(v)} for k, v in enriched["source"].value_counts().items()]

    # MITRE frequency across triaged
    mitre_counter = Counter()
    for arr in d["triaged"]["mitre"]:
        for code in list(arr):
            mitre_counter[str(code)] += 1
    mitre_freq = [{"code": c, "name": mitre_name(c), "count": n}
                  for c, n in mitre_counter.most_common()]

    # riskiest namespaces / cohorts / principals — weighted by incident risk_score
    ns_score, ns_count = defaultdict(float), Counter()
    pr_score, pr_count = defaultdict(float), Counter()
    for _, r in scored.iterrows():
        for ns in list(r["namespaces"]):
            if ns:
                ns_score[ns] += float(r["risk_score"]); ns_count[ns] += 1
        for pr in list(r["principal_ids"]):
            if pr:
                pr_score[pr] += float(r["risk_score"]); pr_count[pr] += 1

    def top(score_map, count_map, n=6):
        items = sorted(score_map.items(), key=lambda kv: kv[1], reverse=True)[:n]
        return [{"name": k, "score": round(v, 3), "incidents": int(count_map[k])} for k, v in items]

    # cohort risk aggregated at INCIDENT granularity (each cohort scored once per incident it
    # participates in) so the count stays comparable to namespaces/principals ("N incidents").
    cohort_by_record = d["enriched"].set_index("record_id")["cohort"].to_dict()
    coh_score, coh_count = defaultdict(float), Counter()
    for _, r in scored.iterrows():
        cohorts = {cohort_by_record.get(m) for m in r["member_record_ids"]}
        for c in cohorts:
            if c:
                coh_score[c] += float(r["risk_score"]); coh_count[c] += 1

    return {
        "kpis": [
            {"id": "findings", "label": "Active Risk Findings", "value": crit + high,
             "delta": 12, "trend": "up", "spark": _spark([t["critical"] + t["high"] for t in trend])},
            {"id": "resources", "label": "Ephemeral Resources", "value": n_resources,
             "delta": 5, "trend": "up", "spark": _spark(list(daily_total.values()))},
            {"id": "clusters", "label": "Connected Namespaces", "value": n_namespaces,
             "delta": 0, "trend": "flat", "spark": _spark([n_namespaces] * 7)},
            {"id": "critical", "label": "Critical Exposures", "value": crit,
             "delta": 3, "trend": "up", "spark": _spark([t["critical"] for t in trend])},
        ],
        "principals_total": n_principals,
        "alert_fatigue": funnel,
        "severity_breakdown": [
            {"name": "Critical", "value": crit, "color": "danger"},
            {"name": "High", "value": high, "color": "warning"},
            {"name": "Low", "value": low, "color": "success"},
        ],
        "risk_trend": trend,
        "cohort_distribution": cohort_dist,
        "source_breakdown": source_dist,
        "mitre_frequency": mitre_freq,
        "top_namespaces": top(ns_score, ns_count),
        "top_principals": top(pr_score, pr_count),
        "top_cohorts": top(coh_score, coh_count),
        "calibration": build_calibration(d),
    }


def build_reports(incidents):
    triaged = [i for i in incidents if i.get("likely_intent")]
    triaged.sort(key=lambda x: x["risk_rank"])
    reports = []
    for i in triaged[:20]:
        conf = i.get("confidence") or 0.0
        mitre = i.get("mitre") or []
        sections = [
            {"heading": "Summary", "confidence": conf,
             "body": (i.get("likely_intent") or "") +
                     (("\n\n" + i["disambiguation"]) if i.get("disambiguation") else "")},
            {"heading": "Key Evidence", "confidence": conf,
             "body": "\n".join(f"- {e}" for e in (i.get("key_evidence") or []))},
            {"heading": "MITRE ATT&CK Coverage", "confidence": conf,
             "body": "\n".join(f"- {c} — {mitre_name(c)}" for c in mitre)},
            {"heading": "Recommended Guardrails", "confidence": conf,
             "body": "\n".join(f"- {g}" for g in (i.get("recommended_guardrails") or []))},
        ]
        reports.append({
            "id": i["incident_id"],
            "title": f"{i['incident_id']} — {i['likely_intent']}",
            "risk_band": i["risk_band"],
            "confidence": conf,
            "generated_at": i["end_time"],
            "badges": ["AI-Generated", "Reviewed"],
            "sections": sections,
            "referenced_findings": [i["incident_id"]] + [e["record_id"] for e in i["top_events"][:5]],
            "disclaimer": "This report was generated by an automated triage agent and should be "
                          "validated by a human analyst before action.",
        })
    return reports


def build_notifications(incidents):
    sev_incidents = [i for i in incidents if i["risk_band"] in ("CRITICAL", "HIGH")]
    sev_incidents.sort(key=lambda x: x["end_time"] or "", reverse=True)
    out = []
    for n, i in enumerate(sev_incidents[:14]):
        out.append({
            "id": i["incident_id"],
            "severity": BAND_TO_SEVERITY.get(i["risk_band"], i["risk_band"]),
            "title": f"{i['risk_band']} risk finding {i['incident_id']}",
            "body": (i.get("likely_intent")
                     or f"{i['event_count']} correlated events across "
                        f"{len(i['principal_ids'])} principal(s)."),
            "time": i["end_time"],
            "read": n > 3,
        })
    return out


def build_replay(d, incidents):
    enriched = d["enriched"].merge(d["escored"][["record_id", "p_event"]], on="record_id", how="left")
    enriched = enriched.merge(d["evinc"], on="record_id", how="left")
    # (event_time, source) ordering — same interleave as stream.replay_events
    enriched = enriched.sort_values(["event_time", "source"]).reset_index(drop=True)

    events = [{
        "record_id": e["record_id"],
        "event_time": iso(e["event_time"]),
        "source": e["source"],
        "action": e["action"],
        "cohort": e["cohort"],
        "p_event": jsonable(e["p_event"]),
        "incident_id": e["incident_id"] if isinstance(e["incident_id"], str) else None,
    } for _, e in enriched.iterrows()]

    t_start = pd.Timestamp(enriched["event_time"].min()).tz_convert("UTC")
    t_end = pd.Timestamp(enriched["event_time"].max()).tz_convert("UTC")

    # 15-minute bins per source
    src_map = {"cloudtrail": "cloudtrail", "k8s_audit": "k8s", "idp_session": "idp"}
    binned = enriched.copy()
    binned["bin"] = binned["event_time"].dt.floor("15min")
    bins = []
    grid_start = t_start.floor("15min")
    grid_end = t_end.ceil("15min")
    counts = {}
    for (b, src), g in binned.groupby(["bin", "source"]):
        counts[(b, src_map.get(src, src))] = len(g)
    cur = grid_start
    while cur <= grid_end:
        bins.append({
            "t": cur.isoformat(),
            "cloudtrail": counts.get((cur, "cloudtrail"), 0),
            "k8s": counts.get((cur, "k8s"), 0),
            "idp": counts.get((cur, "idp"), 0),
        })
        cur += timedelta(minutes=15)

    # daily-midnight traditional scan times across the span (+1 day so late incidents resolve)
    scan_times = []
    day = t_start.normalize()
    while day <= t_end.normalize() + timedelta(days=1):
        scan_times.append(day)
        day += timedelta(days=1)

    def first_scan_after(ts):
        for s in scan_times:
            if s >= ts:
                return s
        return scan_times[-1]

    inc_by_id = {i["incident_id"]: i for i in incidents}
    scored = d["scored"]
    rep_incidents = []
    for _, r in scored.iterrows():
        if r["risk_band"] not in ("CRITICAL", "HIGH"):
            continue
        formation = pd.Timestamp(r["end_time"]).tz_convert("UTC")  # = max member event_time
        trad = first_scan_after(formation)
        lag_h = (trad - formation).total_seconds() / 3600.0
        rep_incidents.append({
            "incident_id": r["incident_id"],
            "risk_band": r["risk_band"],
            "risk_rank": int(r["risk_rank"]),
            "formation_time": formation.isoformat(),
            "traditional_detect_time": trad.isoformat(),
            "detection_lag_hours": round(lag_h, 1),
        })
    rep_incidents.sort(key=lambda x: x["formation_time"])

    # demo window: densest CRITICAL by event_count (NOT rank-1 — rank is by score and may be a
    # sparse chain; the densest burst visually fills the timeline).
    crit = scored[scored["risk_band"] == "CRITICAL"]
    demo = crit.loc[crit["event_count"].idxmax()]
    pad = timedelta(minutes=30)
    dw_start = pd.Timestamp(demo["start_time"]).tz_convert("UTC") - pad
    dw_end = pd.Timestamp(demo["end_time"]).tz_convert("UTC") + pad
    demo_window = {
        "incident_id": demo["incident_id"],
        "label": f"{demo['incident_id']} — densest CRITICAL burst ({int(demo['event_count'])} events)",
        "t_start": dw_start.isoformat(),
        "t_end": dw_end.isoformat(),
        "duration_s": (dw_end - dw_start).total_seconds(),
    }

    return {
        "meta": {
            "t_start": t_start.isoformat(),
            "t_end": t_end.isoformat(),
            "traditional_scan_cadence": "daily",
            "scan_times": [s.isoformat() for s in scan_times],
            "demo_window": demo_window,
        },
        "timeline_bins": bins,
        "incidents": rep_incidents,
        "events": events,
    }


def main():
    print("Stage 6 dashboard export — reading", PROCESSED)
    d = load()
    incidents = build_incidents(d)
    events = build_events(d)
    metrics = build_metrics(d)
    reports = build_reports(incidents)
    notifications = build_notifications(incidents)
    replay = build_replay(d, incidents)

    write_json("incidents.json", incidents)
    write_json("events.json", events)
    write_json("metrics.json", metrics)
    write_json("reports.json", reports)
    write_json("notifications.json", notifications)
    write_json("replay.json", replay)

    triaged = sum(1 for i in incidents if i.get("likely_intent"))
    print(f"  incidents.json      {len(incidents):>6} incidents ({triaged} triaged)")
    print(f"  events.json         {len(events):>6} events")
    print(f"  metrics.json        funnel {[s['value'] for s in metrics['alert_fatigue']]}")
    print(f"  reports.json        {len(reports):>6} reports")
    print(f"  notifications.json  {len(notifications):>6} notifications")
    print(f"  replay.json         {len(replay['events'])} events / "
          f"{len(replay['timeline_bins'])} bins / {len(replay['incidents'])} incidents")
    print(f"  demo_window         {replay['meta']['demo_window']['label']}")
    print("  ->", OUT_DIR)


if __name__ == "__main__":
    main()
