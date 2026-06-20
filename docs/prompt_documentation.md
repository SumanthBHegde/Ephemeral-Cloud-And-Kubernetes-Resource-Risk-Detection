# Prompt Documentation

## Phase 1 - Problem Exploration and Selection

### Goal

Explore all available problem statements, compare them using different metrics, and select the best
one for implementation within the 48-hour hackathon.

---

### Prompt 1

```
This is the detailed flyer given by the Société general for the hackathon.
Add on these to the analysis in the previous chat. and also look at the three
options for the solutions and consider its extended highlight feature we can
implement.

Analyse these and give me the best problem set which is achievable in the time
frame. I will be using claude code with pro subscription so consider it. The
data simulation is the main challenge consider it also.

Rate and compare on several categories including judges perspective and earlier
categories.

Search for the datasets already available, in every place from huggingface to
opendata.

reanalyse on your own metrics do not consider the earlier metrics
```

**Purpose:** Perform an overall comparison while considering feasibility, datasets, judges' perspective,
and available tooling.

---

### Prompt 2

```
How should i implement this. any public datasets available
```

**Purpose:** Explore implementation ideas and available public datasets.

---

### Prompt 4

```
These are the 4 praoblem sets provided by the Socite general , ihackmyplace
campus hackathon for rvce.

we have been provided with these problem sets and need to find a solution mvp
within 48 hours,

explore the problem set and exaplain problem set one by one as i say,
cover the background research. why it is needed, who are the stakeholders, how
this will impact, whats the business impact, what are the ways we can approach
the problem to find a solution beyond winning, give the resources and links to
do further research.

lets start with one
```

**Purpose:** Perform detailed background research on each problem statement.

---

### Prompt 5

```
Analysis: Make several criteria's to rank these problem sets. Some of which can
be difficulty, business impact, demo and deployment and other standard used
metrics in the development of the solutions.

also consider the fact that Société Générale is the one valuating these
solutions and how likable the solution will be for judges.

The data structure will be provided but we need to generate the data and the
cases.

Compare them based on the analysis.
```

**Purpose:** Create a structured evaluation framework for comparing the problems.

---

### Prompt 6

```
https://societegenerale.iamneo.ai/pb-5-grc-exception-policy-waiver-management/
https://societegenerale.iamneo.ai/third-party-vendor-risk-management/
https://societegenerale.iamneo.ai/ephemeral-cloud-kubernetes-resource-risk-detection/
https://societegenerale.iamneo.ai/identity-sprawl-privileged-access-abuse-detection-in-hybrid-enterprises/

each problemset is contained in each url
now they have given proper extended problem sets and the possible solutions.
on these new updates data now make the same classification and compare the
problem sets.

Ask me if there are any doubts.
```

**Purpose:** Re-run the comparison using the updated official descriptions.

---

### Prompt 7

```
there are 3 options to solve each problem see all, we will need to do something
beyond the advanced to grab attentions
```

**Purpose:** Brainstorm enhancements beyond the official solution options.

---

### Prompt 8

```
https://societegenerale.iamneo.ai/ephemeral-cloud-kubernetes-resource-risk-detection/

more about this

here in the option a) they have given difficulty of 5/5 can you explain that.
and whats the businees impact score you would give it.
Note that is one of the problem sets provided by the societe generale 48hours
hackathon
```

**Purpose:** Understand the complexity and business value of Problem Statement 3.

---

### Prompt 9

```
analyse with same thing for this problem set [3rd ps]
```

**Purpose:** Continue detailed analysis of Problem Statement 3.

---

### Prompt 10

```
Now do the comparative study and which is better to take as a problem set for
hackathon
```

**Purpose:** Decide the best problem statement to choose.

---

### Prompt 11

```
Similarly analyse this and do the comparative analysis [4th ps]
```

**Purpose:** Compare the remaining problem statements using the same methodology.

---

### Prompt 12

```
no I meant adding some of the features of option b and c to a and building a wow
factor to it.
also for ml (ps 3 and ps 4), is there any thing i can use from newer
implementations as transformers or different architecture
```

**Purpose:** Explore advanced features and modern ML architectures.

---

### Prompt 13

```
ask me some of the questions so that you could suggest me the correct problem
set
```

**Purpose:** Refine the recommendation based on team capabilities.

---

### Prompt 14

```
i am leaning more towards 3rd problem set, so what should i know to build this
and is the business impact high for this
```

**Purpose:** Validate the choice of Problem Statement 3.

---

