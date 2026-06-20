# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Read [context.md](context.md) first.** It is the single source of truth for project *progress* —
what has been built, decided, and verified, in chronological order, and what to do next. This file
covers architecture/conventions; context.md covers history and current state.

**Update context.md at the end of every conversation/session that changes the project** — append a
new dated entry to its "Chronological history" section (don't rewrite history, add to it), and refresh
its "Current status" table if a module's status changed. Do this even for small changes; an out-of-date
context.md is worse than no context.md because the next session will trust it.

## Repository status

This repo is building a near-real-time detection pipeline for ephemeral cloud/Kubernetes risk, as a
hackathon submission. **Stages Zero–Four are complete and verified** (see context.md for the full
chronology and metrics) — Stage Zero (data_simulation), Stage One (ingest_enrich), Stage Two
(detection), Stage Three (correlation), Stage Four (risk_fusion). Stages 5–6 (LLM triage, dashboard)
have empty scaffolds and are next.

## Repository layout

```
docs/                            planning docs (read-only reference, see below)
data/
  raw/                           Stage Zero output: cloudtrail.jsonl, k8s_audit.jsonl,
                                  idp_session.jsonl, labels.jsonl, data_dictionary.md 
  processed/                     Stage One+ output: events_enriched.parquet, ... 
modules/
  data_simulation/                DONE — generator, replay streamer, validator
  ingest_enrich/                  DONE — normalizer, cohort assignment, §5 features
  detection/                      DONE — two-stage detector (recall-first + suppression)
  correlation/                    DONE — graph incident clustering
  risk_fusion/                    DONE — fused score + isotonic calibration + incident ranking
  llm_triage/                     next — structured triage narratives
  dashboard/                      future — forensic/alert UI
tests/                           pytest suite (40 tests: 6 stage0 + 9 stage1 + 8 stage2 + 8 stage3 + 9 stage4)
```

## Common development tasks

```bash
# Setup
pip install -r requirements.txt

# Full pipeline: build → enrich → test
python -m modules.data_simulation.generator.build   # generate data/raw/ (seed 1337)
python modules/data_simulation/validate.py           # 16-check dataset gate (expect: 16/16 PASS)
python -m modules.ingest_enrich.build               # normalize → data/processed/events_enriched.parquet

# Run tests
python -m pytest tests/ -q                          # full suite (15 passed)
python -m pytest tests/test_stage0.py -q            # stage zero only
python -m pytest tests/test_stage1.py -q            # stage one only
python -m pytest tests/test_stage1.py::test_confusability_preserved -q  # single test

# Live inspection
python modules/data_simulation/replay/stream.py --instant --limit 5   # raw replay (first 5 events)
python -c "import pandas as pd; df=pd.read_parquet('data/processed/events_enriched.parquet'); print(df.shape, df.columns.tolist())"  # inspect enriched table
```

The planning documents, in order of authority:

1. [docs/ephemeral_risk_detection_analysis.md](docs/ephemeral_risk_detection_analysis.md) — the
   **single source of truth** for problem analysis, architecture, data flow, build plan, and
   evaluation (its own header states this authority explicitly: doc > CLAUDE.md > module READMEs).
   Section numbers cited below (§N) refer to this document.
2. [docs/problem_statement.md](docs/problem_statement.md) — the original challenge brief (the three Option
   A/B/C tiers, success criteria, framework alignment). Read as background, not as the plan.
3. [docs/data_resource_research.md](docs/data_resource_research.md) — survey of real-world public datasets for
   grounding the simulator (see "Grounding the simulator in real data" below).

## What is being built

A pipeline that discovers ephemeral cloud/K8s assets, classifies them ephemeral-vs-persistent,
detects risky transient behavior, correlates related events into incidents to cut alert noise,
scores risk, and emits analyst-ready LLM narratives with MITRE mapping and remediation.

The chosen approach **merges all three brief options** rather than picking one: Option A's
ML+LLM architecture is the spine; Option B's statistical baselines fold in as a cheap pre-filter;
Option C's deterministic rules fold in as always-on tripwires that force a severity floor regardless
of the ML score. They are inputs to one pipeline, not separate tiers.

## The central thesis (drives every design decision)

At the **event** level, a legitimate autoscaler burst and a malicious crypto-mining hijack are
statistically identical — same API calls, same burst rate. The separating signal is not in the event,
it is in the **context**: the identity's behavioral cohort, pattern novelty, resource exposure, and
how events relate across cloud, K8s, and IAM logs. Any change that detects on events alone will fail
on exactly the ambiguous cases this project exists to solve. Detect on context.

## Architecture (the four differentiators)

Pipeline order (as specified in the brief, literally):
`ingest → enrich → detect → cluster → score → LLM narrative → dashboard`

1. **Behavioral cohorts** replace per-identity baselines. Ephemeral identities have no stable history,
   so cluster principals into cohorts (`ci_runner`, `hpa_autoscaler`, `human_dev`, `scheduled_lambda`)
   and baseline the cohort. A brand-new pod inherits its cohort baseline instantly.
2. **Two-stage detection** separates recall from precision. Stage 1 is a recall-first anomaly model
   (Isolation Forest primary; over-flagging is expected/acceptable). Stage 2 suppresses candidates
   that are normal *for their cohort*. This is how precision >75% and alert reduction ≥40% are hit
   simultaneously instead of traded off.
3. **Graph correlation** (NetworkX). Build an entity multigraph (principals, sessions, resources,
   namespaces, actions); incidents are connected components within an identity+namespace+time
   envelope. This is what collapses 40 autoscaler alerts into 1 incident and links
   Lambda → assumed-role session → S3 access (a chain time-window clustering cannot recover).
4. **LLM triage agent** — a triage agent, not a prose generator. Returns *validated structured JSON*
   (intent, confidence, MITRE techniques, guardrails). Use strict schema + validation + retry, cache
   responses so the live demo never depends on a network call, and provide a templated fallback.

### Critical ordering catch — score AFTER clustering, not before

Read the pipeline order literally: lightweight rule/statistical detection flags candidates *first*,
clustering groups them *second*, and **risk scoring happens at the incident level, after clustering**.
Three individually low-scoring events from the same principal in the same 5-minute window can be one
high-severity incident together. Per-event scoring before clustering misses that; do not reorder these
stages. (Source: analysis doc §3, "Critical ordering catch.")

## Data simulation is the foundation — get it right first

**Implemented in [modules/data_simulation/](modules/data_simulation/).** There is no
provided dataset; the generator produces three labeled, synthetic log streams (CloudTrail, K8s audit,
IdP/session — 4–5k events/source over a 5-day span). Every downstream metric depends entirely on this
simulator, so it was built ground-truth-first: the real incident structure (which events belong to the
same crypto-mining burst, which pod is the debug pod) is constructed first, then every record and label
is derived from that structure — never bolted on randomly.

**Required label columns on every row** (most teams skip these and then can't measure honestly):
- `is_risky` (0/1) — precision/recall ground truth.
- `scenario_type` — `crypto_burst`, `public_exposure`, `identity_anomaly`, `legit_autoscale`,
  `legit_cicd`, `routine`.
- `cohort` — ground-truth behavioral cohort.
- `campaign_id` — **shared across all events of one attack, across all three sources.** Without it,
  graph correlation accuracy is unmeasurable.

**The confusability requirement (the single hardest design principle):** legitimate bursts (~40–50% of
data) and malicious bursts (~5–8%) must look **structurally identical in volume and timing**. They
differ only in metadata completeness and ownership — legit has complete tags / real `controller_owner`;
malicious has sparse tags / `controller_owner: None`. Making malicious events bigger or faster than
benign ones makes the problem artificially easy and renders the noise-reduction metric meaningless.
Generate every malicious scenario with a benign look-alike, and review confusability before trusting
any metric.

Generate with a fixed random seed for reproducibility.

### Grounding the simulator in real data (data_resource_research.md)

**Do not ingest any public dataset wholesale.** None provide the labeled ground truth this project
needs (`is_risky`, `campaign_id`/`true_incident_id`, `severity`) — they are either unlabeled or
labeled for a different purpose. Use them for **field-level and behavioral grounding only**, which
yields a real, citable "grounded in production data" claim at low time cost without making real-data
sourcing a build dependency. Concretely:

- **Cloud audit:** verify the generator's CloudTrail field names match real AWS using AWS's official
  per-event sample JSON. For attacker *behavior patterns* (not a drop-in dataset), the **flaws.cloud**
  public CloudTrail dataset (Summit Route / Scott Piper) is real anonymized attacker activity, though
  2017–2020-era schemas have since evolved. **Stratus Red Team** (Datadog) and **Mordor /
  Security-Datasets** (OTRF) are MITRE-mapped but are a tool / Windows-AD-skewed respectively.
- **Kubernetes:** match the `audit.k8s.io` record format exactly against the official K8s audit-log
  schema docs; the `liggitt/audit2rbac` sample audit log confirms realistic JSON shape (tiny, not
  volume).
- **Burst timing realism:** skim the **Google Cluster Trace (Borg)** or **Alibaba Cluster Trace** to
  sanity-check that inter-event timing within a 10–30 event burst resembles real workloads rather than
  an invented distribution. No security labels — pure timing grounding, which directly serves the
  confusability requirement (legit burst must look like the malicious burst).
- **Identity/session:** the weakest-covered source — no dedicated public ephemeral session-abuse
  dataset exists. Mimic session behavior (TTL patterns, off-hours, scope mismatch) from the
  `AssumeRole` records implicit in the cloud-audit sources above.

## What Stage One produces

**Input:** three JSONL source files from Stage Zero (CloudTrail, K8s audit, IdP events) + their ground-truth sidecar.

**Process:** normalize each source into one unified event schema, assign behavioral cohorts (§6 of design doc), compute §5 context features (burst rate, novelty, tag completeness, privilege, exposure, off-hours, cohort-deviation).

**Output:** `data/processed/events_enriched.parquet` with all source columns plus 8 feature columns, one row per input record, deterministically ordered, joined 1:1 to labels via `record_id`. This is the direct input to Stage Two (detection).

**Key design decision:** cohort assignment is rule-assisted (no ML) — K8s SA subject → CloudTrail role → IdP email prefix → source-IP CIDR. Unmatched principals → `unknown` cohort (a signal in itself; don't silently force the wrong cohort). Empirically, 629 unknowns = exactly the identity_anomaly attack rows (all `is_risky=1`).

**Verified:** 9,857 enriched rows, label join 1:1, cohort accuracy 100% on recognizable principals, confusability preserved (burst_rate overlap, context features separate).

## Source event schemas (see analysis doc §4 "Data Simulation Design" and §5 "Feature Engineering")

- **Cloud audit logs:** `event_id`, `timestamp`, `event_type` (RunInstances/AssumeRole/CreateBucket/
  TerminateInstances/PutBucketPolicy), `principal_id`, `principal_type`, `source_ip`, `region`,
  `resource_id`, `resource_type`, `tags` (deliberately sparse on a subset), `public_ip_assigned`,
  `spot_instance`.
- **Kubernetes events:** `event_id`, `timestamp`, `event_type` (pod_create/pod_delete/service_expose/
  rbac_change), `namespace`, `pod_name`, `controller_owner` (Deployment/Job/CronJob/**None** — "None"
  is the debug-pod signal), `labels`, `privileged`, `exposed_ports` (with a 0.0.0.0/0 marker), `node`.
- **Identity/session logs:** `event_id`, `timestamp`, `session_type` (assumed_role/service_account_token/
  federated), `principal_id`, `source_idp`, `ttl_seconds`, `source_ip`, `actions_performed`,
  `resource_accessed`.

## Tech stack (design doc §16)

Python, Pandas, NumPy/SciPy; scikit-learn (Isolation Forest + isotonic/Platt calibration), optional
autoencoder (PyTorch/Keras) as a secondary signal; NetworkX for the graph; any chat-completions LLM API
with JSON-schema-validated output; Streamlit or Plotly Dash for the dashboard; Parquet/SQLite for
event and incident storage.

**ML-model decision (RESOLVED):** the Stage-1 anomaly model is an **unsupervised ensemble of
scikit-learn `IsolationForest` (primary) + PyOD `ECOD` (required second vote)**, scores min-max
normalized and averaged. TabPFN (supervised, forces label leakage + a train/test split) and a
PyTorch/Keras autoencoder (overkill + a training loop on ~10k×8 data) were considered and rejected;
Claude-as-few-shot-scorer is a documented last-resort fallback only. Full rationale in design doc §16.

## Build order — backend lane first, then ML (strict dependency chain)

`simulator → features + cohorts → two-stage detector → graph + fusion → LLM triage → dashboard + eval`

Status: Stages 0–4 done (simulator → enrich → detection → correlation → risk_fusion). **Stage 5
(`modules/llm_triage/`) is next** — consume `data/processed/incidents_scored.parquet` (ranked incidents)
and emit validated structured triage JSON per incident (design doc §10). Stage 6 (dashboard) follows.

Backend-first is deliberate, not just convenient: ship a working, demoable V1 (normalized event store,
rule tripwires, statistical baselines, API) before any ML code. The rule/statistical pre-filter then
narrows the data so the ML layer only ever sees the harder, already-filtered cases — a smaller surface
for things to go wrong under time pressure.

## Evaluation must be measured, not eyeballed

- Compute against the ground-truth labels you control: ephemeral visibility = classifier recall vs
  `is_risky`-independent true-ephemeral count; correlation accuracy = graph components scored vs
  `campaign_id`; risk quality = precision/recall@K vs injected severity. Targets: precision >75%,
  recall >70%, alert reduction ≥40%.
- Build the **ablation table** (model only → +cohort suppression → full pipeline) — it is the most
  persuasive single artifact, proving each differentiator earns its place.
- Measure **time-to-detection vs resource lifetime** (did the alert fire before the asset vanished)
  and the **alert-fatigue curve** (raw → suppressed → correlated).
