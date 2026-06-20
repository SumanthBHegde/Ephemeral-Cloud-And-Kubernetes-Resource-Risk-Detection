# Ephemeral Cloud & Kubernetes Resource Risk Detection — Comprehensive Analysis

**Track:** Cloud Security Governance & Risk  
**Status:** Selected as final hackathon build  
**Team:** 2 people, full-stack + ML background, new to graph algorithms and NLP, comfortable with LLM APIs  

**Document purpose:** Single source of truth for problem analysis, architecture, data flow, build plan, and evaluation. Authority hierarchy: this document > CLAUDE.md guidance > subsidiary READMEs.

---

## Executive Summary

Ephemeral cloud and Kubernetes resources — CI/CD job pods, spot instances, assumed-role sessions, autoscaled containers — live for minutes and then disappear. Traditional security controls (quarterly scans, daily inventory syncs) run too slowly to see them, and the high-volume noise from legitimate autoscaling and CI/CD buries the rare malicious event.

This design builds a **near-real-time detection pipeline** that discovers ephemeral assets, classifies them, scores risk, correlates related events into incidents, and produces analyst-ready narratives with MITRE mapping and remediation.

**The central thesis that drives every design decision:** at the *event* level, a legitimate autoscaler burst and a crypto-mining hijack are statistically identical — same API calls, same burst rate. The signal that separates them is not in the event; it is in the **context** — the identity's behavioral cohort, pattern novelty, resource exposure, and how events relate to each other across cloud, K8s, and IAM logs. A system that detects on events alone will fail on the ambiguous cases this project exists to solve. Detect on context.

---

## 1. The Problem

### 1.1 Why ephemeral resources break traditional security

| Traditional assumption | Ephemeral reality |
|---|---|
| Assets are stable; inventory can be synced daily | Assets exist for minutes; a daily sync never sees them |
| Each alert maps to a durable resource to investigate | The resource is gone before triage; no forensic evidence remains |
| Identities are long-lived and can be baselined | Sessions have 15-minute TTLs; no stable identity to baseline against |
| Alert volume is manageable | Autoscaling and CI/CD generate thousands of near-identical events |

### 1.2 Concrete business impact: The four canonical incidents

1. **Crypto-mining via compromised CI/CD account** — 20 spot VMs at 3 AM, terminated before the SOC shift. Lost: $14,000 in 90 minutes; zero alerts fired. *Demands:* off-hours + novelty + cohort-deviation detection, and detection latency shorter than the resource lifetime.

2. **Debug pod with NodePort exposed to 0.0.0.0/0** — ran 11 minutes, exploited by an external scanner. Exposure window: the pod lived, was exploited, and died before traditional scanning could catch it. *Demands:* exposure scoring that distinguishes a load balancer (public IP normal) from a debug pod (public IP dangerous).

3. **Assumed-role session reads PII from S3** — session expired in 15 minutes, never correlated to the compromised Lambda that triggered it. *Demands:* cross-source graph correlation linking Lambda → session → S3 access.

4. **Autoscaler burst of 40 pods** — 40 false-positive alerts buried a real credential-abuse alert. *Demands:* correlation that collapses 40 alerts into 1 incident, plus suppression of cohort-normal bursts.

### 1.3 The ambiguity problem (the heart of the challenge)

Every hard case is a pair of look-alikes the system must separate:

- 40 pods in 2 minutes → **HPA autoscale** or **resource hijacking**?
- Spot VM with public IP and no tags → **misconfigured CI job** or **attacker staging**?
- Assumed-role session hits S3 at 3 AM → **scheduled Lambda** or **compromised credential**?
- Privileged debug pod runs 5 minutes → **developer troubleshooting** or **container escape**?

If your simulated malicious events are trivially separable from benign ones, your metrics look great but prove nothing. **The quality of the entire solution is gated by how confusable the simulator makes these pairs.** (See §5 on data simulation design.)

### 1.4 Difficulty assessment: 4/5 (not 5/5 because)

- **No real data, and that's a simplification, not a setback.** You simulate your own telemetry and control the ground truth.
- **The core ML task is well-trodden.** Isolation Forest / autoencoder-style anomaly detection on engineered features is a standard applied-ML pattern.
- **The genuinely hard part is feature engineering** — building signals that separate "HPA burst" from "crypto-mining burst" when they look identical in raw API patterns.
- **NetworkX-based incident correlation** is the most algorithmically substantial piece, but it's a single well-defined task.
- **The LLM layer is the "easy" hard part** — narrative generation from already-structured, already-scored data is gentler than extracting structure from unstructured text.

