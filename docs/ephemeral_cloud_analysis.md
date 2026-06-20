# Ephemeral Cloud & Kubernetes Resource Risk Detection — Compiled Analysis

**Track:** Cloud Security Governance & Risk
**Status:** Selected as final hackathon build
**Team:** 2 people, full-stack + ML background, new to graph algorithms and NLP, comfortable using LLM APIs
**Tooling:** Claude Code on a Pro subscription (5-hour rolling usage window + weekly cap, shared with Claude.ai chat — no fixed token count published, budget accordingly)

---

## 1. The problem, in one paragraph

A cloud-native enterprise provisions hundreds of ephemeral resources daily — CI/CD pods, spot instances, temporary IAM sessions, autoscaled containers — that exist for minutes to hours and then vanish. Traditional security controls (quarterly scans, daily inventory syncs) were never built for that tempo. The hardest part of the problem, stated explicitly in the brief: legitimate autoscaler bursts and malicious resource-hijacking bursts can look *structurally identical* in raw event volume and timing. The system has to tell them apart using metadata signals, not speed or size.

---

## 2. Difficulty and business impact assessment

### Why this is rated 4/5 difficulty, not 5/5

- **No real data, and that's a simplification, not a setback.** The brief has you simulate your own telemetry, which removes the hardest part of a real-world version of this problem (messy, contradictory, multi-source ingestion). You control the ground truth.
- **The core ML task is well-trodden.** Isolation Forest / autoencoder-style anomaly detection on engineered features (burst rate, principal novelty, privilege level, exposure flag, TTL) is a standard applied-ML pattern, not novel research.
- **The genuinely hard part is feature engineering**, not algorithm design: building features that separate "HPA autoscale burst" from "crypto-mining burst" when the brief admits these can look identical in raw API patterns.
- **NetworkX-based incident correlation** (grouping related high-score events by time-window + identity + namespace) is the most algorithmically substantial piece, but it's a single well-defined task, not a chain of compounding ambiguous problems.
- **The LLM layer is the "easy" hard part** — narrative generation from already-structured, already-scored data is a much gentler task than extracting structured facts from unstructured documents (the equivalent step in the Vendor Risk problem, which is why that one is rated 5/5).

### Business impact: 4/5

- **Direct, quantifiable financial exposure.** The brief's Case 1 (20 spot VMs spun up for crypto mining at 3am, $14,000 in 90 minutes, zero alerts fired) is a concrete, recurring abuse pattern — money leaving in real time, not a theoretical risk.
- **The core thesis is sharp and demo-able:** "ephemeral resources exist for minutes, attackers need less" directly indicts the standard quarterly/daily scan cadence as structurally unable to catch this class of risk.
- **Alert fatigue is a real, common SOC failure mode.** Case 4 (40 legitimate autoscaler alerts burying one real credential-abuse alert) has direct, easily quantified analyst-hours payback if solved.
- **Forensic blind spot:** "the resource is gone before the alert gets triaged" is a genuine, hard-to-work-around operational gap in most cloud-native orgs.
- **Why not higher:** the compliance angle (NIST CM-8/SI-4, CIS Benchmarks) is real but is operational hygiene rather than a direct legal-liability trigger (contrast with GDPR/SOX in the Vendor Risk problem). The blast radius — cloud bill, exposure window — is real but bounded and reversible, not open-ended like a regulatory breach-notification cascade.

---

## 3. Build strategy: merge A, B, and C — A is the spine, B/C fold in as signals, not separate tiers

Rather than picking one Option and treating the others as a fallback, the strongest version of this build uses **Option A's architecture as the spine**, with Option B and C's logic folded in as inputs rather than bolted on beside it:

- **From B (statistical layer):** Z-score/IQR baselines per namespace/principal run *before* anything touches the ML model, as a cheap pre-filter — this is the layer that does most of the work of separating obvious-normal and obvious-malicious cases, leaving only the ambiguous middle for the model.
- **From C (deterministic rules):** the explicit rule list (public IP on non-LB resource, privileged pod without controller owner, burst >10 in 5 min, off-hours assumed-role activity) becomes **always-on tripwires** that can force a severity floor regardless of what the ML model scores — a hard guardrail the model can't quietly override.
- **The wow-factor feature:** a "replay" view that animates the brief's own Case 1 scenario (20 spot VMs, 3am, gone in 90 minutes) on a timeline, with a marker showing the moment your system would fire versus a second marker showing when a quarterly/daily scan would have caught it. This before/after framing makes "near real-time" land as a felt difference, not just a metric on a slide — and it sits at the dashboard layer, reading off already-computed scores, so it doesn't depend on your riskiest component (the ML scoring) being perfect.

---

## 4. Architecture — corrected for the brief's literal stage order

