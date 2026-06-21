# Sentinel — Presentation Deck

> 14 slides. One idea per slide. Figures live in `docs/figures/` (regenerate with
> `python -m modules.dashboard.figures.build_all`). Convert to PPT/PDF as-is — each `---`
> is a slide break. Speaker notes are in *italics* under each slide; drop them from the
> final deck or keep them in the notes pane.

---

## Slide 1 — Title

# Ephemeral Cloud & Kubernetes Resource Risk Detection

### Detecting risk in resources that live for *minutes* and vanish before a scan sees them

**Track:** Cloud Security Governance & Risk
**Live demo:** sentinel-rho-sooty.vercel.app/app

*Speaker note: We built a near-real-time detection pipeline for the blind spot traditional security has: CI pods, spot instances, assumed-role sessions — gone before the daily scan runs.*

---

## Slide 2 — The blind spot

### Traditional security assumes stable assets. Ephemeral reality breaks every assumption.

| Traditional assumption | Ephemeral reality |
|---|---|
| Inventory synced daily | Assets exist for **minutes** |
| Alert → a durable resource to investigate | Resource **gone before triage** |
| Identities are long-lived, baselineable | Sessions have **15-min TTLs** |
| Alert volume is manageable | Autoscaling floods **thousands** of look-alike events |

*Speaker note: A daily scan literally cannot see a pod that lived 11 minutes at 3 AM.*

---

## Slide 3 — Four real incidents, real money

1. **Crypto-mining** via compromised CI account — 20 spot VMs at 3 AM → **$14k in 90 min, zero alerts**
2. **Debug pod** with NodePort open to `0.0.0.0/0` — exploited in **11 minutes**, then died
3. **Assumed-role session** reads PII from S3 — expired in 15 min, never linked to its Lambda
4. **Autoscaler burst** of 40 pods — **40 false alerts buried one real** credential-abuse alert

*Speaker note: These four canonical incidents drive every design decision and every metric.*

---

## Slide 4 — Why it's genuinely hard

### Every hard case is a pair of look-alikes:

- 40 pods in 2 minutes → **autoscale** or **hijack**?
- Untagged spot VM, public IP → **misconfigured CI** or **attacker staging**?
- Assumed-role hits S3 at 3 AM → **scheduled Lambda** or **stolen credential**?

**At the event level, the attack and the benign twin are identical.**

*Speaker note: If your simulated attacks are trivially separable, your metrics prove nothing.*

---

## Slide 5 — The thesis, in one figure

![Same burst — which is the attack?](figures/confusability.png)

### Same burst rate (left). Only **context** separates them (right). **Detect on context, not events.**

*Speaker note: These are two real populations from our data. Most teams cheat by making attacks bigger/faster — we refuse that shortcut; the confusability is enforced at generation time.*

---

## Slide 6 — Architecture

![Pipeline architecture](figures/architecture.png)

### `ingest → enrich → detect → cluster → score → triage → dashboard`

*Speaker note: Note the order — we score AFTER clustering, never before. Three low-scoring events can be one high-risk incident together.*

---

## Slide 7 — Differentiator 1+2: cohorts & two-stage detection

- **Behavioral cohorts** replace per-identity baselines — a new pod inherits its cohort baseline instantly
- **Two-stage detection** — recall-first ensemble (IsolationForest + ECOD), then cohort-aware suppression

![Behavioral cohorts — size vs risky fraction](figures/cohort_risk.png)

### The `unknown` cohort is **100% attack** — "fits no baseline" *is* the signal

---

## Slide 8 — Differentiator 3: graph correlation

![Cross-source correlation of one incident](figures/graph_incident.png)

### IdP login → AssumeRole → 3× S3 GetObject — **one incident across two log sources.** Time-windowing can't recover this.

*Speaker note: This chain unfolds over minutes and across CloudTrail + IdP. The entity graph links it; a time-window cluster cannot.*

---

## Slide 9 — Differentiator 4: the LLM triage agent

- Returns **validated structured JSON** — intent, confidence, MITRE, disambiguation, guardrails
- Strict schema + retry + cached → the demo never needs a network call
- A **triage agent that reasons over evidence**, not a prose generator

![MITRE ATT&CK techniques attributed by LLM triage](figures/mitre_frequency.png)

---

## Slide 10 — The proof: ablation

![Ablation — each differentiator earns its place](figures/ablation.png)

### Each differentiator earns its place. Recall → **100%**, alerts → **−89%**.

*Speaker note: This is the single most persuasive artifact — every row adds exactly one differentiator.*

---

## Slide 11 — The proof: noise reduction

![Alert-fatigue funnel](figures/alert_funnel.png)

### 9,857 raw events → **529 incidents** to investigate. The SOC's actual workload drops 95%.

---

## Slide 12 — The proof: ranking quality & calibration

![Risk-ranking quality — precision / recall @ K](figures/precision_at_k.png)

### **precision@50 = 96%** — high precision exactly where the analyst starts the queue. Calibration max error **0.016**.

*Speaker note: We optimize the ranked queue an analyst works top-down, not a single threshold.*

---

## Slide 13 — Honest evaluation

**"Isn't `cohort=unknown` just the label you injected?"** — No. The score is label-free; confusability is enforced at generation; the only label touch is out-of-fold calibration.

**"Precision is 68%, target was 75%."** — That's the high-recall band cut. The brief's metric is precision@K — we hit **96% @50**.

**"It's all synthetic."** — Controlled, not faked. No public dataset has this ground truth; schemas are grounded field-by-field in real AWS/K8s/Okta.

---

## Slide 14 — Close

# Detect on context, not events.

- **Live demo:** sentinel-rho-sooty.vercel.app/app
- **Repo:** _add GitHub URL_ · **Video:** _add link_
- Measured: recall 72%→**100%**, alerts **−89%**, precision@50 **96%**, V-measure **0.93**

### Ephemeral resources exist for minutes. Attackers need less. We catch them in time.

*Speaker note: Close on the demo — let the replay simulation show detection beating the next daily scan by 17.9 hours.*