### 1.5 Business impact: 4/5

- **Direct, quantifiable financial exposure.** The Case 1 scenario (20 spot VMs, $14,000 in 90 minutes) is a concrete, recurring abuse pattern — money leaving in real time.
- **The core thesis is sharp and demo-able:** "ephemeral resources exist for minutes, attackers need less" directly indicts the standard quarterly/daily scan cadence as structurally unable to catch this class of risk.
- **Alert fatigue is a real, common SOC failure mode.** Case 4 (40 legitimate autoscaler alerts burying one real credential-abuse alert) has direct, easily quantified analyst-hours payback.
- **Forensic blind spot:** "the resource is gone before the alert gets triaged" is a genuine, hard-to-work-around operational gap in most cloud-native orgs.

---

## 2. Solution Thesis: Context Beats Events

The naive approach — one anomaly model over all events, clustered by time window — fails predictably:

- The model either flags every burst (precision collapses) or learns to ignore bursts (recall collapses on real attacks).
- Time-window clustering groups co-occurring events but cannot link a Lambda to the S3 access its stolen session performed minutes later.

The winning solution replaces event-level detection with **context-aware detection** built on four key differentiators:

1. **Behavioral cohorts** replace per-identity baselines.
2. **Two-stage detection** separates recall (model) from precision (context suppression).
3. **Graph correlation** surfaces campaigns spanning all three log sources.
4. **LLM triage** reasons over assembled evidence and disambiguates the hard cases.

---

## 3. Architecture & Data Flow

```
[Cloud audit] [K8s events] [Identity/session]
        \          |          /
         v          v         v
(1) Ingest + enrich       -> normalize to unified schema; assign behavioral cohort;
                             compute novelty + exposure features
         |
         v
(2) Rules + stat baselines -> hard tripwires (always-on, force severity floor)
         |                    z-scores per namespace/principal
         |
         v
(3) Anomaly model          -> Isolation Forest / autoencoder, recall-first
         |
         v
(4) Context suppression    -> suppress events normal for their cohort
         |
         v
(5) Graph correlation      -> entity graph (principal→session→resource→ns→action),
         |                    incidents = connected components
         v
(6) Risk fusion + calib.   -> combine anomaly score, signals, exposure, novelty,
         |                    privilege into a calibrated 0-1 risk score
         v
(7) LLM triage agent       -> structured JSON: intent, confidence, MITRE, guardrails;
         |                    forensic snapshot captured at detection time
         v
(8) Dashboard + forensics  -> inventory, TTL distribution, burst timeline, incident
                              queue with drill-down; analyst feedback → loop
```

### Stage-by-stage breakdown

**(1) Ingest + enrich.** Read three sources into one normalized event schema. Compute per-event features and assign each principal to a behavioral cohort. This solves the "no stable identity to baseline" problem — a freshly created ephemeral pod inherits its cohort's baseline instantly.

**(2) Rules + statistical baselines.** Lightweight, always-on tripwires (public IP on non-LB, privileged pod without owner, burst >10 in 5 min, off-hours activity) combined with z-score/IQR baselines per namespace and principal. These act as a pre-filter and set a severity floor that the ML model cannot override.

**(3) Anomaly model.** Train an Isolation Forest (primary; fast, interpretable) on the feature matrix of normal CI/CD and autoscale patterns. Tune for **high recall** — over-flagging at this stage is acceptable and expected.

**(4) Context suppression.** For each flagged candidate, check whether it is normal *for its cohort* (e.g., an HPA scaling event with matching traffic metric, a CI job from a recognized service account with complete tags). Suppress cohort-normal events. This is where precision is won without sacrificing recall from stage 3.

**(5) Graph correlation.** Build a NetworkX multigraph of entities and relationships across all three sources. Incidents are connected components (or dense subgraphs) within an identity + namespace + time envelope. This collapses 40 alerts into 1 incident and links the Lambda → session → S3 chain.

**(6) Risk fusion + calibration.** Fuse anomaly score, rule/signal matches, exposure window, privilege level, and novelty into a single risk score, then calibrate (isotonic or Platt) so a 0.8 means roughly 80% likely-malicious. Calibrated scores are interpretable and rank the incident queue meaningfully.

