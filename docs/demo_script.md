# Demo Video — Shot-by-Shot Script (~3 minutes)

> **Target:** the live deployment at <https://sentinel-rho-sooty.vercel.app/app> (or a local
> `npm run dev` build — identical UI). Record at 1080p, browser full-screen, no devtools.
>
> **Arc:** Hook (0:00–0:20) → Why It's Hard / Confusability (0:20–0:50) → Backend Pipeline (0:50–1:20) → Live Demo (1:20–2:25) → Proof / Metrics (2:25–2:50) → Close (2:50–3:00)
>
> Total target: **3:00**. Each shot lists **[screen]**, **[say]**, **[do]**.
>
> **Speaking tip:** these lines are written to be *said*, not read. Short sentences. Pause at
> the dashes. Don't rush the numbers — say them slowly and let them land.

---

## Shot 1 — Hook: The Problem (0:00–0:20, 20s)

- **[screen]** Title card **"Sentinel"** or Dashboard hero at `/app`. Show the replay panel loading.
- **[say]** "Spot instances. CI job pods. Temporary login sessions. They live for a few minutes, then they're gone — often before any security scan even runs. Attackers know this. They hide inside things that are *supposed* to be temporary. So we built **Sentinel**: it spots risk in cloud and Kubernetes in near real time."
- **[do]** Let the dashboard animate in. Don't click yet.

---

## Shot 2 — Why It's Hard: Confusability (0:20–0:50, 30s)

- **[screen]** Cut to the **confusability figure** (`docs/figures/confusability.png`) — show it as a full-screen image or embed in a slide.
- **[say]** "Here's what makes this hard. Look at these two bursts of activity. Same API calls. Same speed. Same volume. One is your autoscaler doing its job. The other is a crypto-miner running on *your* bill. At the event level, they're identical. So any tool that looks only at events will fail on the cases that matter most. The real clue isn't in the event — it's in the **context**. Who is this identity? Is it tagged? Is it running at 3 AM? That's what we look at."
- **[do]** Point to the left panel (overlapping burst_rate distributions → indistinguishable), then the right panel (tag_completeness 0.00 vs 0.54, off_hours 0.83 vs 0.08, spot 0.50 vs 0.00 → separable).

---

## Shot 3 — Backend Pipeline: Seven Stages in 30s (0:50–1:20, 30s)

- **[screen]** Show the **architecture diagram** (`docs/figures/architecture.png`) — pipeline flow: `Data Simulation → Ingest + Enrich → Detect → Cluster → Score → LLM Triage → Dashboard`.
- **[say]** "The pipeline has seven stages. First, we generate nine thousand labeled events across three log sources — cloud, Kubernetes, and login sessions — using real schemas. Next, we clean them up and sort every identity into a **behavioral group** — CI runners, autoscalers, human developers. So even a brand-new pod gets a baseline right away. Then detection runs in two passes. Hard rules always fire first. After that, an anomaly model flags anything unusual, and a second pass removes what's normal *for that group*. Next comes the **graph stage** — we link related events across all three sources into one picture. Then we score the risk, but only *after* grouping, never before — and we calibrate those scores. The riskiest incidents go to an LLM for triage. And finally, everything lands on the dashboard you're looking at."
- **[do]** Trace the architecture flow left to right / top to bottom as you name each stage.

> **Tip:** This is the densest segment — practice pacing. Aim ~4-5 seconds per stage. Pause
> between each "First / Next / Then" so it doesn't blur together.

---

## Shot 4 — Live Demo: Replay Simulation (1:20–1:50, 30s)

- **[screen]** Navigate to **Dashboard** (`/app`) — point at the **Replay Panel** (hero card, autoplays on mount).
- **[say]** "This is the part we're most proud of — the live replay. Five days of activity, played back on a fast clock. Watch the incidents appear in real time. The pipeline catches this one **the moment it forms** —" *(pause as the before/after annotation appears)* "— but a normal daily scan wouldn't check for almost **eighteen hours**. By then, the resource is long gone."
- **[do]** Let the replay reach the demo-window incident (INC-0230, densest CRITICAL). Point at the "Traditional scan misses this for 17.9h" annotation. If it already completed, click **restart**.

---

## Shot 5 — Live Demo: Ranked Findings + Triage Drawer (1:50–2:20, 30s)

- **[screen]** Navigate to **Risk Findings** (`/app/findings`). Click the top CRITICAL finding to open the triage drawer.
- **[say]** "Instead of nine thousand raw events, the analyst sees a ranked list of **529 incidents**. Let's open the top one. Every incident comes with a full triage from the LLM. What the attacker is likely doing. How confident we are. The MITRE techniques. The exact evidence. And the key part — why this is the *attack*, and not the harmless version that looks just like it. It's all structured and cached, so it's instant and works offline. And this snapshot saves the resource's state at the moment we caught it — because by the time you investigate, the pod or session is already gone."
- **[do]** Scroll the drawer: intent → confidence bar → MITRE chips → evidence → disambiguation → forensic snapshot → guardrails → member events.

---

## Shot 6 — Noise Reduction: Alert Funnel (2:20–2:30, 10s)

- **[screen]** Navigate back to **Dashboard** (`/app`) → point at the **Alert-Fatigue Funnel**.
- **[say]** "Nine thousand eight hundred raw events. We flag three thousand. Then we group those into five hundred twenty-nine incidents. That's an **eighty-nine percent cut**. Forty autoscaler alerts become one. The team looks at five hundred things, not ten thousand."
- **[do]** Trace the funnel top to bottom quickly.

---

## Shot 7 — Proof: Analytics & Ablation (2:30–2:50, 20s)

- **[screen]** Navigate to **Analytics** (`/app/analytics`) — show the ablation table/chart and the Risk Calibration panel.
- **[say]** "And we measured all of this — we didn't just eyeball it. On nine thousand labeled events: **100% recall** and **96% precision** at the top of the list. That beats every target we were given. This table shows each part pulling its weight. Hard rules alone catch 72 percent. Add the anomaly model, and it climbs to 84. The graph stage pushes it to 100, while cutting 89 percent of the alerts. And the scores are honest — when we say zero point eight, it really is about 80 percent likely to be an attack. Best of all, anyone can reproduce this. It runs fully offline."
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