**Important catch:** the brief specifies the pipeline order as **ingest → enrich → detect → cluster → score → LLM narrative → dashboard**. Read literally, this means lightweight detection (the rule/statistical layer) flags candidate events *first*, clustering groups flagged events into incidents *second*, and scoring happens *at the incident level, after clustering* — not per-event before clustering. This matters: three separately low-scoring events from the same principal in the same 5-minute window can be a high-severity incident together, even if none of them alone would trigger a high score. Scoring after clustering captures that; scoring before clustering does not.

### Pipeline, with backend/ML ownership split

```
Simulated event streams (cloud audit, K8s, IAM)   [shared/backend]
                  |
        ┌─────────┴─────────┐
        ▼                   ▼
Rules + stat baselines   Feature engineering
  (backend)                (ML)
  - hard overrides         - burst rate, novelty,
  - z-scores per ns/principal  TTL, exposure flag
        └─────────┬─────────┘
                  ▼
        Composite risk score (merge point)
        Rule fires → severity floor, regardless of ML score
        Else → blend of z-score deviation + ML anomaly probability
                  ▼
        Incident clustering (ML, NetworkX)
        time-window + identity + namespace correlation
                  ▼
        LLM narrative (ML)
        evidence summary, MITRE mapping, guardrails
                  ▼
        API + dashboard (backend)
```

### Build order — backend lane first, and this is deliberate, not just convenient

1. **Backend lane:** event store (normalize all 3 sources into one schema), rule tripwires, statistical baselines, API layer. This ships a working, demoable V1 before any ML code is touched.
2. **ML lane, built against the already-working event store:** feature engineering, anomaly scoring, NetworkX clustering, LLM narrative.

The reason backend-first matters specifically for this problem: the brief's hardest stated challenge — telling apart a legitimate burst from a malicious one that looks the same — is exactly where the rule/statistical pre-filter earns its keep. If the ML layer sees raw, unfiltered events, it's being asked to solve the noise problem alone. If backend ships first, the ML layer only ever sees the harder, already-narrowed cases, which is both more defensible to judges and a smaller surface for things to go wrong under a time-constrained build.

---

## 5. ML architecture: what to use instead of plain Isolation Forest

- **Sequence-aware transformer options exist** (Anomaly Transformer, TranAD) and are explicitly designed for the "tell apart look-alike bursts" problem — but they require training on your data, and a few hundred to a thousand simulated events is a genuinely risky scale to train a transformer on. At that size, a trained-from-scratch transformer will likely underperform a well-tuned Isolation Forest, regardless of how modern the architecture sounds.
- **Recommended instead: a tabular foundation model (TabPFN / TabPFN-2.5).** Engineer the burst/exposure/privilege features into a table, then run a pretrained tabular foundation model over it for anomaly scoring. TabPFN is pretrained once via in-context learning on millions of synthetic datasets and is never trained on your actual data — feed it the table, get scores back in seconds. This is the single most important practical recommendation given the Claude Code Pro budget constraint: **no training loop, no hyperparameter search, no tune-rerun cycle that burns through the 5-hour usage window.** It's also genuinely current (TabPFN-2.5 shipped November 2025), so it's a defensible "we used 2025-2026-era architecture" claim, not a cosmetic one.
- **Fallback if integration time runs short:** use Claude itself as a few-shot anomaly scorer — feed the engineered feature row plus 3-4 labeled examples, ask for a score and a one-line rationale. No training, no model file, but less rigorous and harder to defend the number under judge questioning. Treat this as a fallback, not the primary plan.

---

## 6. Deliverables checklist

| Deliverable | What it concretely requires | Common failure mode to avoid |
|---|---|---|
| Working prototype + short data dictionary | Running pipeline + a one-page field/type/example/purpose table | Skipping the data dictionary — it's a separate explicit ask |
| Ephemeral classifier + detection approach explained | **Two separate things:** (1) an ephemeral-vs-persistent classifier (TTL, label presence, controller ownership) answering "is this short-lived at all," and (2) the risk-detection approach explained in prose/diagram, answering "is it dangerous." These are orthogonal — a persistent resource can be risky, an ephemeral one can be benign. | Conflating the two into a single model |
| Dashboard, 4 named panels | (1) ephemeral inventory + TTL distribution, (2) burst/creation-spike timeline, (3) top risky resources/identities ranked list, (4) incident list with narratives | Building one impressive panel (e.g. the replay demo) and skipping the other three |
| Architecture diagram | Literally specified stage order: ingest → enrich → detect → cluster → score → LLM narrative → dashboard (see Section 4 for the corrected version) | Scoring before clustering instead of after — see the catch in Section 4 |
| 2–3 sample incidents: evidence, MITRE mapping, guardrails | A written artifact — efficient move: design the LLM narrative prompt to directly output MITRE-mapped, guardrail-recommending text, so this deliverable is just an export of your best dashboard narratives | Treating this as a second writing pass instead of designing the narrative prompt to produce it directly |

