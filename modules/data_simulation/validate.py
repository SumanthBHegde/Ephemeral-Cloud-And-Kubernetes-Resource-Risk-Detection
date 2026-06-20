"""Validate a generated Stage Zero dataset.

Asserts the properties the whole project leans on: honest anomaly mix, real
confusability (every malicious campaign has a volume-matched benign twin), recoverable
cross-source linkage (without the label sidecar), schema validity, label join integrity,
and presence/shape of the four canonical incidents.

Run:  python modules/data_simulation/validate.py [--out DIR]
Exit code 0 = all checks pass, 1 = one or more failed.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from modules.data_simulation.generator.build import load_config  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "data" / "raw"

_SRC_FILE = {"cloudtrail": "cloudtrail.jsonl", "k8s_audit": "k8s_audit.jsonl",
             "idp_session": "idp_session.jsonl"}
_ID_FIELD = {"cloudtrail": "eventID", "k8s_audit": "auditID", "idp_session": "uuid"}
_TS_FIELD = {"cloudtrail": "eventTime", "k8s_audit": "requestReceivedTimestamp",
             "idp_session": "published"}
_OFF_HOURS = {0, 1, 2, 3, 4, 5, 22, 23}
_PAIRED_ANOMALIES = {"resource_hijacking", "public_exposure", "identity_session_abuse"}


class Checker:
    def __init__(self):
        self.failures = 0

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        mark = "PASS" if ok else "FAIL"
        line = f"[{mark}] {name}"
        if detail:
            line += f" -- {detail}"
        print(line)
        if not ok:
            self.failures += 1


def _read_jsonl(path: pathlib.Path) -> list[dict]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _hour(value: str) -> int:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).hour


def _required(rec: dict, keys) -> bool:
    return all(k in rec for k in keys)


def validate(out_dir: pathlib.Path, cfg: dict) -> int:
    c = Checker()
    records = {src: _read_jsonl(out_dir / fname) for src, fname in _SRC_FILE.items()}
    labels = _read_jsonl(out_dir / "labels.jsonl")

    # index: record_id -> (source, record, label)
    label_by_id = {lab["record_id"]: lab for lab in labels}
    idx = {}
    for src, recs in records.items():
        for rec in recs:
            rid = rec[_ID_FIELD[src]]
            idx[rid] = (src, rec, label_by_id.get(rid))

    total = sum(len(r) for r in records.values())

    # --- 1. label join integrity ------------------------------------------
    rec_ids = [rec[_ID_FIELD[src]] for src, recs in records.items() for rec in recs]
    c.check("record ids unique", len(rec_ids) == len(set(rec_ids)),
            f"{len(rec_ids)} ids, {len(set(rec_ids))} unique")
    c.check("labels join 1:1 with records",
            len(labels) == total and set(rec_ids) == set(label_by_id),
            f"{total} records, {len(labels)} labels")

    # --- 2. anomaly mix within tolerance ----------------------------------
    tol = cfg["tolerance"]
    scn = Counter(lab["scenario_type"] for lab in labels)
    mix_ok = True
    details = []
    for k, target in cfg["anomaly_mix"].items():
        realized = scn.get(k, 0) / total
        if abs(realized - target) > tol:
            mix_ok = False
            details.append(f"{k}={realized:.2%}(target {target:.2%})")
    c.check(f"anomaly mix within +/-{tol:.1%}", mix_ok, ", ".join(details) or "all within tolerance")

    # --- 3. per-source volumes near targets -------------------------------
    vols_ok = all(len(records[s]) >= 0.9 * cfg["volumes"][s] for s in cfg["volumes"])
    c.check("per-source volumes >= 90% of target", vols_ok,
            ", ".join(f"{s}={len(records[s])}/{cfg['volumes'][s]}" for s in cfg["volumes"]))

    # --- build campaign view from labels ----------------------------------
    campaigns: dict[str, dict] = {}
    for lab in labels:
        cid = lab["campaign_id"]
        camp = campaigns.setdefault(cid, {
            "risky": False, "scenario": lab["scenario_type"], "anomaly": None,
            "pair": lab["pair_id"], "incident": None, "sources": set(),
            "actions": Counter()})
        camp["risky"] |= bool(lab["is_risky"])
        camp["sources"].add(lab["source"])
        camp["actions"][lab["action"]] += 1
        if lab["anomaly_type"]:
            camp["anomaly"] = lab["anomaly_type"]
        if lab["true_incident_id"]:
            camp["incident"] = lab["true_incident_id"]

    # --- 4. confusability: every paired-scenario risky campaign has a benign twin
    pairs = defaultdict(list)
    for camp in campaigns.values():
        if camp["pair"]:
            pairs[camp["pair"]].append(camp)
    pairs_ok = all(any(m["risky"] for m in members) and any(not m["risky"] for m in members)
                   for members in pairs.values())
    c.check("every pair has a risky + benign side", pairs_ok, f"{len(pairs)} pairs")

    unpaired = [cid for cid, camp in campaigns.items()
                if camp["risky"] and camp["anomaly"] in _PAIRED_ANOMALIES and not camp["pair"]]
    c.check("all paired-scenario malicious campaigns are paired", not unpaired,
            f"{len(unpaired)} unpaired")

    # crypto bursts: malicious vs benign RunInstances volume parity (timing/size look-alike)
    parity_ok = True
    for members in pairs.values():
        risky = [m for m in members if m["risky"]]
        if not risky or risky[0]["anomaly"] != "resource_hijacking":
            continue
        r = sum(m["actions"].get("RunInstances", 0) for m in risky)
        b = sum(m["actions"].get("RunInstances", 0) for m in members if not m["risky"])
        if abs(r - b) > max(2, 0.3 * r):
            parity_ok = False
    c.check("crypto bursts size-matched to benign twin", parity_ok)

    # --- 5. cross-source linkage recoverable WITHOUT the sidecar ----------
    assumed_ids, getobj_principals = set(), set()
    for src, rec, lab in idx.values():
        if src != "cloudtrail":
            continue
        if rec["eventName"] in ("AssumeRole", "AssumeRoleWithWebIdentity"):
            assumed_ids.add(rec["responseElements"]["assumedRoleUser"]["assumedRoleId"])
        elif rec["eventName"] == "GetObject":
            pid = rec.get("userIdentity", {}).get("principalId")
            if pid:
                getobj_principals.add(pid)
    linkable = assumed_ids & getobj_principals
    c.check("STS assumedRoleId links to S3 GetObject principalId", bool(linkable),
            f"{len(linkable)} linkable sessions")

    # --- 6. schema validity (sample-and-assert all) -----------------------
    ct_ok = all(_required(r, ("eventVersion", "eventID", "eventTime", "eventSource",
                              "eventName", "userIdentity", "awsRegion", "recipientAccountId"))
                for r in records["cloudtrail"])
    k8_ok = all(r.get("kind") == "Event" and r.get("apiVersion") == "audit.k8s.io/v1"
                and _required(r, ("auditID", "verb", "user", "objectRef",
                                  "requestReceivedTimestamp", "stageTimestamp"))
                for r in records["k8s_audit"])
    idp_ok = all(_required(r, ("uuid", "published", "eventType", "actor",
                               "authenticationContext", "outcome"))
                 for r in records["idp_session"])
    c.check("cloudtrail records schema-valid", ct_ok)
    c.check("k8s_audit records schema-valid", k8_ok)
    c.check("idp_session records schema-valid", idp_ok)

    # --- 7. canonical incidents present and correctly shaped --------------
    inc = defaultdict(list)
    for src, rec, lab in idx.values():
        if lab and lab["true_incident_id"]:
            inc[lab["true_incident_id"]].append((src, rec, lab))
    c.check("all four canonical incidents present",
            all(inc.get(i) for i in ("INC-A", "INC-B", "INC-C", "INC-D")),
            ", ".join(f"{i}={len(inc.get(i, []))}" for i in ("INC-A", "INC-B", "INC-C", "INC-D")))

    # INC-A: off-hours, untagged, spot RunInstances burst
    a_runs = [rec for src, rec, lab in inc["INC-A"]
              if src == "cloudtrail" and rec["eventName"] == "RunInstances"]
    a_ok = (len(a_runs) >= 20
            and all("tagSpecificationSet" not in rec["requestParameters"] for rec in a_runs)
            and all(rec["requestParameters"].get("instanceMarketOptions", {}).get("marketType")
                    == "spot" for rec in a_runs)
            and all(_hour(rec["eventTime"]) in _OFF_HOURS for rec in a_runs))
    c.check("INC-A is an off-hours untagged spot burst", a_ok, f"{len(a_runs)} RunInstances")

    # INC-B: bare (no ownerReferences) privileged pod + NodePort 0.0.0.0/0
    b_pods = [rec for src, rec, lab in inc["INC-B"]
              if src == "k8s_audit" and rec["objectRef"]["resource"] == "pods"
              and rec["verb"] == "create"]
    b_svcs = [rec for src, rec, lab in inc["INC-B"]
              if src == "k8s_audit" and rec["objectRef"]["resource"] == "services"]
    b_ok = (any("ownerReferences" not in rec["requestObject"]["metadata"]
                and rec["requestObject"]["spec"]["containers"][0]["securityContext"]["privileged"]
                for rec in b_pods)
            and any(rec["requestObject"]["spec"]["type"] == "NodePort"
                    and rec["requestObject"]["metadata"].get("annotations", {})
                    .get("sim.exposure/source-ranges") == "0.0.0.0/0" for rec in b_svcs))
    c.check("INC-B is a bare privileged pod exposed via NodePort 0.0.0.0/0", b_ok)

    # INC-C: spans IdP + CloudTrail, PII read, joinable chain
    c_sources = set().union(*[s for cid, camp in campaigns.items()
                              if camp["incident"] == "INC-C" for s in [camp["sources"]]]) \
        if any(camp["incident"] == "INC-C" for camp in campaigns.values()) else set()
    c_assumed = {rec["responseElements"]["assumedRoleUser"]["assumedRoleId"]
                 for src, rec, lab in inc["INC-C"]
                 if src == "cloudtrail" and rec["eventName"] == "AssumeRoleWithWebIdentity"}
    c_getpr = {rec["userIdentity"]["principalId"] for src, rec, lab in inc["INC-C"]
               if src == "cloudtrail" and rec["eventName"] == "GetObject"}
    c_ok = ("idp_session" in c_sources and "cloudtrail" in c_sources
            and bool(c_assumed & c_getpr))
    c.check("INC-C spans IdP->STS->S3 with a joinable session", c_ok,
            f"sources={sorted(c_sources)}")

    # INC-D: a real credential-abuse alert (cluster-admin binding) inside the burst window
    d_ok = (any(lab["anomaly_type"] == "credential_abuse" for src, rec, lab in inc["INC-D"])
            and any(src == "k8s_audit" and rec["objectRef"]["resource"] == "clusterrolebindings"
                    and rec["requestObject"]["roleRef"]["name"] == "cluster-admin"
                    for src, rec, lab in inc["INC-D"]))
    # and a large benign burst exists (the noise that buries it)
    max_burst = max((camp["actions"].get("pod_create", 0) for camp in campaigns.values()
                     if camp["scenario"] == "legit_autoscale"), default=0)
    c.check("INC-D embeds a real cred-abuse alert; large noise burst exists",
            d_ok and max_burst >= 40, f"max autoscale burst={max_burst}")

    print()
    if c.failures:
        print(f"VALIDATION FAILED: {c.failures} check(s) failed.")
    else:
        print("VALIDATION PASSED: all checks green.")
    return 1 if c.failures else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Validate a Stage Zero dataset")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="dir with generated artifacts")
    ap.add_argument("--config", default=None, help="path to simulation.yaml")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    return validate(pathlib.Path(args.out), cfg)


if __name__ == "__main__":
    raise SystemExit(main())