**(7) LLM triage agent.** Pass the assembled incident evidence to an LLM that returns **validated structured JSON** — likely intent, confidence, MITRE technique(s), and specific guardrails. It disambiguates hard cases by weighing enriched features. A forensic snapshot of the resource state is captured at detection time so the incident survives the resource's disappearance.

**(8) Dashboard + forensics + feedback.** Interactive dashboard (ephemeral inventory, TTL histogram, burst timeline, incident queue with drill-down). Analyst TP/FP decisions feed back to stage 4 suppression, closing the loop.

### Critical ordering catch — score AFTER clustering, not before

Read the pipeline order literally: lightweight rule/statistical detection flags candidates *first*, clustering groups them *second*, and **risk scoring happens at the incident level, after clustering**. Three individually low-scoring events from the same principal in the same 5-minute window can be one high-severity incident together. Per-event scoring before clustering misses this; do not reorder these stages.

---

## 4. Data Simulation Design (Foundation)

The simulator is the foundation; every downstream metric depends on it. It must be richer than a basic generator in three ways.

### 4.1 Volume and source mix

| Source | Records | Key fields |
|---|---|---|
| Cloud audit logs | 800–1,000 | timestamp, principal, action (RunInstances/AssumeRole/CreateBucket…), resource_id, tags, public_ip, region |
| Kubernetes events | 800–1,000 | timestamp, namespace, pod, action (create/delete/expose), labels, controller_owner, security_context, service_type |
| Identity/session logs | 300–500 | timestamp, principal, session_id, role, ttl, source_ip, federation/idp, actions_performed |

**Total: 4–5k events over a 5-day span.**

### 4.2 Required label columns (most teams skip these — don't)

Every event row must carry:

- `is_risky` (0/1) — ground truth for precision/recall.
- `scenario_type` — e.g., `crypto_burst`, `public_exposure`, `identity_anomaly`, `legit_autoscale`, `legit_cicd`, `routine`.
- `cohort` — ground-truth behavioral cohort (`ci_runner`, `hpa_autoscaler`, `human_dev`, `scheduled_lambda`).
- `campaign_id` — **shared across all events of the same attack, across all three sources.** Without it, graph correlation accuracy is unmeasurable.

### 4.3 Anomaly mix (target distribution)

| Class | Share | Role |
|---|---|---|
| Resource hijacking (crypto bursts) | 5–8% | true positives to catch |
| Public exposure of ephemeral compute | 3–5% | true positives to catch |
| Unexpected identity/session activity | 5–8% | true positives to catch |
| Legitimate autoscaling / CI/CD bursts | 40–50% | **noise to suppress** |
| Routine ephemeral lifecycle | 30–40% | normal background |

### 4.4 The confusability requirement (the single hardest design principle)

Legitimate autoscale/CI bursts (40–50% of the data) and malicious resource-hijacking bursts (5–8%) **must look structurally similar in volume and timing**. They should differ in **metadata completeness and ownership**, not size or speed:

- **Legitimate burst** → complete tags (`managed-by: autoscaler`), real `controller_owner`, proper labels.
- **Malicious burst** → sparse/missing tags, `controller_owner: None`, spot instances with no business justification.

For each malicious scenario, generate a **benign look-alike** that shares surface features:

- Crypto burst ↔ HPA autoscale: same RunInstances/pod-create rate; differ only in time-of-day, principal novelty, tag completeness, and absence of a matching traffic metric.
- Attacker staging VM ↔ misconfigured CI VM: both untagged with a public IP; differ in cohort and session lineage.
- Compromised session ↔ scheduled Lambda: both assumed-role S3 access at 3 AM; differ in whether a known scheduler triggered the session.

**Generate with a fixed random seed for reproducibility.**

Making the malicious bursts bigger or faster than legitimate ones renders the problem artificially easy and makes the noise-reduction metric meaningless. Do not do this.

---

## 5. Feature Engineering

Per-event and per-window features feeding the model:

- **Burst rate** — count of same-action events by the same principal in a rolling 2–5 minute window.
- **Principal novelty** — has this principal (or this cohort-member pattern) been seen before in the baseline window?
- **Tag completeness** — fraction of expected tags present (ownership, environment, cost-center).
- **Privilege level** — derived from role/RBAC and security context (privileged pod, broad IAM policy).
- **Public exposure flag** — public IP / NodePort / 0.0.0.0/0, weighted by resource type (LB = normal, debug pod = risky).
- **TTL / exposure window** — how long the resource was (or is expected to be) alive and reachable.
- **Off-hours flag** — activity outside the principal's cohort-normal hours.
- **Cohort-deviation score** — distance from the cohort's feature centroid (the key contextual feature).