---

## 7. Success criteria — operationalized against your own ground truth

| Metric | Target | How to actually compute it |
|---|---|---|
| Ephemeral Asset Visibility | ≥95% identified | Recall of the ephemeral/persistent classifier against the ground-truth label you control: correctly-classified-ephemeral ÷ true-ephemeral-count. Don't conflate with anomaly detection — this is purely inventory completeness. |
| Detection Latency | Near real-time (no fixed number given) | Define and measure your own: replay events with real timestamps, time from ingestion to incident appearing in the dashboard, report a concrete number. Build this measurement into the replay demo itself. |
| Noise Reduction | ≥40% alert reduction | (raw rule-flagged event count − final incident count) ÷ raw rule-flagged event count. Directly operationalizes Case 4: 40 individual pod alerts should collapse into 1 incident. |
| Incident Correlation Accuracy | High-confidence clustered incidents | Requires a `true_incident_id` field injected at data-generation time (e.g., tag the 20 crypto-mining VMs as one synthetic incident when created). Measure cluster precision/recall against that, don't eyeball it. |
| Risk Scoring Quality | Aligns with analyst judgment | Precision/recall@K against your own injected severity labels. Adopt the same "recall on CRITICAL/HIGH matters more than overall precision" principle used explicitly in the Vendor Risk brief — it's the right default for security scoring generally. |
| Analyst Readiness | Single-incident narratives | Binary coverage check (100% of incidents have a non-empty narrative) plus a qualitative pass — does it read like something a SOC analyst would act on. |

---

## 8. Data structure and schema design

The brief gives example event types and loose field hints, not an exact schema — this is the concrete design:

**Cloud audit logs (500–1,000 records):** `event_id`, `timestamp`, `event_type` (RunInstances / AssumeRole / CreateBucket / TerminateInstances / PutBucketPolicy), `principal_id`, `principal_type` (user/role/service), `source_ip`, `region`, `resource_id`, `resource_type`, `tags` (deliberately sparse on a subset of records), `public_ip_assigned`, `spot_instance` flag.

**Kubernetes events (500–1,000 records):** `event_id`, `timestamp`, `event_type` (pod_create / pod_delete / service_expose / rbac_change), `namespace`, `pod_name`, `controller_owner` (Deployment/Job/CronJob/**None** — "None" is the Case 2 debug-pod signal), `labels`, `privileged` flag, `exposed_ports` (with a 0.0.0.0/0 marker), `node`.

**Identity/session logs (200–500 records):** `event_id`, `timestamp`, `session_type` (assumed_role / service_account_token / federated), `principal_id`, `source_idp`, `ttl_seconds`, `source_ip`, `actions_performed`, `resource_accessed`.

### The single hardest design principle

Legitimate autoscale/CI bursts (40–50% of the data) and malicious resource-hijacking bursts (5–8%) must look **structurally similar in volume and timing** — that's what makes the problem hard in the first place, per the brief's own Case 4. They should differ in **metadata completeness and ownership**, not size or speed:
- Legitimate burst → complete tags (`managed-by: autoscaler`), real `controller_owner`, proper labels.
- Malicious burst → sparse/missing tags, `controller_owner: None`, spot instances with no business justification.

Making the malicious bursts bigger or faster than the legitimate ones to make them easy to tell apart accidentally makes the problem easier than intended, and the noise-reduction metric stops meaning anything, because there was never real noise to reduce against.

### Grounding fields required (same philosophy as: build the ground truth first, derive labels from it — don't bolt labels on randomly)

- `true_incident_id` — needed to measure Incident Correlation Accuracy honestly.
- `severity` / `anomaly_type` — needed to measure Risk Scoring Quality honestly.

---

## 9. Open items / next steps

- [ ] Build the synthetic data generator using the ground-truth-first approach (build the real incident structure — which events belong to the same crypto-mining burst, which pod is the Case-2-style debug pod — then derive every CSV and label from that structure, not the other way around).
- [ ] Decide dashboard tech stack (Flask/FastAPI + Plotly vs a frontend framework) based on which person on the team owns the backend lane.
- [ ] Confirm TabPFN integration path (Python package, feature table format) before committing the ML lane's build time to it.
- [ ] Design the LLM narrative prompt once, so it directly satisfies both the dashboard's incident narratives and the "2–3 sample incidents" written deliverable.
- [ ] Revisit the architecture diagram with the corrected detect→cluster→score ordering before finalizing the documentation deliverable.