### Prompt 15

```
i know basic graph knowledge, If it were you to build the synthetic data how
would you do it
```

**Purpose:** Plan synthetic data generation.

---

### Prompt 16

```
is there any huggingface datasets which can take some of the feilds from
```

**Purpose:** Find reusable public datasets.

---

### Prompt 17

```
In the options A and B, I want to approact it like combining backend engineer
skills with the approach A(ML Engineer).
How would you tackle it
```

**Purpose:** Design a hybrid backend + ML implementation strategy.

---

### Prompt 18

```
I am choosing Ephemeral Cloud problem, so once again analyse the deliverables
with success criteria and data structure descriptions
```

**Purpose:** Understand deliverables and expected outputs.

---

### Prompt 19

```
Create single analysis file by compiling all the learing into a single file on
problem set 3 Ephemeral Cloud problem and export it.
It should include all the analysis you have done till now on that problem set
```

**Purpose:** Consolidate all research into one reference document.

---

### Prompt 20

```
Can we build a real time api of the data for this anomaly soluiton of Ephemeral
Cloud
```

**Purpose:** Explore real-time streaming and API integration.

---

### Prompt 21

```
According to the given problem statement what are they expecting and what will
be the wow factor
```

**Purpose:** Understand judging expectations and differentiating features.

---

### Prompt 22

```
we have choosed the third problem set. lets plan how we can overcome this
problem what should be the flow of the problem
```

**Purpose:** Plan the end-to-end implementation flow.

---

### Prompt 23

```
give me the detailed MD of analysis and flow of the this problem, option A with
extra beyond winning.
```

**Purpose:** Generate detailed planning documentation.

---

### Prompt 24

```
[used data_resource_research.md as prompt to create dataset]
```

**Purpose:** Use prior research to guide synthetic dataset creation.

---

### Prompt 25

```
We need to create a scaffold of project folder structure.
make proper structured folder tree according to the flow of the project and name
it properly with subfolders. add gitkeep for the folders
organise the current files in the respective folders.
ask quesiton if needed
```

**Purpose:** Create a clean project structure.

---

### Prompt 26

```
make a context.md as single source of truth of progress,
it should contain everything about what happend, when, why, and flow and
progress,
it should be like when a new ai session start by reading this md it should get
the complete context of what has happend.
also update the claude.md
context.md should be updated after every conversation
```

**Purpose:** Maintain project continuity and documentation across AI sessions.

---

## Result of Phase 1

- Explored all four hackathon problem statements.
- Performed multiple rounds of comparative analysis.
- Researched datasets and synthetic data strategies.
- Evaluated implementation feasibility and judge appeal.
- Planned enhancements beyond the baseline solutions.
- Selected **Problem Statement 3 – Ephemeral Cloud Kubernetes Resource Risk Detection** as the
  final project.

---

## Phase 2 - Stage One Build (Ingest & Enrich)

### Goal

Build Stage 1 of the detection pipeline: normalize the three authentic Stage-Zero sources into one
unified event schema, assign behavioral cohorts, and compute per-event context features (§5 of
design doc) that unblock the two-stage detector.

---

### Prompt 27

```
See the @context.md and at the end of the iteration update the context.md.
Now in the ingest and enrich we have to use the replay of the data_simulation to simulate the logs.
Essentially the data cleaning also takes place. You are the lead developer here, ask questions
whenever necessary about the model. I think we need to parse the jsonl to csv for next layer
correct me if necessary.
```

**Purpose:** Plan Stage 1 (ingest_enrich) with design decisions about data format, consumption mode,
cohort assignment, and feature engineering scope.

**Key decisions locked:**
- Output format: **Parquet only** (not CSV) — per design doc §16; CSV is lossy on nested/list columns
- Consumption mode: **Both** — batch file-read (deterministic) + live stream wrapper (demo)
- Scope: **Full Stage 1** — normalize + clean + all §5 features + §6 cohorts
- Cohort method: **Rule-assisted, deterministic** (K8s SA → CloudTrail role → IdP prefix → CIDR)
- Cohort baseline: **Empirical from data** (not config) — avoids circularity

---

### Prompt 28

```
/init
Please analyze this codebase and create a CLAUDE.md file, which will be given to future instances
of Claude Code to operate in this repository.
```

**Purpose:** Initialize/update CLAUDE.md with Stage 1 completion, practical commands, and module
status.

---

## Result of Phase 2

