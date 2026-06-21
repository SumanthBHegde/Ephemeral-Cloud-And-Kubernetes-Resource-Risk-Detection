# Demo Video — Shot-by-Shot Script (~3 minutes)

> **Target:** the live deployment at <https://sentinel-rho-sooty.vercel.app/app> (or a local
> `npm run dev` build — identical UI). Record at 1080p, browser full-screen, no devtools.
>
> **Arc:** Hook (0:00–0:20) → Why It's Hard / Confusability (0:20–0:50) → Backend Pipeline (0:50–1:20) → Live Demo (1:20–2:25) → Proof / Metrics (2:25–2:50) → Close (2:50–3:00)
>
> Total target: **3:00**. Each shot lists **[screen]**, **[say]**, **[do]**.

---

## Shot 1 — Hook: The Problem (0:00–0:20, 20s)

- **[screen]** Title card **"Sentinel"** or Dashboard hero at `/app`. Show the replay panel loading.
- **[say]** "Spot instances. CI job pods. Assumed-role sessions. They live for minutes and disappear before a security scan ever runs. Attackers know this — they hide inside the noise of things that are *supposed* to be temporary. This is **Sentinel**: near-real-time risk detection for ephemeral cloud and Kubernetes."
- **[do]** Let the dashboard animate in. Don't click yet.

---

## Shot 2 — Why It's Hard: Confusability (0:20–0:50, 30s)

- **[screen]** Cut to the **confusability figure** (`docs/figures/confusability.png`) — show it as a full-screen image or embed in a slide.
- **[say]** "Here's the hard part. Look at these two event bursts — same API calls, same burst rate, same volume. One is your autoscaler doing its job. The other is a crypto-miner running on *your* bill. At the event level they are **statistically identical**. Any tool that detects on events alone fails on exactly the cases that matter. The signal isn't in the event — it's in the **context**: who the identity is, whether it's tagged, whether it runs at 3 AM. So we detect on context."
- **[do]** Point to the left panel (overlapping burst_rate distributions → indistinguishable), then the right panel (tag_completeness 0.00 vs 0.54, off_hours 0.83 vs 0.08, spot 0.50 vs 0.00 → separable).

---

## Shot 3 — Backend Pipeline: Seven Stages in 30s (0:50–1:20, 30s)

- **[screen]** Show the **architecture diagram** (`docs/figures/architecture.png`) — pipeline flow: `Data Simulation → Ingest + Enrich → Detect → Cluster → Score → LLM Triage → Dashboard`.
- **[say]** "Our pipeline has seven stages. Stage Zero simulates 9,857 labeled events across three log sources — CloudTrail, Kubernetes audit, and IdP sessions — grounded in real AWS and K8s schemas. Stage One normalizes all three into a unified schema and assigns each identity to a **behavioral cohort** — CI runners, HPA autoscalers, human devs — so even a brand-new pod inherits a baseline instantly. Stage Two runs two-stage detection: tripwires always fire on hard rules, then a recall-first anomaly ensemble — Isolation Forest plus ECOD — flags candidates, and a cohort-suppression pass cuts the noise. Stage Three runs **graph correlation** via NetworkX — an entity multigraph with time-gated typed edges that links events across all three sources. Stage Four fuses risk scores at the **incident** level after clustering — never before — and calibrates them with isotonic regression. Stage Five sends each CRITICAL and HIGH incident to **gpt-4o-mini** for structured triage: intent, MITRE, guardrails — validated JSON, cached offline. Stage Six is the SOC dashboard you're seeing now."
- **[do]** Trace the architecture flow left to right / top to bottom as you name each stage.

> **Tip:** This is the densest segment — practice pacing. Aim ~4-5 seconds per stage.

---

## Shot 4 — Live Demo: Replay Simulation (1:20–1:50, 30s)

- **[screen]** Navigate to **Dashboard** (`/app`) — point at the **Replay Panel** (hero card, autoplays on mount).
- **[say]** "The pipeline's headline payoff is the live replay. Watch incidents form in real time as five days of telemetry stream through a virtual clock. The pipeline flags this incident **at the moment it forms** —" *(pause as the before/after annotation appears)* "— but the next *daily* scan wouldn't look for almost **eighteen hours**. By then, the resource is long gone."
- **[do]** Let the replay reach the demo-window incident (INC-0230, densest CRITICAL). Point at the "Traditional scan misses this for 17.9h" annotation. If it already completed, click **restart**.

---

## Shot 5 — Live Demo: Ranked Findings + Triage Drawer (1:50–2:20, 30s)

- **[screen]** Navigate to **Risk Findings** (`/app/findings`). Click the top CRITICAL finding to open the triage drawer.
- **[say]** "Instead of nine thousand raw events, the analyst works a ranked queue of **529 incidents**. Open the top one — every incident gets an LLM triage: the likely intent, a confidence score, MITRE techniques, the specific evidence, and — crucially — the **disambiguation**: why this is the attack and not its benign look-alike. Structured JSON from the triage agent, cached, so it's instant and offline. The forensic snapshot captures the resource state at detection time — because by the time you investigate, the pod or session is already gone."
- **[do]** Scroll the drawer: intent → confidence bar → MITRE chips → evidence → disambiguation → forensic snapshot → guardrails → member events.

---

## Shot 6 — Noise Reduction: Alert Funnel (2:20–2:30, 10s)

