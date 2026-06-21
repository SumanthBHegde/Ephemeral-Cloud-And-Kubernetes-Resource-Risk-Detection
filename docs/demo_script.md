# Demo Video — Shot-by-Shot Script (~3 minutes)

> **Target:** the live deployment at <https://sentinel-rho-sooty.vercel.app/app> (or a local
> `npm run dev` build — identical UI). Record at 1080p, browser full-screen, no devtools.
>
> **Relationship to the in-app guided tour:** the dashboard ships a driver.js *Guided tour*
> (the "Guided tour" button in the top bar) that walks a live judge through the UI. This
> script is the *recording* path — it directs your narration and clicks for the video. They
> are complementary: the tour is for hands-on judges, the video is for async viewing. Don't
> read the tour aloud; follow the shots below.
>
> Total target: **3:00**. Each shot lists **[screen]**, **[say]**, **[do]**.

---

## Shot 1 — Cold open: the thesis (0:00–0:15, 15s)

- **[screen]** Title card or the Dashboard hero at `/app`.
- **[say]** "A legitimate autoscaler burst and a crypto-mining hijack look *identical* at the event level — same API calls, same burst rate. Traditional security scans run daily; these resources live for minutes. So we built a pipeline that detects on **context**, not events — and catches them before they vanish."
- **[do]** Let the Dashboard load. Don't click yet.

---

## Shot 2 — The replay simulation: the payoff (0:15–1:00, 45s)

- **[screen]** Dashboard → the **replay panel** (the hero "Telemetry replay" card; it autoplays on mount).
- **[say]** "This is five days of real telemetry replayed against a virtual clock. Watch incidents form live as events stream in. The pipeline flags this critical incident at the moment it forms —" *(pause for the before/after annotation)* "— but the next *daily* scan wouldn't see it for almost eighteen hours. By then the resource is gone. That gap is the entire problem."
- **[do]** Let the replay run to the demo-window incident. Point at the "traditional scan misses this for 17.9h" annotation. If it finished before you got here, click the replay **restart** control.

---

## Shot 3 — Ranked findings + the triage drawer (1:00–1:45, 45s)

- **[screen]** Navigate to **Risk Findings** (`/app/findings`).
- **[say]** "Instead of nine thousand raw events, the analyst works a ranked queue of incidents. Open the top one —"
- **[do]** Click the highest-ranked CRITICAL finding to open the **triage drawer**.
- **[say]** "— and every incident carries an LLM-generated triage: the likely intent, a confidence score, MITRE techniques, the specific evidence, and — crucially — the **disambiguation**: why this is the attack and not its benign look-alike. Plus recommended guardrails. This is structured JSON from the triage agent, cached, so it's instant and offline."
- **[do]** Scroll the drawer: intent → confidence bar → MITRE chips → evidence → disambiguation → guardrails → member events.

---

## Shot 4 — The noise-reduction story (1:45–2:15, 30s)

- **[screen]** Back to **Dashboard** (`/app`) → the **alert-fatigue funnel**.
- **[say]** "Here's why this is usable. Nine thousand eight hundred raw events collapse to three thousand flagged, then to five hundred twenty-nine correlated incidents — a graph stage that links events across cloud, Kubernetes, and identity logs, and folds forty autoscaler alerts into one. The SOC investigates five hundred things, not ten thousand. That's an eighty-nine percent cut in alert volume."
- **[do]** Point along the funnel stages top to bottom.

---

## Shot 5 — The evidence: analytics & calibration (2:15–2:45, 30s)

- **[screen]** Navigate to **Analytics** (`/app/analytics`).
- **[say]** "And it's measured, not eyeballed. The ablation shows each piece earning its place — recall climbs to a hundred percent, precision recovers at the incident level. The ranked queue hits ninety-six percent precision at fifty. And the risk scores are calibrated — a point-eight really means eighty percent likely-malicious, predicted versus observed almost dead-on."
- **[do]** Show the ablation/trend panels, then the **Risk Calibration** panel (observed curve hugging the diagonal).

---

## Shot 6 — Close on the live URL (2:45–3:00, 15s)

- **[screen]** Back to Dashboard, or a closing card with the URL.
- **[say]** "Ephemeral resources exist for minutes. Attackers need less. We catch them in time — detect on context, not events. It's live, it's reproducible end-to-end, and every number you saw comes from labeled ground truth we control."
- **[do]** Show <https://sentinel-rho-sooty.vercel.app/app> on screen. End.

---

## Recording checklist

- [ ] Browser full-screen, 1080p, light theme (or dark — pick one and keep it consistent).
- [ ] Pre-load `/app` once so data is cached and the replay autoplays smoothly on the take.
- [ ] Have the demo-window incident ready in Risk Findings (it's the densest CRITICAL).
- [ ] Mic check — the narration is the spine; the visuals support it.
- [ ] Keep total under 3:30 even with pauses (most judges cut there).
- [ ] Optional B-roll: trigger the **Guided tour** button once to show the tour exists, then cut.
