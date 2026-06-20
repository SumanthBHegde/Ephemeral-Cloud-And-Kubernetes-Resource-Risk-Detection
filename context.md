# context.md

**Purpose:** single source of truth for project progress. A new AI session (or teammate) should be
able to read only this file and know what exists, why it exists, what was decided and rejected, what
is verified, and what to do next. Update this file at the end of every significant work session —
don't let it drift out of sync with reality.

Authority note: for *architecture/design* decisions, `docs/ephemeral_risk_detection_analysis.md` is
the source of truth (it says so in its own header). This file is the source of truth for *progress* —
what has actually been built, decided, and verified, in chronological order.

---

## 1. The project, in one paragraph

A hackathon submission building a near-real-time detection pipeline for ephemeral cloud/Kubernetes
risk (CI job pods, spot instances, assumed-role sessions, autoscaled containers — things that live for
minutes and vanish before traditional scans see them). The central thesis: at the *event* level a
legitimate autoscaler burst and a crypto-mining hijack are statistically identical, so detection must
work on **context** (behavioral cohort, novelty, exposure, cross-source correlation), not raw events.
Full design rationale lives in [docs/ephemeral_risk_detection_analysis.md](docs/ephemeral_risk_detection_analysis.md).

## 2. Current status (read this first)

| Module | Status |
|---|---|
| `modules/data_simulation/` | **DONE, verified** — generator + replay streamer + validator, all checks green |
| `modules/ingest_enrich/` | **DONE, verified** — normalize + clean + cohorts + §5 features, 9/9 tests green |
| `modules/detection/` | not started — empty scaffold |
| `modules/correlation/` | not started — empty scaffold |
| `modules/risk_fusion/` | not started — empty scaffold |
| `modules/llm_triage/` | not started — empty scaffold |
| `modules/dashboard/` | not started — empty scaffold |

**Next concrete step:** build `modules/detection/` — the two-stage detector (recall-first anomaly
model + cohort-aware suppression) over the enriched feature table at
`data/processed/events_enriched.parquet`. **Before writing any ML code, resolve the open
Isolation-Forest-vs-TabPFN decision** (§5 below / design doc §16) — it gates this module. Stage 1
(ingest_enrich) is done and provides every §5 feature the detector needs.

## 3. Chronological history

### 2026-06-20 10:13 — Initial planning docs committed (`f680d6f`)
Problem statement and first-pass analysis added at repo root: `problem_statement.md` (the original
hackathon brief — three tiers, Option A/B/C), an initial analysis doc, and an initial Option A design
doc. No code yet.

### 2026-06-20 10:35 / 10:41 — Planning docs iterated (`3e66de3`, `9ea1719`)
Pipeline ordering ("flow of k[8s]") clarified, and `data_resource_research.md` added — a survey of
real public datasets (flaws.cloud, Stratus Red Team, Mordor/Security-Datasets, Google/Alibaba cluster
traces, `audit2rbac`) to be used for **field-level and behavioral grounding only**. Decision made early
and never revisited: do not ingest any public dataset wholesale, because none carry the labeled ground
truth (`is_risky`, `campaign_id`, `severity`) this project needs.

### Stage Zero planning (AI session, before `c8d5671`)
User asked to build "Stage Zero" — synthetic telemetry generation — and explicitly asked to be
questioned until the plan was ~95% certain before building. Decisions locked via Q&A:

| Question | Answer |
|---|---|
| Output mode | Dataset **+** a replay streamer, not files alone |
| Schema style | Authentic nested JSON (real CloudTrail/`audit.k8s.io`/Okta shapes) — flattening is a *later* stage's job |
| File format | JSON Lines, one file per source |
| Volume & span | Larger volume (3–5k events/source) over **several days** (landed on 5) |
| Identity logs | **Both** — STS events inside CloudTrail *and* a separate IdP/session feed |
| Replay output | stdout JSONL with a speed multiplier knob |
| Labels | **Separate sidecar** file (`labels.jsonl`), keyed by each record's real ID — raw logs stay byte-authentic |

Non-negotiable principles carried into the build (all still true, see §4 of the design doc):
1. **Ground-truth-first** — build the incident/campaign structure first, derive every record/label from it.
2. **Confusability** — every malicious scenario ships a benign look-alike matched on volume/timing,
   differing only in metadata completeness/ownership/lineage. This is the single hardest design
   principle in the whole project — a simulator that makes attacks trivially separable makes every
   downstream metric meaningless.
3. **Cross-source linkage** via *authentic* fields (STS `assumedRoleId` → S3 caller `principalId`;
   IdP `externalSessionId` → STS session), not just a shared label column.
