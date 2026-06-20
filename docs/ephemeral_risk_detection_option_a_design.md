# Ephemeral Cloud & Kubernetes Risk Detection — Option A (Beyond-Winning Design)

**Track:** Cloud Security Governance & Risk
**Approach:** ML-Driven Detection + LLM Triage (Advanced), extended with cohort baselining, two-stage suppression, graph correlation, and structured LLM triage.
**Document purpose:** Single source of truth for problem analysis, architecture, data flow, build plan, and evaluation.

---

## 1. Executive Summary

Ephemeral cloud and Kubernetes resources — CI/CD job pods, spot instances, assumed-role sessions, autoscaled containers — live for minutes and then disappear. Traditional security controls (quarterly scans, daily inventory syncs) run too slowly to see them, and the high-volume noise from legitimate autoscaling and CI/CD buries the rare malicious event.

This design builds a **near-real-time detection pipeline** that discovers ephemeral assets, classifies them, scores risk, correlates related events into incidents, and produces analyst-ready narratives with MITRE mapping and remediation.

**The central thesis that drives every design decision:** at the *event* level, a legitimate autoscaler burst and a crypto-mining hijack are statistically identical — same API calls, same burst rate. The signal that separates them is not in the event; it is in the **context** — the identity's behavioral cohort, the novelty of the pattern, the resource's exposure, and how events relate to each other across cloud, K8s, and IAM logs. A system that detects on events alone fails on exactly the ambiguous cases this challenge is built around. A system that detects on *context* solves them.

---

## 2. Problem Analysis

### 2.1 Why ephemeral resources break traditional security

| Traditional assumption | Ephemeral reality |
|---|---|
| Assets are stable; inventory can be synced daily | Assets exist for minutes; a daily sync never sees them |
| Each alert maps to a durable resource to investigate | The resource is gone before triage; no forensic evidence remains |
| Identities are long-lived and can be baselined | Sessions have 15-minute TTLs; no stable identity to baseline against |
| Alert volume is manageable | Autoscaling and CI/CD generate thousands of near-identical events |

### 2.2 The four canonical incidents (and what each demands of the system)

1. **Crypto-mining via compromised CI/CD account** — 20 spot VMs at 3 AM, terminated before the SOC shift. *Demands:* off-hours + novelty + cohort-deviation detection, and detection latency shorter than the resource lifetime.
2. **Debug pod with NodePort exposed to 0.0.0.0/0** — ran 11 minutes, exploited by an external scanner. *Demands:* exposure scoring that distinguishes a load balancer (public IP normal) from a debug pod (public IP dangerous).
3. **Assumed-role session reads PII from S3** — session expired in 15 minutes, never correlated to the compromised Lambda that triggered it. *Demands:* cross-source graph correlation linking Lambda → session → S3 access.
4. **Autoscaler burst of 40 pods** — 40 false-positive alerts buried a real credential-abuse alert. *Demands:* correlation that collapses 40 alerts into 1 incident, plus suppression of cohort-normal bursts.

### 2.3 The ambiguity problem (the heart of the challenge)

Every hard case is a pair of look-alikes the system must separate:

- 40 pods in 2 minutes → **HPA autoscale** or **resource hijacking**?
- Spot VM with public IP and no tags → **misconfigured CI job** or **attacker staging**?
- Assumed-role session hits S3 at 3 AM → **scheduled Lambda** or **compromised credential**?
- Privileged debug pod runs 5 minutes → **developer troubleshooting** or **container escape**?

If your simulated malicious events are trivially separable from benign ones, your metrics look great but prove nothing. **The quality of the entire solution is gated by how confusable the simulator makes these pairs.**

---

## 3. Solution Thesis: Context Beats Events

The naive Option A — one anomaly model over all events, clustered by time window — fails predictably:

- The model either flags every burst (precision collapses) or learns to ignore bursts (recall collapses on the real attack).
- Time-window clustering groups co-occurring events but cannot link a Lambda to the S3 access its stolen session performed minutes later.

The beyond-winning solution replaces event-level detection with **context-aware detection** built on four pillars:

1. **Behavioral cohorts** replace per-identity baselines.
2. **Two-stage detection** separates recall (model) from precision (context suppression).
3. **Graph correlation** surfaces campaigns spanning all three log sources.
4. **LLM triage** reasons over assembled evidence and disambiguates the hard cases.