- **Stage 1 built and verified:** normalizer (3 sources), rule-assisted cohort assignment,
  §5 feature engineering pipeline, batch + live streaming modes.
- **Output:** `data/processed/events_enriched.parquet` — 9,857 enriched rows, label join 1:1.
- **Tests:** 9/9 green (normalization, features, cohorts, confusability, determinism).
- **Full test suite:** 15/15 passed (6 Stage 0 + 9 Stage 1).
- **Key finding:** 629 rows assigned `unknown` cohort — exactly the identity_anomaly attack
  (contractor-* federated users, all `is_risky=1`). Cohort accuracy 100% on 9,228 recognizable
  principals.
- **Confusability verified:** crypto vs legit burst_rate overlap (10.82 vs 10.57), separation
  from metadata (tag_completeness 0.00 vs 0.41, off_hours 0.83 vs 0.07).
- **Updated:** context.md (chronological entry + status table), CLAUDE.md (repo status, commands,
  Stage 1 overview).

---

## Phase 3 - Stage Two Build (Two-Stage Detection) + Model Decision

### Goal

Resolve the open ML-model decision (Isolation Forest vs. TabPFN vs. autoencoder) and build Stage 2:
the two-stage detector (recall-first anomaly ensemble + cohort-aware suppression) over the enriched
feature table.

---

### Prompt 29 (Synthesized from session)

```
In this part which is the best approach to achieve our goal? We have different libraries like
scikit-learn, PyTorch, transformers, etc. Which is the best approach to follow based on our
ingest and enrichment phase? Update the @docs/ephemeral_risk_detection_analysis.md according to it.
```

**Purpose:** Resolve the Isolation-Forest-vs-TabPFN tension and choose the ML stack for detection.

**Key decisions locked:**
- **Stage-1 model:** unsupervised ensemble of scikit-learn `IsolationForest` (primary) + PyOD `ECOD`
  (required second vote)
- **Why IF+ECOD:** ~10k×8 tabular is IF's sweet spot; unsupervised (preserves held-out-label
  honesty); no training loop; keeps stack on sklearn (which also does §9 calibration)
- **Why ECOD required:** parameter-free, deterministic, interpretable per-dimension contributions
  (evidence for LLM-triage bundle)
- **Rejected:** TabPFN (supervised → forces label leakage + train/test split; rationale evaporates
  since IF has no tune cycle), PyTorch/Keras autoencoder (overkill + training loop on data this
  small)
- **Transformers/LLM:** stay where they belong — Stage 5 (llm_triage), not detection

---

### Prompt 30 (Synthesized from session)

```
Now implement Stage 2 — the full two-stage detector with the tripwires, anomaly ensemble, and
cohort suppression. Make it pass the required recall and alert-reduction targets. Write tests.
```

**Purpose:** Build the complete detection module mirroring Stage 1's structure and conventions.

**Implemented:**
- `modules/detection/detect/tripwires.py` — always-on rules (NodePort 0.0.0.0/0, bare privileged
  pod, `burst_rate>10`, broad RBAC, `cohort=="unknown"` as a context tripwire)
- `modules/detection/detect/anomaly.py` — Stage 1, recall-first: IF + ECOD ensemble, min-max
  normalized and averaged, `is_candidate` = top ~35% by ensemble_score
- `modules/detection/detect/suppression.py` — Stage 2, cohort-aware: suppress candidates that are
  normal for their cohort (low `cohort_deviation`, complete tags, in-hours, not tripwires)
- `modules/detection/pipeline.py` (`run_detection`), `build.py` (CLI), `evaluate.py` (label join,
  P/R/F1, ablation table), real `README.md`, `tests/test_stage2.py`
- **Key finding:** the IF+ECOD ensemble alone reached ~47% recall — structurally cannot catch the
  629 `identity_anomaly` rows (unknown cohort, dense same-shape cluster, not sparse outliers).
  Adding `cohort=="unknown"` as a tripwire lifts recall to **84.2%** with near-zero added FP.

---

## Result of Phase 3

- **Stage 2 built and verified:** three-layer detector (tripwires + recall-first ensemble +
  cohort suppression), full pipeline end-to-end.
- **Output:** `data/processed/detections.parquet` — enriched rows + `if_score`, `ecod_score`,
  `ensemble_score`, `is_candidate`, `tripwire_hit`, `is_suppressed`, `predicted_risky`,
  `severity_floor`.
- **Tests:** 8/8 green (schema, determinism, recall floor, suppression behavior, unknown-cohort
  safety, tripwire enforcement).