4. **Fixed seed** (1337) for full reproducibility.

### 2026-06-20 12:13 — Stage Zero implemented and committed (`c8d5671`)
Built `stage0_simulator/` (later renamed twice, see §4 below — final location
`modules/data_simulation/`):

- **Schemas** (`generator/schemas/`): authentic AWS CloudTrail (`eventVersion 1.09`, nested
  `userIdentity`/`sessionContext`, `RunInstances`/`AssumeRole`/`AssumeRoleWithWebIdentity`/
  `GetSessionToken`/`GetCallerIdentity`/`CreateBucket`/`PutBucketPolicy`/`GetObject`/`TerminateInstances`),
  `audit.k8s.io/v1` Kubernetes events (pod/service/RBAC, `ownerReferences` absence = bare-pod signal,
  `securityContext.privileged`, NodePort/LoadBalancer with source ranges), and Okta-style IdP System
  Log records (`externalSessionId` for cross-source linking).
- **Cohorts** (`generator/cohorts.py`): `ci_runner`, `hpa_autoscaler`, `human_dev`, `scheduled_lambda`,
  each with active hours, burst-size range, tag completeness, namespaces, source-IP CIDR.
- **Six scenario generators** (`generator/scenarios/`): `crypto_burst`, `public_exposure`,
  `identity_anomaly` (each emits a malicious campaign *and* a volume/timing-matched benign twin via
  `pair_id`), plus `legit_autoscale`, `legit_cicd`, `routine` (noise/background).
- **Four canonical incidents** forced in at fixed anchors (`generator/scenarios/canonical.py`):
  - **INC-A** — crypto burst: 20× `RunInstances` by `ci-runner-sa`, ~03:14, untagged, spot, public IP.
  - **INC-B** — exposed debug pod: bare pod (no owner), privileged, NodePort `0.0.0.0/0`, ~11 min life.
  - **INC-C** — compromised session → PII: federated IdP login → `AssumeRoleWithWebIdentity` → S3
    `GetObject` on a PII key, ~03:00, no scheduled trigger; spans IdP + CloudTrail.
  - **INC-D** — autoscaler noise burying a real alert: 40-pod HPA burst with a genuine
    credential-abuse event (`cluster-admin` binding) embedded in the same window.
- **Timeline placement** (`generator/timeline.py`): diurnal-weighted hour sampling so events land at
  realistic times without hand-coded heuristics.
- **Sidecar labels** (`generator/labels.py`): `is_risky`, `scenario_type`, `cohort`, `campaign_id`,
  `true_incident_id`, `severity`, `anomaly_type`, `pair_id`, keyed by each record's real ID.
- **Orchestrator** (`generator/build.py`): loads `config/simulation.yaml`, builds all campaigns, lays
  them on the timeline, renders to authentic schemas, writes JSONL + labels + an auto-generated
  `data_dictionary.md`.
- **Replay streamer** (`replay/stream.py`): merges the three JSONL files into one time-ordered,
  source-interleaved stream to stdout; `--speed N` paces it (`--instant` = no sleep); also importable
  as `replay_events()` for in-process consumption.
- **Validator** (`validate.py`): 16-check gate (label join integrity, anomaly-mix tolerance,
  confusability pairing, crypto-burst size parity, cross-source linkage recoverable *without* the
  sidecar, per-source schema validity, all four canonical incidents present and correctly shaped).
- **Tests** (`tests/test_stage0.py`): determinism (same seed → byte-identical digest), seed-sensitivity,
  anomaly-mix tolerance, canonical-incident presence, label join 1:1, replay time-ordering.