---

## 4. Architecture & Data Flow

```
[Cloud audit] [K8s events] [Identity/session]
        \          |          /
         v          v         v
  (1) Ingest + cohort enrich   -> normalize to unified schema; assign behavioral cohort;
                                  compute novelty + exposure features
                 |
                 v
  (2) Stage 1: anomaly model    -> Isolation Forest / autoencoder, recall-first
                 |
                 v
  (3) Stage 2: context filter   -> suppress events that are normal for their cohort
                 |
                 v
  (4) Graph correlation         -> entity graph (principal->session->resource->ns->action),
                                  incidents = connected components
                 |
                 v
  (5) Risk fusion + calibration -> combine anomaly score, signals, exposure, novelty,
                                  privilege into a calibrated 0-1 risk score
                 |
                 v
  (6) LLM triage agent          -> structured JSON: intent, confidence, MITRE, guardrails;
                                  forensic snapshot captured at detection time
                 |
                 v
  (7) Dashboard + forensics     -> inventory, TTL distribution, burst timeline, incident
                                  queue with drill-down; analyst feedback loop -> Stage 2
```

### Stage-by-stage

**(1) Ingest + cohort enrich.** Read three sources into one normalized event schema. Compute per-event features and assign each principal to a behavioral cohort. This is the differentiator: a freshly created ephemeral pod inherits its cohort's baseline immediately, solving the "no stable identity" problem.

**(2) Stage 1 — anomaly model.** Train an Isolation Forest (primary; fast, interpretable) and/or an autoencoder (secondary; richer) on the feature matrix of normal CI/CD and autoscale patterns. Tune the threshold for **high recall** — it is acceptable (expected) that this stage over-flags.

**(3) Stage 2 — context filter.** For each Stage-1 candidate, check whether it is normal *for its cohort* (e.g., an HPA scaling event with a matching traffic metric, a CI job from a recognized service account with complete tags). Suppress cohort-normal events. This stage is where precision is won without sacrificing the recall from Stage 1.

**(4) Graph correlation.** Build a NetworkX multigraph of entities and relationships across all three sources. Incidents are connected components (or dense subgraphs) within an identity + namespace + time envelope. This is what turns 40 alerts into 1 incident and what links the Lambda → session → S3 chain.

**(5) Risk fusion + calibration.** Fuse anomaly score, rule/signal matches, exposure window, privilege level, and novelty into a single risk score, then calibrate (isotonic or Platt) so a 0.8 means roughly 80% likely-malicious. Calibrated scores are interpretable and rank the incident queue meaningfully.

**(6) LLM triage agent.** Pass the assembled incident evidence to an LLM that returns **validated structured JSON** — likely intent, confidence, MITRE technique(s), and the specific guardrail. It also disambiguates the hard cases by weighing enriched features. A forensic snapshot of the resource state is captured at detection time so the incident survives the resource's disappearance.

**(7) Dashboard + forensics + feedback.** Interactive dashboard (ephemeral inventory, TTL histogram, burst timeline, incident queue with drill-down). Analyst TP/FP decisions feed back to Stage 2 suppression, closing the loop.

---

## 5. Data Simulation Design

The simulator is the foundation; every downstream metric depends on it. For Option A it must be **richer than a basic generator** in three ways.

### 5.1 Volume and source mix

| Source | Records | Key fields |
|---|---|---|
| Cloud audit logs | 800–1,000 | timestamp, principal, action (RunInstances/AssumeRole/CreateBucket…), resource_id, tags, public_ip, region |
| Kubernetes events | 800–1,000 | timestamp, namespace, pod, action (create/delete/expose), labels, controller_owner, security_context, service_type |
| Identity/session logs | 300–500 | timestamp, principal, session_id, role, ttl, source_ip, federation/idp |

### 5.2 Required label columns (the part most teams skip)

Every event row must carry:

- `is_risky` (0/1) — ground truth for precision/recall.
- `scenario_type` — e.g. `crypto_burst`, `public_exposure`, `identity_anomaly`, `legit_autoscale`, `legit_cicd`, `routine`.
- `cohort` — ground-truth behavioral cohort (`ci_runner`, `hpa_autoscaler`, `human_dev`, `scheduled_lambda`).
- `campaign_id` — **shared across all events of the same attack, across all three sources.** This is what lets you score graph correlation. Without it, correlation accuracy is unmeasurable.

### 5.3 Anomaly mix (target distribution)

| Class | Share | Role |
|---|---|---|
| Resource hijacking (crypto bursts) | 5–8% | true positives to catch |
| Public exposure of ephemeral compute | 3–5% | true positives to catch |
| Unexpected identity/session activity | 5–8% | true positives to catch |
| Legitimate autoscaling / CI/CD bursts | 40–50% | **noise to suppress** |
| Routine ephemeral lifecycle | 30–40% | normal background |

### 5.4 The confusability requirement

For each malicious scenario, generate a **benign look-alike** that shares surface features:

- Crypto burst ↔ HPA autoscale: same RunInstances/pod-create rate; differ only in time-of-day, principal novelty, tag completeness, and absence of a matching traffic metric.
- Attacker staging VM ↔ misconfigured CI VM: both untagged with a public IP; differ in cohort and session lineage.
- Compromised session ↔ scheduled Lambda: both assumed-role S3 access at 3 AM; differ in whether a known scheduler triggered the session (graph lineage).

Generate with a fixed random seed for reproducibility. Keep a held-out split if you train the autoencoder.

---

## 6. Feature Engineering

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

## 7. Behavioral Cohorts (Differentiator #1)

Per-identity baselines are impossible for ephemeral identities. Instead:

1. **Build cohorts** by clustering principals on their action signatures (e.g., k-means/DBSCAN over action histograms, or rule-assisted assignment using naming conventions + service-account metadata).
2. **Baseline the cohort**, not the individual — normal hours, normal burst sizes, normal exposure, normal tag completeness.
3. **Score new ephemeral identities against their cohort** instantly on first appearance.

This converts the brief's stated blocker ("no stable identity to baseline") into the solution's strongest signal.

---

## 8. Two-Stage Detection (Differentiator #2)

**Stage 1 (recall-first).** Isolation Forest over the feature matrix, threshold tuned so true attacks are almost never missed; expect many candidates. Optionally ensemble with an autoencoder reconstruction-error score.

**Stage 2 (precision via context suppression).** Drop candidates that are normal for their cohort:
- HPA scaling event with a corresponding traffic/CPU metric → suppress.
- CI job from a recognized service account with complete tags and in-cohort hours → suppress.
- Otherwise → promote to correlation.

The split is what lets the system hit **precision > 75% and alert reduction ≥ 40% simultaneously**, rather than trading one for the other.

---

## 9. Graph Correlation (Differentiator #3)

Build a NetworkX multigraph:

- **Nodes:** principals, sessions, resources, namespaces, actions.
- **Edges:** "assumed", "created", "accessed", "exposed", "owns", weighted by time proximity and shared identity.
- **Incidents:** connected components (or dense subgraphs) constrained to an identity + namespace + time envelope.

Outcomes this unlocks:
- 40 autoscaler alerts → 1 connected component → 1 incident (noise reduction made literal).
- Lambda → assumed-role session → S3 access becomes a single traced subgraph (Case 3), which time-window clustering alone cannot recover.

Score graph correlation against `campaign_id` ground truth (homogeneity / completeness or pairwise precision-recall on co-membership).

---

## 10. Risk Fusion & Calibration

Fuse component signals into one score:

```
raw_risk = w1*anomaly_score
         + w2*signal_matches
         + w3*exposure_window_norm
         + w4*privilege_level
         + w5*novelty
```

Then **calibrate** (`sklearn` isotonic or Platt scaling against held-out labels) so the final 0–1 score behaves like a probability. Aggregate event scores into an incident score (max + mean blend, or a learned aggregator). Calibrated scores rank the analyst queue truthfully and make the dashboard's "risk = 0.82" meaningful rather than arbitrary.

---

## 11. LLM Triage Agent (Differentiator #4)

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

Operational discipline for the demo:
- **Strict JSON schema** with validation and a retry; reject and re-prompt on malformed output.
- **Cache responses** so the live demo never depends on a network call mid-presentation.
- **Templated fallback narrative** if the API is unavailable — the pipeline still produces a usable card.