- **Full test suite:** 23/23 passed (6 Stage 0 + 9 Stage 1 + 8 Stage 2).
- **Ablation table (verified):**
  | Configuration | Precision | Recall | Alert reduction |
  |---|---|---|---|
  | tripwires only | 43.5% | 72.5% | 38% |
  | + Stage-1 ensemble | 31.1% | 84.2% | 0% |
  | + Stage-2 suppression (full) | 33.6% | 84.2% | 8% |
- **Recall target (>70%):** ✓ met at 84.2%.
- **Precision:** intentionally low (33.6%) at this stage — won later by graph + fusion (≥40%
  alert reduction also lands there).
- **Updated:** design doc §7/§16/§20 (model decision resolved), detection README, CLAUDE.md,
  requirements.txt (+scikit-learn, pyod, scipy), context.md (status table + chronological
  history).

---

## Phase 4 - Stage Three Build (Graph Correlation)

### Goal

Cluster Stage-2 detection flags into incidents using a NetworkX entity graph. This is where the
headline **alert reduction** is won (40 autoscaler alerts → 1 incident) and where cross-source
chains become single traced incidents. Lock the graph design (especially the seed-originated 1-hop
guarantee and the time/namespace envelope) and verify canonical incident recovery.

---

### Prompt 31 (Synthesized from session)

```
Plan Stage 3 — the correlation module. The user asked two critical design questions:
1. Which events should become nodes? (flagged-only vs. anchored with 1-hop expansion)
2. What outputs should Stage 3 emit? (incidents only vs. both incidents + event map)

Lock these decisions via Q&A, then design the implementation plan with exact schema specs
(source_*_count, edge_types, tripwire_hits) to prevent implementation drift.
```

**Purpose:** Plan Stage 3 with user-locked design decisions before touching code.

