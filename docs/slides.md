# Sentinel — Presentation Deck

> 14 slides, one idea per slide. Figures live in `docs/figures/` (regenerate with
> `python -m modules.dashboard.figures.build_all`). Build the Société Générale-styled PowerPoint with
> `python docs/build_pptx.py` → `docs/slides.pptx`. Each `---` is a slide break; speaker notes (in
> *italics* as `*Speaker note: ...*`) are placed in the PPTX notes pane.

---

## Slide 1 — Title

# Sentinel

### Ephemeral Cloud & Kubernetes Resource Risk Detection — catching risk in resources that live for minutes and vanish before a scan sees them

**Track:** Cloud Security Governance & Risk
**Live demo:** sentinel-rho-sooty.vercel.app/app
**Repo:** github.com/pavannaik2004/Sentinel

*Speaker note: Sentinel is a near-real-time detection pipeline for the blind spot traditional security has — CI pods, spot instances, assumed-role sessions, gone before the daily scan runs.*

---

## Slide 2 — The blind spot

### Traditional security assumes stable assets. Ephemeral reality breaks every assumption.

| Traditional assumption | Ephemeral reality |
|---|---|
| Inventory synced daily | Assets exist for minutes |
| Alert maps to a durable resource | Resource gone before triage |
| Identities are long-lived, baselineable | Sessions have 15-min TTLs |
| Alert volume is manageable | Autoscaling floods thousands of look-alikes |

*Speaker note: A daily scan literally cannot see a pod that lived 11 minutes at 3 AM.*

---

## Slide 3 — Four real incidents, real money

1. Crypto-mining via a compromised CI account — 20 spot VMs at 3 AM → $14k in 90 min, zero alerts
2. Debug pod with NodePort open to 0.0.0.0/0 — exploited in 11 minutes, then died
3. Assumed-role session reads PII from S3 — expired in 15 min, never linked to its Lambda
4. Autoscaler burst of 40 pods — 40 false alerts buried one real credential-abuse alert

*Speaker note: These four canonical incidents drive every design decision and every metric.*

---

## Slide 4 — Why it's genuinely hard

### Every hard case is a pair of look-alikes:

- 40 pods in 2 minutes → autoscale or hijack?
- Untagged spot VM, public IP → misconfigured CI or attacker staging?
- Assumed-role hits S3 at 3 AM → scheduled Lambda or stolen credential?
- At the event level, the attack and its benign twin are identical.

*Speaker note: If your simulated attacks are trivially separable, your metrics prove nothing. This is the discipline most submissions skip.*

---

## Slide 5 — The thesis, in one figure

![Same burst — which is the attack?](figures/confusability.png)

### Same burst rate (left). Only context separates them (right). Detect on context, not events.

*Speaker note: These are two real populations from our data. Most teams cheat by making attacks bigger or faster — we refuse that shortcut; confusability is enforced at generation time. PAUSE here.*

---

## Slide 6 — Architecture

![Pipeline architecture](figures/architecture.png)

### ingest → enrich → detect → cluster → score → triage → dashboard. We merge all three brief options into one pipeline.

*Speaker note: Note the order — we score AFTER clustering, never before. Three low-scoring events can be one high-risk incident together. Option A (ML+LLM) is the spine, B (statistics) the pre-filter, C (rules) the always-on tripwires.*

---

## Slide 7 — Differentiators 1 & 2: cohorts + two-stage detection

- Behavioral cohorts replace per-identity baselines — a new pod inherits its cohort baseline instantly
- Two-stage detection — recall-first ensemble (IsolationForest + ECOD), then cohort-aware suppression
- Recall climbs 72% → 84% without giving back precision

![Behavioral cohorts — size vs risky fraction](figures/cohort_risk.png)

### The unknown cohort is 100% attack — "fits no baseline" is the signal.

*Speaker note: Ephemeral identities have no history, so we baseline the cohort, not the identity. An identity that fits no cohort is itself the alarm.*

---

## Slide 8 — Differentiator 3: graph correlation

![Cross-source correlation of one incident](figures/graph_incident.png)

### IdP login → AssumeRole → 3× S3 GetObject: one incident across two log sources. Time-windowing can't recover this.

*Speaker note: This chain unfolds over minutes and across CloudTrail + IdP. The entity graph links it; a time-window cluster cannot. Recall 84% → 100%, alerts −89%.*

---

## Slide 9 — Differentiator 4: the LLM triage agent

- Returns validated structured JSON — intent, confidence, MITRE, disambiguation, guardrails
- Strict schema + retry + cached → the demo never needs a network call
- A triage agent that reasons over evidence, not a prose generator — 263 incidents, 100% MITRE coverage

![MITRE ATT&CK techniques attributed by LLM triage](figures/mitre_frequency.png)

### Analyst-ready narratives, not raw alerts.

*Speaker note: The LLM is the last mile — it turns a scored incident into something an analyst can act on in seconds.*

---

## Slide 10 — The proof: ablation

![Ablation — each differentiator earns its place](figures/ablation.png)

### Each differentiator earns its place. Recall → 100%, alerts → −89%.

*Speaker note: This is the single most persuasive artifact — every row adds exactly one differentiator. Event-level precision dips at correlation by design; it is won back by ranking, next slide.*

---

## Slide 11 — The proof: we beat every target

| Success criterion | Target | Sentinel |
|---|---|---|
| Risk-scoring quality — precision@50 | > 75% | 96% ✓ |
| Detection coverage — recall | > 70% | 100% ✓ |
| Noise reduction — alert reduction | ≥ 40% | 89% ✓ |
| Correlation accuracy — V-measure | high-confidence | 0.93 ✓ |
| Risk calibration — predicted ≈ observed | well-calibrated | max err 0.016 ✓ |

![Risk-ranking quality — precision / recall @ K](figures/precision_at_k.png)

### Precision is measured the way a SOC works the queue — top-down. precision@50 = 96%.

*Speaker note: We optimize the ranked queue an analyst works top-down, not a single global threshold. That is the brief's prescribed risk-quality metric.*

---

## Slide 12 — The proof: noise reduction

![Alert-fatigue funnel](figures/alert_funnel.png)

### 9,857 raw events → 529 incidents to investigate. The SOC's actual workload drops 95%.

*Speaker note: 4,638 raw flags collapse to 529 correlated incidents — an 89% alert reduction. This is the alert-fatigue problem solved.*

---

## Slide 13 — Honest evaluation

- "Isn't cohort=unknown just the label you injected?" — No. The score is label-free; confusability is enforced at generation; the only label touch is out-of-fold calibration.
- "Precision is 68%, target was 75%." — That's the conservative high-recall band cut. The brief's metric is precision@K — we hit 96% @50 on the ranked queue.
- "It's all synthetic." — Controlled, not faked. No public dataset has this ground truth; schemas are grounded field-by-field in real AWS / K8s / Okta. Reproducible at seed 1337, offline demo.

*Speaker note: This slide wins trust. Volunteer the hard questions before the judges ask them.*

---

## Slide 14 — Close

# Detect on context, not events.

### Ephemeral resources exist for minutes. Attackers need less. Sentinel catches them in time.

- Live demo: sentinel-rho-sooty.vercel.app/app
- Repo: github.com/pavannaik2004/Sentinel · Video: _add link_
- Measured: recall 72% → 100%, alerts −89%, precision@50 96%, V-measure 0.93

*Speaker note: Close on the demo — let the replay simulation show detection beating the next daily scan by 17.9 hours.*