---

## 6. Behavioral Cohorts — Differentiator #1

Per-identity baselines are impossible for ephemeral identities. Instead:

1. **Build cohorts** by clustering principals on their action signatures (k-means/DBSCAN over action histograms, or rule-assisted assignment using naming conventions + service-account metadata).
2. **Baseline the cohort**, not the individual — normal hours, normal burst sizes, normal exposure, normal tag completeness.
3. **Score new ephemeral identities against their cohort** instantly on first appearance.

This converts the brief's stated blocker ("no stable identity to baseline") into the solution's strongest signal.

---

## 7. Two-Stage Detection — Differentiator #2

**Stage 1 (recall-first).** An **unsupervised ensemble** over the feature matrix, threshold tuned so true attacks are almost never missed; expect many candidates. Two complementary detectors vote and their min-max-normalized scores are averaged: **Isolation Forest** (scikit-learn) as the primary, and **ECOD** (PyOD — Empirical-Cumulative-distribution Outlier Detection) as a required second vote. ECOD is parameter-free, deterministic, and exposes per-dimension outlier contributions that become evidence for the LLM-triage bundle. Neither sees the held-out labels. (See §16 for why this pairing was chosen over TabPFN / an autoencoder.)

**Stage 2 (precision via context suppression).** Drop candidates that are normal for their cohort:
- HPA scaling event with a corresponding traffic/CPU metric → suppress.
- CI job from a recognized service account with complete tags and in-cohort hours → suppress.
- Otherwise → promote to correlation.

**Why this works:** the split lets the system hit **precision > 75% and alert reduction ≥ 40% simultaneously**, rather than trading one for the other. The rule/statistical pre-filter narrows the data so the ML layer only ever sees the harder, already-filtered cases.

---

## 8. Graph Correlation — Differentiator #3

Build a NetworkX multigraph:

- **Nodes:** principals, sessions, resources, namespaces, actions.
- **Edges:** "assumed", "created", "accessed", "exposed", "owns", weighted by time proximity and shared identity.
- **Incidents:** connected components (or dense subgraphs) constrained to an identity + namespace + time envelope.

Outcomes this unlocks:
- 40 autoscaler alerts → 1 connected component → 1 incident (noise reduction made literal).
- Lambda → assumed-role session → S3 access becomes a single traced subgraph, which time-window clustering alone cannot recover.

**Score graph correlation** against `campaign_id` ground truth (homogeneity / completeness or pairwise precision-recall on co-membership).

---

## 9. Risk Fusion & Calibration

Fuse component signals into one score:

```
raw_risk = w1*anomaly_score
         + w2*signal_matches
         + w3*exposure_window_norm
         + w4*privilege_level
         + w5*novelty
```

Then **calibrate** (scikit-learn isotonic or Platt scaling against held-out labels) so the final 0–1 score behaves like a probability. Aggregate event scores into an incident score (max + mean blend, or a learned aggregator). Calibrated scores rank the analyst queue truthfully and make the dashboard's "risk = 0.82" meaningful rather than arbitrary.

---

## 10. LLM Triage Agent — Differentiator #4

The LLM is a **triage agent**, not a prose generator. For each incident it receives the assembled evidence bundle (events, graph subgraph, cohort context, scores) and returns **validated structured output**:

```json
{
  "incident_id": "INC-0427",
  "likely_intent": "Resource hijacking for cryptocurrency mining",
  "confidence": 0.86,
  "mitre": ["T1496", "T1578"],
  "key_evidence": [
    "20x RunInstances by ci-runner-sa within 3 min at 03:14 UTC",
    "principal novel for cohort 'ci_runner' at this hour",
    "no matching CI pipeline trigger; instances untagged"
  ],
  "disambiguation": "Burst rate matches HPA autoscale, but off-hours + no traffic metric + tag gaps indicate hijack",
  "recommended_guardrails": [
    "Enforce SCP spot-fleet quota per service account",
    "Require cost-center tag at provisioning; deny untagged RunInstances",
    "Alert on off-hours RunInstances by CI cohort"
  ]
}
```

