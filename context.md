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
| `modules/detection/` | **DONE, verified** — tripwires + IF/ECOD ensemble + cohort suppression, 8/8 tests green |
| `modules/correlation/` | **DONE, verified** — entity graph + connected-component incidents, alert reduction 89%, 8/8 tests green |
| `modules/risk_fusion/` | **DONE, verified** — fused raw score + OOF isotonic calibration + incident aggregation, precision@50 96%, 9/9 tests green |
| `modules/llm_triage/` | **DONE, verified** — OpenAI gpt-4o-mini structured-output triage + existence-based cache (cost guard) + label-free templated fallback, 263 CRITICAL+HIGH incidents triaged live (100%), 10/10 tests green |
| `modules/dashboard/` | **DONE, verified** — React 19 + Vite + Tailwind SOC console (ThreatLens design language) over static JSON exported from the pipeline; real-time replay simulation; `npm run build` green (2350 modules) |

**Next concrete step:** the pipeline (Stages 0–6) is complete. Remaining work is polish/eval, not new
stages: optionally run the live OpenAI triage (`python -m modules.llm_triage.build` with a key) to
refresh narratives, and walk the dashboard QA checklist (design handoff §8) in both themes. To run the
dashboard: `python -m modules.dashboard.build` (export JSON) then `cd modules/dashboard/frontend &&
npm install && npm run dev`.

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