Two encountered issues, both fixed during this build (no other errors hit):
- `ctx.mint_principal_for_role()` was referenced before it existed → added to `context.py`.
- CloudTrail's `AssumeRole` renderer didn't expose pinnable result fields → made
  `result_access_key_id`/`result_assumed_role_id`/`result_assumed_role_arn` configurable via `attrs`
  so scenarios could thread STS session identity into later S3 calls (INC-C's cross-source link).

**Verified end-to-end at this commit:** build → 9,857 events (4,000 CloudTrail / 4,357 K8s / 1,500
IdP, ~9% over the K8s target because legit pod bursts + exposure overshoot before routine top-up —
accepted, global mix still within tolerance); `validate.py` → 16/16 PASS; `pytest` → 6/6 PASS; replay
spot-checked for time-ordering and source interleaving.

### 2026-06-20 12:28 — Docs refactored (`e7435ab`)
`docs/ephemeral_cloud_analysis.md` and `docs/ephemeral_risk_detection_option_a_design.md` were merged
into a single **`docs/ephemeral_risk_detection_analysis.md`** (478 lines) — now the one design
source of truth, with its own internal section numbers 1–20 and an explicit authority statement in its
header ("this document > CLAUDE.md guidance > subsidiary READMEs"). `docs/problem_statement.md` and
`docs/data_resource_research.md` are unchanged. This happened outside the AI session that built Stage
Zero — **CLAUDE.md's references to the two old filenames and old section numbers (§4, §8, §17) were
stale until corrected in this same context.md-creation pass; see §5 below.**

### (same day, AI session) — Folder scaffold created, then renamed twice
1. First pass: created `docs/`, `data/raw/` + `data/processed/`, and `stages/stage0_data_simulation/`
   (renamed from the original `stage0_simulator/`) alongside six empty future-stage folders
   `stages/stage{1..6}_*`. All Python imports, path-resolution math, and the `.gitignore` were updated
   to match; re-verified 16/16 + 6/6 green after the move.
2. Second pass (this was a deliberate user-requested rename, not a correction): `stages/` → `modules/`,
   and the `stageN_` prefix dropped from every inner folder name (`stage0_data_simulation` →
   `data_simulation`, `stage1_ingest_enrich` → `ingest_enrich`, etc.). Same depth, so no path-math
   changes were needed this time — only the import strings and docs. Re-verified 16/16 + 6/6 green
   again. **This is the current, final naming** — do not reintroduce `stages/` or `stageN_` prefixes.

### 2026-06-20 — CLAUDE.md `/init` pass
Ran the `/init` skill against the existing CLAUDE.md. Found it already accurate post-rename; added the
one missing piece per `/init`'s checklist — a single-test invocation example
(`pytest tests/test_stage0.py::test_deterministic_same_seed -q`). No other changes were needed at that
point (this was *before* the doc-reference staleness from the `e7435ab` merge was caught and fixed).

### 2026-06-20 — This file created + CLAUDE.md doc-reference fix
Created this `context.md`. While grounding it against `git log`, discovered CLAUDE.md still pointed at
the two pre-merge doc filenames and old section numbers from the `e7435ab` refactor — corrected as part
of this same pass (see CLAUDE.md's current "planning documents" list and section citations).

### 2026-06-20 — Stage 1 (`modules/ingest_enrich/`) built and verified
Built the full ingest+enrich stage: read the three authentic Stage-Zero sources, normalize to one
unified event schema, clean, assign behavioral cohorts (§6), and compute the §5 context features that
unblock the detector. **9/9 new tests green; full suite 15/15 (6 Stage 0 + 9 Stage 1).**

Decisions locked via Q&A this session (some correct the user's initial framing):

| Question | Answer |
|---|---|
| Output format | **Parquet only** (`data/processed/events_enriched.parquet`) — design doc §16. User's initial "JSONL→CSV" instinct **rejected**: CSV is lossy on the nested/list columns this stage emits (`tags`, `labels`, `raw`). |
| Consumption mode | **Both** — `build_enriched()` reads the 3 JSONL files directly (deterministic batch path detection reads); `enrich_stream()` wraps the existing `replay_events()` for the dashboard's live tile (per-event normalize+cohort only; windowed features stay batch). |
| Scope | **Full Stage 1** — normalize + clean + all §5 features + §6 cohorts (not just cleaning). |
| Cohort method | **Rule-assisted, deterministic** (no ML, no sklearn yet) — K8s SA subject → CloudTrail role/`invokedBy` → IdP email prefix → source-IP CIDR. §6 explicitly allows this. |
| Cohort baseline | **Computed empirically from the data** (per-cohort z-centroid), NOT from `simulation.yaml` — avoids the circularity of "detecting what was injected". |

Files added under `modules/ingest_enrich/`: `normalize/{cloudtrail,k8s_audit,idp_session,dispatch}.py`
(+ `__init__.py` defining `UNIFIED_FIELDS`), `enrich/{cohorts,features}.py`, `pipeline.py`, `build.py`,
real `README.md`; plus `tests/test_stage1.py`. `requirements.txt` gained `pandas>=2.0`, `pyarrow>=14`
(no scikit-learn — deferred to detection). Reused `replay_events()`, `load_config()`/`load_cohorts()`,
and the `SRC_*`/`ID_FIELD` constants from Stage Zero rather than re-hardcoding.

**Implementation findings worth keeping:**
- The cross-source thread for INC-C is `roleSessionName` ↔ IdP `actor.displayName` + a shared
  `sharedEventID`, and STS→S3 via `assumedRoleId == S3 caller principalId`. The IdP
  `externalSessionId` does **not** appear verbatim in CloudTrail — all linkage keys are surfaced as
  columns; the *joining* is the graph stage's job, not Stage 1's.
- The config's nominal hpa `k8s_subject` (`cluster-autoscaler`) does **not** match the rendered data
  (the autoscale path surfaces as `replicaset-controller` + `autoscaling.amazonaws.com`). Cohort rules
  are therefore grounded in the fields that actually appear, not blind config trust.
- **629 rows assigned `unknown` cohort — this is correct, not a bug.** Every one is the
  `identity_anomaly` attack (`contractor-*` federated users, public IPs, `is_risky=1`). Ground truth
  labels them `human_dev` (nearest benign), but the whole point is they fit no known cohort baseline —
  that *is* the signal. Forcing them into a cohort would mask the attack. Cohort accuracy on the 9,228
  recognizable principals is **100%**.

**Verified this session:** build → 9,857 enriched rows (4,000 CT / 4,357 K8s / 1,500 IdP), label join
1:1, cohort accuracy 100% (non-unknown), all four canonical incidents' signals captured in features
(INC-A off-hours+untagged+spot+public, INC-B privileged+exposed+bare, INC-C STS/IdP linkage keys,
INC-D broad_rbac), and **confusability preserved** — crypto vs legit `burst_rate` overlap (mean 10.82
vs 10.57) while tag_completeness (0.00 vs 0.41) and off_hours (0.83 vs 0.07) carry the separation.

## 4. Naming history (so nobody resurrects an old path)

```
stage0_simulator/                          ← original name, commit c8d5671
  → stages/stage0_data_simulation/         ← first rename (parent + per-stage folders introduced)
    → modules/data_simulation/             ← FINAL — current name, do not revert
```

Same evolution applies to the empty future-stage folders:
`stages/stage1_ingest_enrich/` → `modules/ingest_enrich/` (and analogously for stages 2–6).

## 5. Decisions made and explicitly rejected (don't re-litigate these)

- **Rejected:** ingesting any real public dataset wholesale. Reason: none carry the labeled ground
  truth (`is_risky`/`campaign_id`/`severity`) this project needs; real data is for field/behavior
  grounding only (§3 of the design doc).
- **Rejected:** making malicious bursts bigger/faster than benign ones. Reason: this is exactly the
  shortcut that makes the noise-reduction metric meaningless — confusability must come from metadata
  (tags, ownership, lineage), never from volume/timing.
- **Rejected:** scoring risk per-event before clustering. Reason: three individually low-scoring events
  from the same principal in one window can be one high-severity incident together; per-event scoring
  before clustering misses that. Score AFTER clustering — this is called out as non-negotiable in both
  CLAUDE.md and the design doc.
- **Open, not yet decided:** Isolation Forest vs. TabPFN for the anomaly model (design doc §16 flags
  TabPFN as a way to avoid burning the Claude Code Pro usage window on train/tune cycles, with
  "Claude-as-few-shot-scorer" as a fallback-of-last-resort). Decide this before starting
  `modules/detection/`.

## 6. How to verify the current state still holds

```bash
pip install -r requirements.txt
python -m modules.data_simulation.generator.build      # regenerate data/raw/ (seed 1337, deterministic)
python modules/data_simulation/validate.py              # expect: 16/16 PASS
python -m modules.ingest_enrich.build                   # -> data/processed/events_enriched.parquet
python -m pytest tests/ -q                              # expect: 15 passed (6 stage0 + 9 stage1)
python modules/data_simulation/replay/stream.py --instant --limit 5   # sanity-check live replay
```
Last confirmed: Stage 0 → 9,857 events (4,000/4,357/1,500 per source), 1,710 risky (17.3%), all four
canonical incidents present (`INC-A=40, INC-B=3, INC-C=7, INC-D=2`), 16/16 validator green. Stage 1 →
9,857 enriched rows, label join 1:1, cohort accuracy 100% (non-unknown), confusability preserved.
Full suite 15/15 green.

## 7. What a new session should do next

1. Read this file, then `docs/ephemeral_risk_detection_analysis.md` for the design rationale behind
   whatever you're about to touch.
2. If picking up `modules/detection/`: **first resolve the Isolation-Forest-vs-TabPFN decision** (§5),
   then read the enriched feature columns from `modules/ingest_enrich/README.md` and load
   `data/processed/events_enriched.parquet` — that table (cohorts + §5 features) is the detector's
   input. Labels for eval are in `data/raw/labels.jsonl`, joined on `record_id` (never read at runtime).
3. After any meaningful change, append a new dated entry to §3 of this file — don't rewrite history,
   add to it.
