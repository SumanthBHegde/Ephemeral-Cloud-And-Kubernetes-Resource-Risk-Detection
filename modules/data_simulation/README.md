# Stage Zero — Synthetic Telemetry Generator + Real-Time Replay

Stage Zero produces the labeled, cross-source-linked log streams the detection pipeline
(Stages 1+) ingests. It emits **authentic nested** AWS CloudTrail, Kubernetes
`audit.k8s.io`, and Okta-style IdP/session records as JSON Lines, with a **separate
ground-truth label sidecar**, and a **replay streamer** so the pipeline can consume the
data "live".

Everything is built **ground-truth-first**: the incident/campaign structure is created
first and every record + label is derived from it (never the other way around).

## Quick start

```bash
pip install -r ../../requirements.txt       # numpy, PyYAML, pytest (run from repo root)

# 1) generate the dataset (writes to data/raw/ at the repo root)
python -m modules.data_simulation.generator.build

# 2) validate it (anomaly mix, confusability, linkage, schema, canonical incidents)
python modules/data_simulation/validate.py

# 3) replay it as a live stream
python modules/data_simulation/replay/stream.py --instant | head
python modules/data_simulation/replay/stream.py --speed 60 --limit 100
```

## Outputs (`data/raw/`)

| File | Contents |
|---|---|
| `cloudtrail.jsonl` | EC2 / STS / S3 CloudTrail records (STS = the in-feed identity half) |
| `k8s_audit.jsonl` | `audit.k8s.io/v1` pod / service / RBAC events |
| `idp_session.jsonl` | Okta-style federated login / SSO / token-grant events |
| `labels.jsonl` | Ground-truth, keyed by record id (`eventID`/`auditID`/`uuid`) |
| `data_dictionary.md` | Auto-generated field reference + realized stats |

Raw records stay **byte-authentic** — all labels live only in the sidecar, joined by
`record_id`.

## What makes the data hard (by design)

- **Confusability:** every malicious campaign ships with a benign look-alike (`pair_id`)
  that matches it on volume and timing, differing only in tag completeness, controller
  ownership, off-hours behaviour, or session lineage.
- **Cross-source linkage:** an attack's events share a `campaign_id` *and* are recoverable
  from authentic fields alone — STS `assumedRoleUser.assumedRoleId` == the S3 caller
  `userIdentity.principalId`; IdP `externalSessionId` threads a federated login to its STS
  session.
- **Four canonical incidents** are always present: INC-A crypto burst, INC-B exposed debug
  pod, INC-C compromised-session→PII, INC-D autoscaler-noise burying a real cred-abuse alert.

## Configuration

All knobs live in [config/simulation.yaml](config/simulation.yaml): `seed`, time span,
per-source volumes, the anomaly mix, and the cohort baselines. Change the seed (or anything
else) and the whole dataset changes deterministically.

## Replay envelope

The streamer adds two non-invasive keys to each emitted line so a consumer knows the
schema and order: `_source` (`cloudtrail`/`k8s_audit`/`idp_session`) and `_seq`. The stored
files are untouched. `--speed N` paces inter-event gaps at N× real-time (`--instant` = no
sleep); `--max-gap` caps any single sleep so demos stay snappy.

## Layout

```
generator/
  schemas/    authentic CloudTrail / audit.k8s.io / IdP renderers + dispatch
  scenarios/  one module per scenario_type (+ canonical incidents)
  cohorts.py  behavioural baselines    context.py  deterministic RNG + identity factories
  timeline.py diurnal placement        labels.py   sidecar    build.py  orchestrator
replay/stream.py   merge + paced stdout stream
validate.py        dataset gate (exit 0/1)
```

Tests: `pytest tests/test_stage0.py` (determinism, mix, replay ordering, canonical incidents).