- **[screen]** Navigate back to **Dashboard** (`/app`) → point at the **Alert-Fatigue Funnel**.
- **[say]** "Nine thousand eight hundred raw events → three thousand flagged → five hundred twenty-nine correlated incidents. That's an **eighty-nine percent cut**. Forty autoscaler alerts collapse into one. The SOC investigates five hundred things, not ten thousand."
- **[do]** Trace the funnel top to bottom quickly.

---

## Shot 7 — Proof: Analytics & Ablation (2:30–2:50, 20s)

- **[screen]** Navigate to **Analytics** (`/app/analytics`) — show the ablation table/chart and the Risk Calibration panel.
- **[say]** "And it's measured, not eyeballed. On 9,857 labeled, reproducible events: **100% recall**, **96% precision on the ranked queue at 50** — beating every target in the brief. This ablation table proves each component earns its place: tripwires alone give 72% recall; add the ensemble and recall climbs to 84%; graph correlation pushes it to 100% while cutting 89% of alerts; risk fusion recovers precision. And the risk scores are calibrated — a 0.8 score really means 80% likely-malicious, predicted vs observed almost dead-on. Everything is **seed-reproducible** and runs fully offline."
- **[do]** Show ablation panel (each row adds one differentiator), then Risk Calibration curve hugging the diagonal.

---

## Shot 8 — Close (2:50–3:00, 10s)

- **[screen]** Return to **Dashboard** (`/app`) or a closing title card with the URL.
- **[say]** "**Sentinel.** Detect on context, not events. Thank you."
- **[do]** Show `https://sentinel-rho-sooty.vercel.app/app` on screen. End.

---

## What Each Shot Covers (Deliverables Checklist)

| Problem Statement Deliverable | Shot |
|---|---|
| Ephemeral asset discovery & classification | Shot 3 (Stage 0 + Stage 1 pipeline description) |
| Behavioral cohort baselines (ephemeral identity problem) | Shot 3 (Stage 1) |
| Two-stage detection (recall-first + suppression) | Shot 3 (Stage 2) |
| Graph correlation (noise reduction, campaign linking) | Shot 3 (Stage 3) + Shot 6 (funnel) |
| Incident-level risk scoring + calibration | Shot 3 (Stage 4) + Shot 7 (analytics) |
| LLM triage: intent, MITRE, guardrails | Shot 5 (triage drawer) |
| SOC dashboard with replay simulation | Shot 4 (replay) + Shot 5 (findings) |
| The confusability thesis (why it's hard) | Shot 2 (figure) |
| Alert-fatigue funnel (89% reduction) | Shot 6 |
| Ablation table (measured, not eyeballed) | Shot 7 |
| 17.9h time-to-detection advantage | Shot 4 |
| Reproducibility (seed 1337, offline, 50 tests) | Shot 7 |
| MITRE ATT&CK mapping | Shot 5 (drawer) |
| Forensic snapshot (resource gone before triage) | Shot 5 (drawer) |

---

## Timing Summary

| Shot | What | Duration |
|---|---|---|
| 1 | Hook — title + thesis | 0:00–0:20 (20s) |
| 2 | Confusability figure — why events alone fail | 0:20–0:50 (30s) |
| 3 | Backend pipeline — 7 stages in 30s | 0:50–1:20 (30s) |
| 4 | Live replay — 17.9h detection advantage | 1:20–1:50 (30s) |
| 5 | Ranked findings + triage drawer + forensic block | 1:50–2:20 (30s) |
| 6 | Alert-fatigue funnel — 89% reduction | 2:20–2:30 (10s) |
| 7 | Analytics: ablation + calibration proof | 2:30–2:50 (20s) |
| 8 | Close | 2:50–3:00 (10s) |
| **Total** | | **3:00** |

---

## Recording Checklist

- [ ] Browser full-screen, 1080p, one consistent theme (light or dark throughout).
- [ ] Pre-load `/app` once so data is cached and the replay autoplays smoothly on the real take.
- [ ] Have the `docs/figures/confusability.png` ready as a full-screen slide for Shot 2.
- [ ] Have `docs/figures/architecture.png` ready as a slide or overlay for Shot 3.
- [ ] Know your demo-window incident in Risk Findings (densest CRITICAL — INC-0230, 46 events).
- [ ] Mic check — narration is the spine; UI is supporting evidence.
- [ ] Keep total under 3:20 even with natural pauses (most judges stop watching at 3:30).
- [ ] Add captions — judges often watch muted.
- [ ] Optional B-roll: trigger the **Guided tour** (`?` button in the topbar) for 10s after Shot 8 to show the interactive tour exists, then cut. This is optional; never gamble on a live network.
- [ ] End description with: `Live demo: https://sentinel-rho-sooty.vercel.app/app · Repo: <GitHub URL>`

---

## Key Numbers to Have Ready (Don't Stumble)

| Metric | Value |
|---|---|
| Total events | 9,857 |
| Log sources | 3 (CloudTrail, K8s audit, IdP/session) |
| Raw flags | 4,638 |
| Correlated incidents | 529 |
| Alert reduction | **89%** |
| CRITICAL + HIGH triaged | 263 |
| Recall | **100%** |
| Precision @50 | **96%** |
| Detection advantage | **17.9 hours** before traditional daily scan |
| Calibration error | < 0.016 across all bins |
| INC-A collapse | 40 alerts → 1 incident |
| Test suite | 50 tests, all green |
| Fixed seed | 1337 (fully reproducible) |