**Key decisions locked via user Q&A:**
- **Graph scope:** Flagged seeds + 1-hop expansion (not flagged-only, not full 9,857-event graph)
  — seed from `predicted_risky`, expand one hop along strong linkage keys to pull in bridge events
  (e.g. INC-C's benign IdP login connecting the compromised session)
- **Output:** Both — `incidents.parquet` (primary for risk_fusion) + `event_incidents.parquet`
  (per-event map, all 9,857 events; non-members get `incident_id=None` for risk_fusion's timeline
  and the dashboard's inventory view)
- **`source_*_count` schema:** Three flat int columns (not dict) — `source_cloudtrail_count` /
  `source_k8s_count` / `source_idp_count`, derived with fixed mapping to literal source values
  (`cloudtrail` / `k8s_audit` / `idp_session`) + `.get(..., 0)` to avoid KeyError
- **Alert-reduction denominator:** Locked to `tripwire_hit | is_candidate` — identical to Stage 2's
  denominator (verified at `detection/evaluate.py:64`) so the 8% → ≥40% jump is apples-to-apples

**Five plan-review rounds identified drift risks:**
1. 1-hop enforcement must be at **build time** (not component time) — spec explicit so implementation
   can't silently do 2-hop expansion
2. INC-C test dependency on IdP login being flagged — **verified** (all 7 INC-C members are
   `predicted_risky=True` via `tripwire_hit`)
3. Alert-reduction denominator must be consistent — **locked** to Stage 2's denominator
4. `source_mix` storage format — **changed to flat ints** from dict to keep table vectorizable
5. Events not in any incident — **explicit handling**: they receive `incident_id=None` and still
   appear in `event_incidents.parquet`

---

### Prompt 32 (Synthesized from session)

```
Implement Stage 3 — the full graph-correlation module. Build:
- graph/entities.py (edge specs, time-cluster helpers)
- graph/build_graph.py (MultiGraph, seed-originated edges, 1-hop envelope)
- graph/incidents.py (connected components → incident rows)
- pipeline.py, build.py, evaluate.py (mirroring Stage 2 structure)
- test_stage3.py (8 tests per plan)

Verify: alert reduction ≥40%, canonical incident recovery, 1-hop guarantee, correlation accuracy
vs campaign_id.
```

**Purpose:** Implement the complete correlation module test-first.

**Key design note (deliberate deviation from §8):**
Design §8 specifies entity-node graph (principals/sessions/resources as nodes, events as edges).
Implementation inverts to **event-node graph with time-gated, typed edges** because:
- Entity-node model cannot enforce the identity+namespace+time envelope — one `replicaset-controller`
  node would chain every autoscaler burst across 5 days into one mega-incident
- Event-node model enforces the envelope **structurally at edge-creation time**: edges exist only
  between events within a time window AND in the same namespace (cloud events group by identity)
- The invariant **every edge has ≥1 seed endpoint** prevents 2-hop bridge expansion
- Connected-component output is functionally identical to §8; the incident artifact still surfaces
  the entity view (`principal_ids`, `namespaces`, `resource_ids`, `edge_types`)

**Implemented:**
- `graph/entities.py` — 5 edge specs (same_principal, same_session, external_session, shared_event,
  same_resource), each with a linkage key and time window (30 min weak keys, 2 h resource window);
  time_cluster_ids helper for gating
- `graph/build_graph.py` — MultiGraph builder; star-connects seed-containing clusters from seed
  rep (enforces the **every edge has ≥1 seed endpoint** invariant); isolated seeds added as nodes
- `graph/incidents.py` — connected-components → incident rows (INCIDENT_COLS schema); deterministic
  numbering by (start_time, smallest record_id); ground-truth columns joined only in evaluate.py
- `pipeline.py` — `correlate(df)` (pure) + `run_correlation(source, out_path, map_out)` (CLI-facing)
- `build.py` — argparse CLI with summary stats (incidents, members, multi-event, high-severity,
  cross-source)
- `evaluate.py` — reuses `_load_labels()` and `_prf()` from detection; adds
  `sklearn.homogeneity_completeness_v_measure` for correlation accuracy vs `campaign_id`; extends
  ablation table with `+ graph correlation` row
- `test_stage3.py` — 8 tests: schema, one_hop_only, autoscaler_collapse, cross_source_chain,
  credential_abuse_captured, envelope_no_overmerge, alert_reduction_target, event_map_complete
- README.md, graph/__init__.py

**Verified (python -m modules.correlation.evaluate):**
- **Alert reduction: 89%** (4,638 raw flags → 529 incidents; target ≥40%)
- **Correlation accuracy vs campaign_id:** homogeneity 0.88, completeness 0.99, V-measure 0.93
- **Canonical recovery:** INC-A 40→1, INC-B 3→1, INC-C 7→1 (cross-source), INC-D 2→2 (by design;
  the credential-abuse `rbac_change` still surfaces as HIGH)
- **Bridge expansion recovery:** recall lifted 84% → 100% (unflagged risky events recovered by
  1-hop from seeds)
- **Extended ablation:**
  | Configuration | Precision | Recall | Alert reduction |
  |---|---|---|---|
  | tripwires only | 43.5% | 72.5% | 38% |
  | + Stage-1 ensemble | 31.1% | 84.2% | 0% |
  | + Stage-2 suppression | 33.6% | 84.2% | 8% |
  | **+ graph correlation** | **24.1%** | **100%** | **89%** |

---

## Result of Phase 4

- **Stage 3 built and verified:** event-node graph with seed-originated 1-hop edges, time/namespace
  envelope, deterministic incident numbering, full structure mirroring Stages 1–2.
- **Output:** `data/processed/incidents.parquet` (529 rows, INCIDENT_COLS schema) +
  `data/processed/event_incidents.parquet` (9,857 rows, complete event map)
- **Tests:** 8/8 green (schema, 1-hop enforcement, autoscaler collapse, cross-source chain,
  credential-abuse capture, envelope hold, alert reduction, event map completeness)
- **Full test suite:** 31/31 passed (6 Stage 0 + 9 Stage 1 + 8 Stage 2 + 8 Stage 3)
- **Design deviation (documented):** inverted §8's entity-node to event-node with time-gated edges
  to enforce the envelope structurally. Functionally equivalent output; better correctness.
  Updated README, entities.py, build_graph.py, context.md with explicit reasoning.
- **Key findings:**
  - 1-hop guarantee (every edge has ≥1 seed endpoint) prevents 2-hop bridge leakage
  - Bridge expansion recovers ~16% missed detections (recall 84% → 100%)
  - Event-level precision drops to 24% at correlation (expected; incident-level ranking is next stage's job)
  - Homogeneous incident formation: V-measure 0.93 vs `campaign_id` (very tight grouping)
  - Envelope holds: namespace-partitioned bursts never merge unrelated web/prod activity
- **Updated:** CLAUDE.md (Stage 2→3 status), requirements.txt (+networkx>=3.0), context.md
  (chronological entry + status table + next-step pointer to risk_fusion), README.md (graph model
  inversion rationale), entities.py / build_graph.py (docstrings updated).