### Forensic snapshot
At detection time, serialize the resource's observed state (config, tags, exposure, session lineage) into the incident record so investigation is possible **after the resource is gone** — directly answering "post-incident forensics are impossible."

---

## 12. Feedback Loop

Analyst TP/FP decisions on the dashboard update Stage-2 suppression (e.g., add a confirmed-benign cohort signature, or down-weight a noisy rule). Over time the queue gets cleaner without code changes — a continuous-monitoring story that maps to NIST SI-4.

---

## 13. Dashboard

Minimum views (Plotly / Streamlit):
- **Ephemeral inventory** — current + recent assets with classification confidence.
- **TTL distribution** — histogram showing how short-lived the fleet is.
- **Burst timeline** — events per minute, with incidents overlaid so spikes are visually obvious.
- **Top risky resources / identities** — sorted by calibrated risk.
- **Incident queue** — drill-down to evidence, graph subgraph, MITRE, guardrails, forensic snapshot.

The headline demo moment: show the **before/after alert count** ("312 raw alerts → 14 incidents, 96% reduction") next to the burst timeline.

---

## 14. Evaluation Methodology

### 14.1 Success-criteria mapping

| Criterion | Target | How this design meets it |
|---|---|---|
| Ephemeral asset visibility | 95%+ identified | AI ephemeral classifier over TTL/labels/owner/cohort |
| Detection latency | Near real-time | Streaming scoring on a rolling window |
| Noise reduction | ≥40% | Stage-2 suppression + graph correlation |
| Incident correlation accuracy | High-confidence clusters | Graph components scored vs `campaign_id` |
| Risk scoring quality | Aligns with analyst judgment | Calibrated fused score |
| Analyst readiness | Single-incident narratives | Structured LLM triage + forensic snapshot |

### 14.2 The ablation table (most persuasive single artifact)

| Configuration | Precision | Recall | Alert reduction |
|---|---|---|---|
| Model only | … | … | … |
| Model + cohort suppression | … | … | … |
| Full pipeline (+ graph + fusion) | … | … | … |

This proves each differentiator earns its place rather than being decoration.

### 14.3 Operational metrics most teams forget

- **Time-to-detection vs resource lifetime** — did the alert fire before the asset vanished?
- **Alert-fatigue curve** — raw → suppressed → correlated incidents.
- **Calibration plot** — predicted risk vs observed malicious rate.

### 14.4 Baseline self-eval snippet (extend, don't just print once)

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

## 15. Worked Sample Incidents (for the writeup deliverable)

### Incident A — Crypto-mining burst (T1496)
**Evidence:** 20× RunInstances by `ci-runner-sa` in 3 min at 03:14 UTC; principal off-hours for cohort `ci_runner`; instances untagged; no matching pipeline trigger.
**Disambiguation:** burst rate equals HPA autoscale, but off-hours + missing traffic metric + tag gaps point to hijack.
**MITRE:** T1496 Resource Hijacking, T1578 Modify Cloud Compute Infrastructure.
**Guardrails:** SCP spot-fleet quota per SA; deny untagged RunInstances; off-hours alert for CI cohort.

### Incident B — Exposed debug pod (T1190)
**Evidence:** bare pod (no controller owner) with NodePort to 0.0.0.0/0 and privileged security context; 11-minute lifetime; namespace `dev`.
**Disambiguation:** public exposure is normal for a load balancer but anomalous for a controllerless privileged debug pod.
**MITRE:** T1190 Exploit Public-Facing Application.
**Guardrails:** deny NodePort 0.0.0.0/0 via admission policy; block privileged contexts on bare pods; enforce controller ownership.

### Incident C — Compromised session → PII access (graph-only catch)
**Evidence:** assumed-role session (15-min TTL) reads PII S3 bucket at 03:00; graph links it to a Lambda with anomalous invocation lineage; no scheduled trigger.
**Disambiguation:** identical to a scheduled-Lambda pattern except the triggering lineage is novel — caught only by cross-source graph correlation.
**MITRE:** T1578; data-access exposure relevant to GDPR Art. 32.
**Guardrails:** scope session role to least privilege; alert on off-hours PII access; bind sessions to expected trigger lineage.