### 2026-06-20 — Prompt history converted to docs/prompt_documentation.md
Converted `docs/Prompt Documentation.pdf` (the team's own log of the 26 prompts used during Phase 1 —
problem-statement exploration/selection across the four Société Générale hackathon options, ending in
the choice of Problem Statement 3 / Ephemeral Cloud) into
[docs/prompt_documentation.md](docs/prompt_documentation.md). Faithful 1:1 conversion (each prompt's
text + stated purpose, plus the phase's closing results list); no content added or reinterpreted. The
source PDF is left in place in `docs/` alongside the new `.md`.

### 2026-06-20 — Stage-1 model decision resolved + Stage 2 (`modules/detection/`) built and verified
Resolved the long-open Isolation-Forest-vs-TabPFN decision (§5) and built the full two-stage
detector. **8/8 new tests green; full suite 23/23 (6 Stage 0 + 9 Stage 1 + 8 Stage 2).**

Decision (via Q&A this session, user confirmed): Stage-1 anomaly model = **unsupervised ensemble of
scikit-learn `IsolationForest` (primary) + PyOD `ECOD` (required second vote)**. The user upgraded
ECOD from "optional" to a **required** ensemble member. TabPFN and a PyTorch/Keras autoencoder were
considered and rejected (see §5 / design doc §16, all rewritten from "open tension" → resolved).
Docs synced: design doc §7/§16/§20, `modules/detection/README.md`, CLAUDE.md, `requirements.txt`
(+`scikit-learn`, `pyod`, `scipy`).

Module `modules/detection/` (mirrors Stage 1's structure):
- `detect/tripwires.py` — always-on deterministic rules forcing a HIGH severity floor (never
  suppressed): NodePort 0.0.0.0/0, bare privileged pod, `burst_rate>10`, broad RBAC, **and
  `cohort=="unknown"`**.
- `detect/anomaly.py` — Stage 1, recall-first: median-impute + `StandardScaler` over the 8 §5
  features, `IsolationForest(n_estimators=200, contamination=0.30, random_state=1337)` + PyOD
  `ECOD`, each min-max normalized, averaged into `ensemble_score`; `is_candidate` = top ~35%.
- `detect/suppression.py` — Stage 2, no ML: suppress a candidate only if cohort-normal (known
  cohort, `cohort_deviation` ≤ cohort 75th pct, `tag_completeness≥0.5`/NaN, in-hours, not a
  tripwire). `predicted_risky = (is_candidate & ~is_suppressed) | tripwire_hit`.
- `pipeline.py` (`run_detection`), `build.py` (CLI → `data/processed/detections.parquet`),
  `evaluate.py` (label join → P/R/F1 + ablation table), real `README.md`; `tests/test_stage2.py`.

**Key implementation finding (kept for the next session):** the recall-first IF+ECOD ensemble alone
caught only ~47% recall — it *cannot* catch the 629 `identity_anomaly` rows because they are the
`unknown` cohort and form a dense same-shape cluster (not sparse outliers an anomaly model flags).
Those 629 are ~100% `is_risky` (per the ingest README), so adding `cohort=="unknown"` as a context
**tripwire** is high-precision and lifts recall to **84.2%** with near-zero added false positives.
This is the project thesis made literal: detect on context, not events.

**Verified this session (ablation table from `evaluate.py`):**
| Configuration | Precision | Recall | Alert reduction |
|---|---|---|---|
| tripwires only | 43.5% | 72.5% | 38% |
| + Stage-1 ensemble | 31.1% | 84.2% | 0% |
| + Stage-2 suppression (full) | 33.6% | 84.2% | 8% |

Recall target (>70%) met. Precision is intentionally low here — it is won by the **graph
correlation + risk fusion** stages next (the ≥40% alert reduction also lands there; suppression
alone buys ~8%). The ablation already shows the two-stage mechanism working: the ensemble lifts
recall 72%→84%, and suppression recovers precision 31%→33.6% **without** giving back recall.

### 2026-06-20 — Stage 3 (`modules/correlation/`) built and verified
Built the graph-correlation stage that clusters Stage-2 flags into incidents. **8/8 new tests
green; full suite 31/31 (6 stage0 + 9 stage1 + 8 stage2 + 8 stage3).** `requirements.txt`
gained `networkx>=3.0`.

Decisions locked with the user this session (plan was reviewed and revised twice before approval):
| Question | Answer |
|---|---|
| Graph scope | **Flagged seeds + 1-hop expansion** — seed from `predicted_risky`, expand exactly one hop along strong linkage keys to pull in directly-linked *bridge* events even when unflagged. Not flagged-only, not the full 9,857-event graph. |
| Output | **Both** — `incidents.parquet` (one row per incident, primary for risk_fusion) + `event_incidents.parquet` (per-event `record_id → incident_id`, ALL 9,857 events; non-members get `incident_id=None`). |
| `source_mix` storage | **Three flat int columns** (`source_cloudtrail_count`/`source_k8s_count`/`source_idp_count`), not a dict — derived with a fixed mapping to the literal source values (`cloudtrail`/`k8s_audit`/`idp_session`) + `.get(...,0)` so a missing source is 0, never a KeyError. |
| Alert-reduction denominator | **`tripwire_hit | is_candidate`** — the *same* denominator Stage 2 used (verified at `detection/evaluate.py:64`), so the 8% → 89% jump is apples-to-apples. |

**Key design deviation from design doc §8 (documented, deliberate):** §8 specifies an *entity*
multigraph (principals/sessions/resources as nodes, events as edges). Implementation inverts this
to an **event-node graph with time-gated, typed edges**. Why: design §8's entity model cannot
enforce the identity+namespace+time envelope (§18) because nodes have no temporal scope. One
service account (`replicaset-controller`) produces one timeless principal node, and all
autoscaler bursts across all namespaces and all time chain into one mega-incident. The envelope
can only be enforced *at edge-creation time*, so edges (not nodes) carry the temporal gate. The
event-node model makes the envelope a structural property: `add_edge_only_if(same_entity AND
within_time_window AND same_namespace)`. Connected-component output is functionally identical to
the entity model; the incident artifact still surfaces the entity view (`principal_ids`,
`namespaces`, `resource_ids`, `edge_types`). 

The 1-hop guarantee is enforced at **build time** (not component time): within each edge key,
only seed-containing clusters survive and are star-connected from a seed; the invariant **every
edge has ≥1 seed endpoint** holds — exactly seed→bridge (1 hop) and seed→bridge←seed (cross-source),
never seed→bridge→bridge.

Edge rules (grounded in the actual linkage values, not config trust): `same_principal`
(`principal_id`, 30-min window, namespace-partitioned), `same_session` (`session_name`, 30 min —
the **only** link from INC-C's IdP login to its AssumeRole), `external_session`
(`external_session_id`, 30 min), `shared_event` (`shared_event_id`, ungated — a UUID, unique per
API call), `same_resource` (`resource_id`+`principal_id`, 2-h window — bridges INC-A's
RunInstances→TerminateInstances across a 91-min gap on one instance id). Windows are tunable
constants in `graph/entities.py`.

Module files: `graph/{entities,build_graph,incidents}.py` (+ `__init__.py` exporting `build_graph`,
`extract_incidents`, `INCIDENT_COLS`, the window constants), `pipeline.py` (`correlate` pure +
`run_correlation` CLI-facing), `build.py`, `evaluate.py` (reuses `_load_labels`/`_prf` from
`detection.evaluate` and `sklearn.homogeneity_completeness_v_measure`), real `README.md`; plus
`tests/test_stage3.py`.

**Implementation findings worth keeping:**
- **Graph correlation recovers missed detections.** Recall jumps **84% → 100%**: bridge expansion
  pulls in the ~16% of `is_risky` events the detector missed (they were 1-hop from a flagged seed).
  This is a real, measurable second benefit of correlation beyond noise reduction.
- **Event-level precision drops to ~24% at correlation** (benign bridge neighbours join incidents).
  This is expected and *correct* — precision is now an **incident-level** concern won by the next
  stage (risk_fusion ranks incidents by risk). Do not "fix" it inside correlation.
- **INC-D's two labelled events legitimately split into two incidents** — they share no surfaced
  linkage key (`session_name=oncall` vs `resource_id=oncall-escalation`, different principals). The
  credential-abuse `rbac_change` still surfaces as its own HIGH incident; the autoscaler noise
  around it collapses. The `test_autoscaler_collapse` assertion is therefore on INC-A (clean 40→1),
  and a separate `test_credential_abuse_captured` asserts INC-D's real alert is a HIGH member.

**Verified this session (`evaluate.py`):** 4,288 flagged events → **529 incidents**, **alert
reduction 89%** (4,638 raw flags → 529; target ≥40%), **correlation accuracy vs `campaign_id`:
homogeneity 0.88 / completeness 0.99 / V-measure 0.93**. Canonical recovery: INC-A 40→1, INC-B
3→1, INC-C 7→1 (cross-source, spans CloudTrail+IdP), INC-D 2→2 (by design). Extended ablation
table:
| Configuration | Precision | Recall | Alert reduction |
|---|---|---|---|
| tripwires only | 43.5% | 72.5% | 38% |
| + Stage-1 ensemble | 31.1% | 84.2% | 0% |
| + Stage-2 suppression | 33.6% | 84.2% | 8% |
| **+ graph correlation** | **24.1%** | **100%** | **89%** |

### 2026-06-20 — Stage 4 (`modules/risk_fusion/`) built and verified
Built the incident-level risk-fusion + calibration stage. **9/9 new tests green; full suite 40/40
(6 stage0 + 9 stage1 + 8 stage2 + 8 stage3 + 9 stage4).** No new deps (scikit-learn/scipy already present).

Decisions locked with the user this session (4-question Q&A) and one mid-build empirical correction:
| Question | Answer |
|---|---|
| Calibration approach | **Calibrate on event-level `is_risky`** (more data than ~529 incidents). Out-of-fold isotonic so no event is scored by a model that saw it. |
| Score inputs | **Re-join member events + aggregate §5 features** (not incident-columns-only). |
| Fusion weights | **Fixed expert weights** (documented, tunable constants) — not learned. |
| Incident severity GT (eval) | **Max `severity` over `is_risky=1` members**; benign-only → none. |

Pipeline (`fuse/` package): `score.py` event-level `raw_risk` = fixed-weight fusion of
`ensemble_score` + `tripwire_hit` signal + exposure (`0.5·public_exposure_flag + 0.5·norm(exposure_window_s)`)
+ `norm(privilege_level)` + `norm(principal_novelty)` (weights 0.30/0.25/0.20/0.10/0.15, **label-free**);
`calibrate.py` `StratifiedKFold(5, seed 1337)` out-of-fold `IsotonicRegression` → `p_event` (**the one
sanctioned label touch** — §9/§16 permit held-out-label calibration); `aggregate.py`
`risk_score = 0.7·max + 0.3·mean` of member `p_event`, tripwire floor via
`FLOOR_THRESHOLDS={"CRITICAL":0.80,"HIGH":0.60}`, bands (CRITICAL≥0.80/HIGH≥0.60/MEDIUM≥0.35/LOW),
`risk_rank` (**label-free**). Outputs `incidents_scored.parquet` (primary, INCIDENT_COLS + `risk_score`/
`risk_band`/`risk_rank` + evidence cols) + `events_scored.parquet` (`record_id`/`raw_risk`/`p_event`).

Decisions made and explicitly rejected this session (review-driven, see plan file):
- **`KFold` → `StratifiedKFold`** — at 17.3% risky rate plain KFold can fit a degenerate isotonic curve
  on a positive-starved fold. Stratify.
- **CRITICAL floor DEFERRED** (user choice) — upstream emits `severity_floor ∈ {HIGH, NONE}` only today
  ([tripwires.py:43](modules/detection/detect/tripwires.py#L43),
  [incidents.py:95](modules/correlation/graph/incidents.py#L95)); no CRITICAL exists yet. `FLOOR_THRESHOLDS`
  already carries the CRITICAL branch forward-compatibly (dormant). Stage 4 did NOT modify Stage 2/3.

**Key implementation finding (kept for the next session): precision recovery is won by RANKING, not the
band cut.** The `burst_rate>10` tripwire fires on *legit* autoscaler bursts too, so flooring every
`severity_floor==HIGH` incident to the HIGH band re-imports the tripwire's false positives — band≥HIGH
gives **P=68.4% / R=99.45%** (a high-recall triage cut, by design: the floor guarantees a tripwire
incident is never dismissed). The real precision recovery is the **ranked queue**: ordering incidents by
`risk_score` gives **precision@10=90%, @20=95%, @50=96%, @100=79%** — recovered from the 24% event-level
precision after correlation. This is §13's prescribed risk-quality metric (precision/recall@K vs injected
severity), so the tests gate on precision@K, not band precision. Calibration is near-perfect (predicted ≈
observed in every reliability bin).

**Verified this session (`evaluate.py`):** 529 incidents scored (44 CRITICAL / 219 HIGH / 266 LOW; no
MEDIUM), `risk_score` ∈ [0.056, 0.885]. Extended ablation table:
| Configuration | Precision | Recall | Alert reduction |
|---|---|---|---|
| tripwires only | 43.5% | 72.5% | 38% |
| + Stage-1 ensemble | 31.1% | 84.2% | 0% |
| + Stage-2 suppression | 33.6% | 84.2% | 8% |
| + graph correlation | 24.1% | 100.0% | 89% |
| **+ risk fusion (incident, band≥HIGH)** | **68.4%** | **99.5%** | **89%** |

(precision@K is the headline recovery: 96% @50. The band≥HIGH row above is the high-recall cut.)

### 2026-06-20 — Stage 5 (`modules/llm_triage/`) built and verified
Built the LLM triage agent that turns the ranked CRITICAL/HIGH incidents into validated structured
triage JSON (design doc §10). **10/10 new tests green; full suite 50/50 (6 stage0 + 9 stage1 + 8 stage2
+ 8 stage3 + 9 stage4 + 10 stage5).** `requirements.txt` gained `openai>=1.40` + `python-dotenv>=1.0`;
`.env` added to `.gitignore` with a committed `.env.example`.

Decisions locked with the user this session (two Q&A rounds), then hardened over three plan-review
passes:
| Question | Answer |
|---|---|
| Provider/model | **OpenAI `gpt-4o-mini`** with **strict `json_schema` structured outputs** (`response_format`, `strict:true`). HuggingFace rejected (weaker JSON adherence; local path = GPU/download risk). `openai>=1.40` pinned — `strict:true` is silently ignored below 1.40. |
| API key | **gitignored `.env` + `python-dotenv`** (`OPENAI_API_KEY`); `.env.example` committed. |
| Triage scope | **`risk_band ∈ {CRITICAL, HIGH}`** — 263 incidents (44 + 219). |
| Caching | **pre-generate + cache** — per-incident `data/processed/triage_cache/INC-XXXX.json` keyed by `incident_id` + `sort_keys` MD5 of the evidence bundle, so a rerun on unchanged data is a pure cache hit (offline, deterministic demo). |

Module `modules/llm_triage/` (mirrors risk_fusion's structure): `triage/` package —
`schema.py` (the 7-field strict json_schema + a stdlib validator: MITRE regex `T\d{4}(\.\d{3})?`,
non-empty lists, confidence∈[0,1]), `evidence.py` (`build_evidence_bundle` — incident aggregates +
top-`MAX_MEMBER_EVENTS=5` member events ranked by `p_event`, carrying confusability fields cohort /
tag_completeness / controller_owner / exposure / off-hours), `prompt.py` (SOC-triage system prompt
encoding the central thesis), `client.py` (lazy-imported OpenAI, `timeout=30`, `MAX_RETRIES=3`,
validate-then-retry), `cache.py`, `fallback.py` (deterministic **LABEL-FREE** template). Plus
`pipeline.py` (`run_triage`: cache → LLM → templated fallback per incident; `use_llm=False` forces
fallback-only for tests/offline), `build.py` (`--no-llm` flag), `evaluate.py`, real `README.md`;
`tests/test_stage5.py`.

Plan-review fixes worth keeping (all caught before/at build):
- **Fallback is strictly label-free** — `scenario_type` is a `labels.jsonl` sidecar field absent from
  `incidents_scored` at runtime; the template derives intent from `edge_types` / `risk_band` /
  `severity_floor` / `any_privileged` / source mix / `max_privilege_level` only. A test asserts
  `scenario_type`/`is_risky` are not in the incident frame and the fallback still validates.
- **Member ranking uses `p_event`** (from `events_scored`, written "for dashboard + LLM"), not
  `ensemble_score` (which lives in `detections.parquet`, not the enriched table). `run_triage` takes
  `events_scored` as a parameter so evidence.py never reads disk → in-memory test path intact.
- **Stage never crashes** — a failed/invalid LLM call degrades to the template; every record carries
  a `triage_source` provenance tag (`llm`/`cache`/`template`).
- One build bug fixed: the bundle's `_py` coercion iterated numpy *scalars* (which have `.tolist()`);
  switched to explicit `np.ndarray` / `np.generic` checks.

**Verified this session (`--no-llm` + `evaluate.py`):** 263/263 CRITICAL+HIGH incidents triaged
(coverage 100%), second run = pure cache hit (provenance `cache=263`), all four canonical incidents
(INC-A/B/C/D) triaged with non-empty intent + disambiguation, MITRE coverage 100%. Ablation extended:
| Configuration | Precision | Recall | Alert reduction |
|---|---|---|---|
| + risk fusion (incident, band≥HIGH) | 68.4% | 99.5% | 89% |
| **+ LLM triage (CRITICAL+HIGH narratives)** | **68.4%** | **99.5%** | **89%** |

(Triage annotates the band≥HIGH queue; it doesn't change the flagged set, so P/R carry forward. Its
contribution is analyst-ready narratives, not a precision/recall move.)

**Live OpenAI verification (same session):** After adding the API key and clearing the cache,
ran `python -m modules.llm_triage.build` to generate real gpt-4o-mini triages. **All 263/263
incidents successfully triaged via LLM** (`provenance: llm=263`, zero fallbacks), mean confidence
0.852 (range 0.80–0.90). All 263 cache files are tagged `triage_source="llm"`, each with a
high-confidence context-driven narrative (e.g. INC-0515: confidence 0.9, "Malicious exposure of
services…", mitre=['T1496','T1610','T1078'], evidence and guardrails drawn from the incident bundle).
Final parquet `incidents_triaged.parquet` is 263 rows, all `llm` provenance. Both live and offline
paths verified green. (Note: an intermediate inspection mid-run saw only 219 files because the
sequential run was still in flight; the completed run is 263/263.)

**Post-build: cache reuse made existence-based (cost guard, user-requested).** Originally the cache
reused an entry only when the evidence hash matched, so any bundle change (even trivial) re-spent the
paid API on every incident. Changed to **existence-based reuse**: if `INC-XXXX.json` already exists it
is reused and the LLM is never re-called — a rerun never re-spends the API. Added `force_refresh`
(`run_triage(..., force_refresh=True)` / `build --force-refresh`) to regenerate; corrupt/incomplete
cache entries fall through to regeneration. `evidence_hash` is still stored (and `cache.get()` still
offers strict hash-checked reuse) so staleness stays detectable. New test
`test_existence_based_reuse_and_force_refresh` (Stage 5 now **10/10**, full suite **50/50**). Verified:
a live `build` over the 263 existing cache files makes **zero API calls** (`provenance: cache=263`).

### 2026-06-21 — Stage 6 (`modules/dashboard/`) built and verified
Built the final stage: an enterprise SOC-style web console that visualizes the *real* pipeline outputs.
Departs from CLAUDE.md's original "Streamlit/Dash" suggestion — the user supplied a polished React
design language ("ThreatLens", `docs/frontend_design_guidlines.md`) exported from a reference app at
`D:\projects\threat-intel`, so the dashboard is **React 19 + Vite + Tailwind v3** instead.

Architecture (decided via plan-mode Q&A + four review passes): **static-JSON export, not a live
backend.** `python -m modules.dashboard.build` reads `data/processed/*.parquet` and writes JSON into
`modules/dashboard/frontend/public/data/`; the frontend fetches it once on mount (`lib/data.jsx`
`DataProvider`/`useData`). This keeps the demo fully offline (matches the project's "demo never depends
on a network call" principle) and the JS bundle small. The threat-intel project was copied in and
rebranded (product → **EphemeraLens**; threats→findings, IOCs→resources/events, threat-actors→
namespaces/cohorts); theme tokens, UI primitives (`ui/index.jsx`), and `shared.jsx` were reused
verbatim. Login/MFA/Landing/Admin pages were dropped (user: no auth); `/` redirects to `/app`.

Exported artifacts (`build.py`): `incidents.json` (529, `incidents_scored` ⟕ `incidents_triaged`, each
with top-8 member events by `p_event`), `events.json` (9,857 enriched + `p_event` + incident), `metrics.json`
(KPIs, **alert-fatigue funnel** 9857→3517→3167→529→263, severity/cohort/source/MITRE aggregates, riskiest
namespaces/cohorts/principals), `reports.json` (top-20 triaged as documents), `notifications.json`,
`replay.json` (time-ordered events + 15-min `timeline_bins` + per-incident `formation_time`/
`traditional_detect_time`/`detection_lag_hours` + a `demo_window`).

Pages (`src/pages/`): Dashboard (KPIs + replay hero + alert-fatigue funnel + trend/donut + latest
findings + riskiest namespaces/cohorts), Risk Findings (grid/list + filter bar + **triage detail drawer**:
intent, confidence bar, MITRE, evidence, disambiguation, guardrails, participants, top member events,
"Ask AI Analyst" → `/app/chat?incident=`), Resource Explorer (sortable/paginated 9,857-event table),
Analytics (6 recharts panels), AI Risk Analyst (canned, triage-driven, reads `?incident=`), Reports,
Notifications, Settings (theme toggle).

**Headline feature — real-time replay simulation** (`lib/ReplayEngine.jsx` + `components/ReplayPanel.jsx`):
a plain JS class drives a virtual clock with play/pause/seek/speed/range and `onTick` subscribers
(emitting `clockTime`/`binIndex`/`eventsSeen`/`formedIncidents`/`newIncidents`). Critical design fix
from review: "1×" is anchored to a `TARGET_DURATION_S=120` real-second budget (NOT real-time, which
would make the window take hours); slider is 0.5×/1×/2×. The chart is fed by 15-min `timeline_bins`
(revealed bin-by-bin) to avoid per-event recharts re-render jank. The demo incident is chosen as the
**densest CRITICAL** (`max(event_count)` → INC-0230, 46 events), not rank-1 (which can be a sparse
chain). A before/after annotation contrasts pipeline detection time vs. the next daily scan
("Traditional scan misses this for 17.9h").

**Verified this session:** `python -m modules.dashboard.build` → incidents 529 (263 triaged), events
9,857, funnel [9857,3517,3167,529,263], replay 9857 events / 481 bins / 263 incidents, demo_window
INC-0230; all six JSON files parse; spot-checked `formation_time == max member event_time` and
`traditional_detect_time ≥ formation_time`. `npm install` clean (0 vulnerabilities); `npm run build`
green (2350 modules, only a >500 kB chunk advisory from recharts); `npm run dev` serves `/app` (200)
and `/data/metrics.json` (200). Visual QA in-browser (handoff §8, both themes) is the remaining manual
check.

### 2026-06-21 — Showcasing/polish pass (deploy + confusability + §19 extras)
Hackathon is judged by **recorded video + public GitHub repo** with ~1 day left; the stated risk is
"judges won't grasp why it's hard." This pass added the showcasing layer (no new pipeline stages). Plan
file: `~/.claude/plans/ok-now-lets-plan-validated-duckling.md`. Scope decided via Q&A; feedback-loop
TP/FP buttons **deliberately cut** (non-functional buttons read as fake to a judge).

Delivered:
- **Vercel deploy config** — `modules/dashboard/frontend/vercel.json` rewrites SPA routes to
  `index.html` *except* `/data/*` (so the static JSON isn't shadowed by the fallback — a real bug if
  the rewrite were unguarded). Deploy at root: Vite `base` is `/` and `lib/data.jsx` already fetches via
  `import.meta.env.BASE_URL`, so no `vite.config` change. Root Directory = `modules/dashboard/frontend`.
  All 6 data JSON files are committed, so the static deploy has live data immediately. `.env` is
  gitignored and absent from history (verified) — safe to go public.
- **Replay autoplays on mount** — `components/ReplayPanel.jsx` `useEffect` now calls `engine.reset()`
  then `engine.play()` so the demo-window before/after payoff is reached without a click (it's a JS
  interval, not `<video>`, so no autoplay-block).
- **Confusability figure (the headline artifact)** — new `modules/dashboard/figures/confusability.py`
  reads `events_enriched.parquet` + `labels.jsonl` (labels at build time only, never exported) and
  writes `docs/figures/confusability.png`: left = crypto vs legit `burst_rate` distributions overlap
  (10.8 vs 13.9, wide-overlap → indistinguishable to a detector); right = the context features that
  separate them (tag_completeness 0.00 vs 0.54, off_hours 0.83 vs 0.08, spot 0.50 vs 0.00). The
  simulator already ships explicit `crypto_burst↔legit_autoscale` twins keyed by `pair_id`. **Finding:**
  raw wall-clock burst *duration* differs systematically (attacker drips ~70–85 min vs autoscaler ~2
  min) — the honest confusable signal is **burst_rate** (per-window), which is near-identical, NOT raw
  span. The figure is framed on burst_rate accordingly.
- **Root `README.md` created** (none existed) — thesis one-liner → confusability figure → architecture
  diagram → **ablation table** above the fold → run/deploy steps → an "Honest evaluation" section
  pre-empting the two critiques a judge will raise (the cohort=unknown "circularity" and the 68% band
  precision vs 96% precision@50).
- **§19 calibration plot** — `build.py` gained `build_calibration()` (self-contained: loads
  `labels.jsonl` inline, joins `events_scored.p_event`, buckets into reliability bins, emits aggregated
  `{p_mid,predicted,observed,n}` as `metrics.json["calibration"]` — **no per-event label reaches the
  client**). Reliability is near-perfect (predicted≈observed: 0.045≈0.045, 0.39≈0.39, 0.78≈0.79,
  0.999≈0.992). New "Risk Calibration" panel in `pages/Analytics.jsx` (observed curve vs y=x diagonal).
  **Decoupling note:** first draft imported `_load_labels` from `detection.evaluate`, which transitively
  pulls `anomaly.py`→`pyod` into the dashboard build — fragile. Inlined the 4-line label loader instead;
  `build.py` no longer depends on the detector's import graph.
- **§19 forensic-snapshot view** — new "Forensic Snapshot — captured at detection time" block in the
  `pages/RiskFindings.jsx` triage drawer, framed as surviving the resource's disappearance. Pure
  presentation of already-exported incident fields (`resource_ids`, `max_exposure_window_s`,
  `any_privileged`, `max_privilege_level`, `tripwire_hits`, `severity_floor`) — no new export.
- **Per-page captions** sharpened (Dashboard, Analytics). The AI Risk Analyst (Chat) page is already
  honestly framed ("Grounded in Stage-5 triage narratives · offline / cached", "gpt-4o-mini (cached)"
  badge) — left as-is, not dressed up as a live agent.

**Verified:** `python -m modules.dashboard.build` re-exports with `calibration` (5 bins); confusability
PNG renders correctly (bursts overlap left, separate right); `npm install` clean (0 vuln); `npm run
build` green; `npm run preview` serves `/app` 200, `/app/findings` 200, `/data/metrics.json` 200 with
`calibration` present. **Pre-existing env caveat (NOT introduced here):** `pyod` is not installed in
this environment, so stage2/stage5 tests error on import (`ModuleNotFoundError: pyod`) — 16 passed, 1
failed, 33 errors, all the same missing-dep. The dashboard build path does not import pyod, so it runs
clean. To get a green suite, `pip install pyod`. **Remaining manual:** in-browser visual QA of the new
calibration panel + forensic block in **both themes**; create the Vercel project and paste the live URL
into README + the demo-link placeholders.

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
- **Resolved (was open):** Stage-1 anomaly model = **unsupervised ensemble of scikit-learn
  `IsolationForest` (primary) + PyOD `ECOD` (required second vote)**, scores min-max normalized and
  averaged. **TabPFN rejected** (supervised → forces label leakage + a train/test split, heavy dep;
  and its only rationale — avoiding train/tune cycles — is moot since IF has no tune cycle).
  **PyTorch/Keras autoencoder rejected** (overkill + a training loop on ~10k×8 data; ECOD gives the
  "second independent view" without it). Claude-as-few-shot-scorer kept only as a documented
  last-resort fallback. See design doc §16. Decided + implemented 2026-06-20 (see §3).

## 6. How to verify the current state still holds

```bash
pip install -r requirements.txt
python -m modules.data_simulation.generator.build      # regenerate data/raw/ (seed 1337, deterministic)
python modules/data_simulation/validate.py              # expect: 16/16 PASS
python -m modules.ingest_enrich.build                   # -> data/processed/events_enriched.parquet
python -m modules.detection.build                       # -> data/processed/detections.parquet
python -m modules.detection.evaluate                    # P/R/F1 + ablation table
python -m modules.correlation.build                     # -> data/processed/incidents.parquet (+ event_incidents.parquet)
python -m modules.correlation.evaluate                  # alert reduction + correlation accuracy + ablation
python -m modules.risk_fusion.build                     # -> data/processed/incidents_scored.parquet (+ events_scored.parquet)
python -m modules.risk_fusion.evaluate                  # precision/recall@K + recovery + calibration table + ablation
python -m modules.llm_triage.build --no-llm             # -> data/processed/incidents_triaged.parquet (+ triage_cache/, offline)
python -m modules.llm_triage.evaluate                   # coverage + provenance + canonical spot-check + ablation
python -m modules.dashboard.build                       # -> modules/dashboard/frontend/public/data/*.json (Stage 6 export)
python -m pytest tests/ -q                              # expect: 50 passed (6 stage0 + 9 stage1 + 8 stage2 + 8 stage3 + 9 stage4 + 10 stage5)
python modules/data_simulation/replay/stream.py --instant --limit 5   # sanity-check live replay
cd modules/dashboard/frontend && npm install && npm run dev           # Stage 6 console at http://localhost:5173/app
```
Last confirmed: Stage 0 → 9,857 events (4,000/4,357/1,500 per source), 1,710 risky (17.3%), all four
canonical incidents present (`INC-A=40, INC-B=3, INC-C=7, INC-D=2`), 16/16 validator green. Stage 1 →
9,857 enriched rows, label join 1:1, cohort accuracy 100% (non-unknown), confusability preserved.
Stage 2 → full pipeline recall 84.2%, precision 33.6% (precision is won later by fusion), alert
reduction 8%. Stage 3 → 4,288 flagged → 529 incidents, alert reduction 89%, correlation accuracy
homogeneity 0.88 / completeness 0.99 / V-measure 0.93, recall lifted to 100% by bridge expansion.
Stage 4 → 529 incidents scored (44 CRITICAL / 219 HIGH / 266 LOW), precision@50 96% (recovered from
24% event-level), band≥HIGH P=68.4%/R=99.5%, calibration reliability predicted≈observed every bin.
Stage 5 → 263 CRITICAL+HIGH incidents triaged live via gpt-4o-mini (100%, mean confidence 0.852),
existence-based cache reuse makes reruns cost-free (`provenance: cache=263`, zero API calls), all four
canonical incidents triaged, MITRE coverage 100%. Full suite 50/50 green.

## 7. What a new session should do next

1. Read this file, then `docs/ephemeral_risk_detection_analysis.md` for the design rationale behind
   whatever you're about to touch.
2. `modules/dashboard/` (Stage 6) is **built** — a React 19 + Vite + Tailwind console under
   `modules/dashboard/frontend/`, fed by static JSON from `python -m modules.dashboard.build`. To run
   it: regenerate the JSON with `build.py` after any pipeline rerun, then `cd modules/dashboard/frontend
   && npm install && npm run dev`. The replay engine, alert-fatigue funnel, ranked queue, triage drawer,
   and analytics all read the exported JSON only — no live model/LLM calls. Remaining: in-browser visual
   QA (handoff §8, light + dark) and any design polish. If editing the export schema, keep the frontend
   `lib/data.jsx` / page field names in sync.
3. If running the **live** LLM triage (not needed for the dashboard, which reads the cached parquet):
   `cp .env.example .env`, set `OPENAI_API_KEY`, `pip install -r requirements.txt`, then
   `python -m modules.llm_triage.build` (gpt-4o-mini, caches per-incident JSON). The `--no-llm` path
   and the whole test suite need no key.
4. After any meaningful change, append a new dated entry to §3 of this file — don't rewrite history,
   add to it.