**Operational discipline for the demo:**
- **Strict JSON schema** with validation and retry; reject and re-prompt on malformed output.
- **Cache responses** so the live demo never depends on a network call mid-presentation.
- **Templated fallback narrative** if the API is unavailable — the pipeline still produces a usable card.

### Forensic snapshot

At detection time, serialize the resource's observed state (config, tags, exposure, session lineage) into the incident record so investigation is possible **after the resource is gone** — directly addressing "post-incident forensics are impossible."

---

## 11. Feedback Loop

Analyst TP/FP decisions on the dashboard update stage-2 suppression (e.g., add a confirmed-benign cohort signature, or down-weight a noisy rule). Over time the queue gets cleaner without code changes — a continuous-monitoring story that maps to NIST SI-4.

---

## 12. Dashboard

**Minimum views (Plotly / Streamlit):**
- **Ephemeral inventory** — current + recent assets with classification confidence.
- **TTL distribution** — histogram showing how short-lived the fleet is.
- **Burst timeline** — events per minute, with incidents overlaid so spikes are visually obvious.
- **Top risky resources / identities** — sorted by calibrated risk.
- **Incident queue** — drill-down to evidence, graph subgraph, MITRE, guardrails, forensic snapshot.

**The headline demo moment:** show the **before/after alert count** ("312 raw alerts → 14 incidents, 96% reduction") next to the burst timeline. This before/after framing makes "near real-time" land as a felt difference, not just a metric on a slide.

**Optional wow-factor feature:** a "replay" view that animates the Case 1 scenario (20 spot VMs, 3am, gone in 90 minutes) on a timeline, with a marker showing the moment your system would fire versus a second marker showing when a quarterly/daily scan would have caught it.

---

## 13. Evaluation Methodology

### 13.1 Success criteria (operationalized against your own ground truth)

| Metric | Target | How to actually compute it |
|---|---|---|
| Ephemeral asset visibility | ≥95% identified | Recall of the ephemeral/persistent classifier against ground-truth: correctly-classified-ephemeral ÷ true-ephemeral-count |
| Detection latency | Near real-time | Replay events with real timestamps; time from ingestion to incident appearing in dashboard; report a concrete number |
| Noise reduction | ≥40% alert reduction | (raw rule-flagged event count − final incident count) ÷ raw rule-flagged event count |
| Incident correlation accuracy | High-confidence clusters | Graph precision/recall against injected `campaign_id` ground truth |
| Risk scoring quality | Aligns with analyst judgment | Precision/recall@K against injected severity labels; prioritize recall on CRITICAL/HIGH |
| Analyst readiness | Single-incident narratives | Binary: 100% of incidents have non-empty narrative + qualitative pass (reads like analyst action item) |

### 13.2 The ablation table (most persuasive single artifact)

| Configuration | Precision | Recall | Alert reduction |
|---|---|---|---|
| Rules only | … | … | … |
| Rules + two-stage model + suppression | … | … | … |
| Full pipeline (+ graph + fusion + LLM) | … | … | … |

This proves each differentiator earns its place rather than being decoration.

### 13.3 Operational metrics most teams forget

- **Time-to-detection vs resource lifetime** — did the alert fire before the asset vanished?
- **Alert-fatigue curve** — raw → suppressed → correlated incidents.
- **Calibration plot** — predicted risk vs observed malicious rate.

### 13.4 Baseline self-eval snippet (extend, don't just print once)

```python
from sklearn.metrics import precision_score, recall_score, f1_score
y_true = labels['is_risky'].astype(int)
y_pred = labels['predicted_risky'].astype(int)
print(f"Precision: {precision_score(y_true, y_pred):.2%}")
print(f"Recall:    {recall_score(y_true, y_pred):.2%}")
print(f"F1 Score:  {f1_score(y_true, y_pred):.2f}")
raw = int((labels['predicted_risky'] == 1).sum())
inc = labels.loc[labels['predicted_risky'] == 1, 'incident_id'].nunique()
print(f"Alert reduction: {raw} -> {inc} ({(1 - inc/raw)*100:.0f}% reduction)")
# Targets: Precision > 75%, Recall > 70%, Alert reduction >= 40%
```

---

## 14. Worked Sample Incidents (Writeup Deliverable)

### Incident A — Crypto-mining burst (T1496)