---

## 16. Compliance & Framework Mapping

| Framework | Control | How the system addresses it |
|---|---|---|
| NIST SP 800-53 | CM-8 (inventory) | Ephemeral classifier + inventory view track transient assets |
| NIST SP 800-53 | SI-4 (monitoring) | Streaming detection + feedback loop = continuous monitoring |
| NIST SP 800-53 | IR-4 (incident handling) | Correlated incidents + structured triage |
| MITRE ATT&CK | T1578, T1496, T1190 | Mapped per incident by the LLM triage agent |
| CIS Kubernetes | pod security, RBAC, netpol | Privileged-pod and exposure signals |
| GDPR | Art. 32 (security of processing) | PII-access incidents flagged with forensic snapshot |

---

## 17. Technology Stack

- **Language/data:** Python, Pandas, NumPy/SciPy.
- **ML:** scikit-learn (Isolation Forest, calibration), optional autoencoder (PyTorch/Keras) for the secondary signal.
- **Graph:** NetworkX.
- **LLM:** any chat-completions API with structured/JSON output + schema validation; cached responses; templated fallback.
- **Dashboard:** Streamlit or Plotly Dash (Plotly charts).
- **Storage:** Parquet/SQLite for events and incident records.

---

## 18. Build Plan & Team Split

**Strict dependency chain:** simulator → features + cohorts → two-stage detector → graph + fusion → LLM triage → dashboard + eval.

| Phase | Output | Unblocks |
|---|---|---|
| 1. Simulator + data dictionary | 3 labeled, campaign-linked log streams | everything |
| 2. Features + cohorts | feature matrix, cohort assignments | model |
| 3. Two-stage detection | candidate + suppressed events | correlation |
| 4. Graph + risk fusion | scored incidents | triage, dashboard |
| 5. LLM triage + forensics | structured incident cards | writeup, dashboard |
| 6. Dashboard + evaluation | demo + ablation table | submission |

**Suggested split (3 people):**
- **A:** simulator + features + data dictionary (must ship a rough v1 on day one).
- **B:** ML core (two-stage detection) + graph + fusion + calibration.
- **C:** LLM triage + dashboard + writeup/MITRE mapping (mock incident JSON early, integrate late).

---

## 19. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Simulator makes attacks trivially separable | Enforce benign look-alikes per scenario; review confusability before trusting metrics |
| LLM output breaks the demo | Strict schema + validation + retry; cached responses; templated fallback |
| Over-engineering the model | Isolation Forest first; add autoencoder only if time allows |
| Graph correlation too aggressive (merges unrelated incidents) | Constrain components to identity + namespace + time envelope; tune edge weights |
| Calibration skipped → meaningless scores | Hold out a split; isotonic/Platt calibration as a required step |

---

## 20. Deliverables Checklist

- [ ] Working prototype on simulated logs + **data dictionary**.
- [ ] Ephemeral classifier + ML/LLM approach explained.
- [ ] Dashboard: inventory, TTL distribution, burst timeline, top-risk resources/identities, incident list with narratives.
- [ ] Architecture diagram (ingest → enrich → detect → cluster → score → LLM narrative → dashboard).
- [ ] Documentation with 2–3 sample incidents: evidence, MITRE mapping, guardrails.
- [ ] **Beyond-winning extras:** ablation table, time-to-detection metric, alert-fatigue curve, calibration plot, forensic snapshots, feedback loop.

---

## 21. The Beyond-Winning Summary (one paragraph for judges)

Most submissions train one anomaly model and cluster by time. Ours treats detection as a context problem: principals are grouped into behavioral cohorts so even brand-new ephemeral identities inherit a baseline; a two-stage detector separates recall (model) from precision (cohort-aware suppression) to hit both targets at once; a cross-source entity graph surfaces multi-step campaigns that time-window clustering cannot see; and an LLM triage agent reasons over the assembled evidence to disambiguate the hard cases, assign MITRE techniques, and recommend concrete guardrails — with a forensic snapshot so the incident survives the resource's disappearance. We prove each layer earns its place with an ablation table, and we measure what actually matters operationally: did we detect before the asset vanished, and by how much did we cut analyst noise.