**Evidence:** 20× RunInstances by `ci-runner-sa` in 3 min at 03:14 UTC; principal off-hours for cohort `ci_runner`; instances untagged; no matching pipeline trigger.  
**Disambiguation:** Burst rate equals HPA autoscale, but off-hours + missing traffic metric + tag gaps point to hijack.  
**MITRE:** T1496 Resource Hijacking, T1578 Modify Cloud Compute Infrastructure.  
**Guardrails:** SCP spot-fleet quota per SA; deny untagged RunInstances; off-hours alert for CI cohort.

### Incident B — Exposed debug pod (T1190)

**Evidence:** Bare pod (no controller owner) with NodePort to 0.0.0.0/0 and privileged security context; 11-minute lifetime; namespace `dev`.  
**Disambiguation:** Public exposure is normal for a load balancer but anomalous for a controllerless privileged debug pod.  
**MITRE:** T1190 Exploit Public-Facing Application.  
**Guardrails:** Deny NodePort 0.0.0.0/0 via admission policy; block privileged contexts on bare pods; enforce controller ownership.

### Incident C — Compromised session → PII access (graph-only catch)

**Evidence:** Assumed-role session (15-min TTL) reads PII S3 bucket at 03:00; graph links it to a Lambda with anomalous invocation lineage; no scheduled trigger.  
**Disambiguation:** Identical to a scheduled-Lambda pattern except the triggering lineage is novel — caught only by cross-source graph correlation.  
**MITRE:** T1578; data-access exposure relevant to GDPR Art. 32.  
**Guardrails:** Scope session role to least privilege; alert on off-hours PII access; bind sessions to expected trigger lineage.

---

## 15. Compliance & Framework Mapping

| Framework | Control | How the system addresses it |
|---|---|---|
| NIST SP 800-53 | CM-8 (inventory) | Ephemeral classifier + inventory view track transient assets |
| NIST SP 800-53 | SI-4 (monitoring) | Streaming detection + feedback loop = continuous monitoring |
| NIST SP 800-53 | IR-4 (incident handling) | Correlated incidents + structured triage |
| MITRE ATT&CK | T1578, T1496, T1190 | Mapped per incident by the LLM triage agent |
| CIS Kubernetes | pod security, RBAC, netpol | Privileged-pod and exposure signals |
| GDPR | Art. 32 (security of processing) | PII-access incidents flagged with forensic snapshot |

---

## 16. Technology Stack

- **Language/data:** Python, Pandas, NumPy/SciPy.
- **ML:** scikit-learn (Isolation Forest, isotonic/Platt calibration) + PyOD (ECOD) for the Stage-1 ensemble.
- **Graph:** NetworkX.
- **LLM:** any chat-completions API with structured JSON output + schema validation; cached responses; templated fallback.
- **Dashboard:** Streamlit or Plotly Dash (Plotly charts).
- **Storage:** Parquet/SQLite for events and incident records.

### ML-model decision (RESOLVED)

**Decision: an unsupervised ensemble of scikit-learn `IsolationForest` (primary) + PyOD `ECOD` (required second vote).** Grounded in what the enrich stage actually hands the detector — `data/processed/events_enriched.parquet`, ~9,857 rows × ~8 numeric features:

- **Isolation Forest primary.** A ~10k×8 tabular matrix is squarely IF's sweet spot. It is unsupervised, so it preserves the project's held-out-label honesty (labels are joined 1:1 only for eval). It fits in under a second with no hyperparameter search, and keeps the stack on scikit-learn (which also does the §9 calibration).
- **ECOD (PyOD) as a required ensemble vote.** Parameter-free, deterministic, fast on tabular data, also unsupervised. Its per-dimension outlier contributions are interpretable and feed the LLM-triage evidence bundle. Stage-1 score = mean of the two min-max-normalized scores.

**Considered and rejected for the critical path:**
- **TabPFN / TabPFN-2.5** — a pretrained tabular foundation model was floated to avoid burning the Claude Code Pro window on train/tune cycles, but that motivation evaporates: Isolation Forest already has no train/tune cycle to avoid. TabPFN is also fundamentally a *supervised* in-context classifier, so using it would force labels into the model and a train/test split — contradicting the recall-first, no-leakage architecture — and adds a heavy dependency with sample/feature caps.
- **PyTorch / Keras autoencoder** — overkill on data this small (8 features, ~10k rows tends to overfit a net) and reintroduces exactly the training loop IF avoids. ECOD provides the desired "second independent view" without it.

**Fallback only (not in the build):** Claude as a few-shot anomaly scorer — feed an engineered feature row plus 3–4 labeled examples, ask for a score and rationale. No training, no model file, but less rigorous. Documented as a last resort if both detectors were ever unavailable.

---

## 17. Build Plan & Team Split

**Strict dependency chain:** simulator → features + cohorts → two-stage detector → graph + fusion → LLM triage → dashboard + eval.

| Phase | Output | Module | Unblocks |
|---|---|---|---|
| 1. Simulator + data dict | 3 labeled, campaign-linked log streams | `modules/data_simulation/` | everything |
| 2. Features + cohorts | feature matrix, cohort assignments | `modules/ingest_enrich/` | model |
| 3. Two-stage detection | candidate + suppressed events | `modules/detection/` | correlation |
| 4. Graph + risk fusion | scored incidents | `modules/correlation/`, `modules/risk_fusion/` | triage, dashboard |
| 5. LLM triage + forensics | structured incident cards | `modules/llm_triage/` | writeup, dashboard |
| 6. Dashboard + evaluation | demo + ablation table | `modules/dashboard/` | submission |

**Status:** Stage 0 (data_simulation) is complete. Stages 1–6 have scaffolding in place; module READMEs link to their specific responsibilities.

---

## 18. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Simulator makes attacks trivially separable | Enforce benign look-alikes per scenario; review confusability before trusting metrics |
| LLM output breaks the demo | Strict schema + validation + retry; cached responses; templated fallback |
| Over-engineering the model | Isolation Forest first; add autoencoder only if time allows |
| Graph correlation too aggressive (merges unrelated incidents) | Constrain components to identity + namespace + time envelope; tune edge weights |
| Calibration skipped → meaningless scores | Hold out a split; isotonic/Platt calibration as a required step |
| Detector and enrichment stages conflict on ordering | Read §3 critical ordering catch: score AFTER clustering, not before. Non-negotiable. |

---

## 19. Deliverables Checklist

- [ ] **Working prototype** on simulated logs + **data dictionary** (separate artifact listing field types, examples, purpose).
- [ ] **Ephemeral classifier** (distinct from anomaly detector) + detection approach explained in prose/diagram.
- [ ] **Dashboard, 4 named panels:** (1) ephemeral inventory + TTL distribution, (2) burst/creation-spike timeline, (3) top risky resources/identities ranked list, (4) incident list with narratives.
- [ ] **Architecture diagram** with corrected stage order: ingest → enrich → detect → cluster → score → LLM narrative → dashboard.
- [ ] **Documentation with 2–3 sample incidents:** evidence, MITRE mapping, guardrails (design the LLM narrative prompt to produce this directly).
- [ ] **Beyond-winning extras:** ablation table, time-to-detection metric, alert-fatigue curve, calibration plot, forensic snapshots, feedback loop wireframe.

---

## 20. Next Steps

- [x] **Stage-1 model decided** (see §16): unsupervised Isolation Forest + ECOD ensemble. Remaining build sub-tasks: wire the §5 feature matrix into both detectors, set the recall-first threshold, normalize + average the two scores.
- [ ] Finalize cohort-assignment rules (naming convention parsing, action-signature clustering).
- [ ] Build LLM narrative prompt template; test JSON schema validation and retry logic.
- [ ] Design feedback-loop UX on the dashboard (TP/FP buttons, staged rollout of suppression rules).
- [ ] Create an incident-correlation test suite using injected `campaign_id` labels.
- [ ] Schedule cross-team sync on graph-correlation edge-weight tuning and time-envelope thresholds.

---

## The Beyond-Winning Summary (one paragraph for judges)

Most submissions train one anomaly model and cluster by time. Ours treats detection as a context problem: principals are grouped into behavioral cohorts so even brand-new ephemeral identities inherit a baseline instantly; a two-stage detector (recall-first model + cohort-aware suppression) hits both >75% precision and ≥40% noise reduction simultaneously rather than trading them off; a cross-source entity graph surfaces multi-step campaigns that time-window clustering cannot see; and an LLM triage agent reasons over assembled evidence to disambiguate hard cases, assign MITRE techniques, and recommend concrete guardrails — with a forensic snapshot so incidents survive resource disappearance. We prove each differentiator earns its place with an ablation table and measure what operationally matters: time-to-detection before asset vanishment, and analyst noise actually cut.
