# Stage 6 — Dashboard (Sentinel console)

An enterprise SOC-style web console that visualizes the real pipeline outputs: the ranked incident
queue, per-incident LLM triage cards, the alert-fatigue reduction curve, an event/resource explorer,
analytics, and a **real-time replay simulation**.

Built with **React 19 + Vite + Tailwind v3** using the ThreatLens design language
([docs/frontend_design_guidlines.md](../../docs/frontend_design_guidlines.md)). It is **frontend-only**:
a Python step exports the pipeline's parquet outputs to static JSON that the app fetches locally — no
backend, no network at demo time.

## Run it (two steps)

```bash
# 1. Export the pipeline outputs to JSON (re-run after any pipeline rerun)
python -m modules.dashboard.build          # -> modules/dashboard/frontend/public/data/*.json

# 2. Start the dev server
cd modules/dashboard/frontend
npm install
npm run dev                                 # http://localhost:5173/app
# npm run build && npm run preview          # production bundle
```

`build.py` requires the upstream artifacts in `data/processed/` (`incidents_scored.parquet`,
`incidents_triaged.parquet`, `events_enriched.parquet`, `events_scored.parquet`, `event_incidents.parquet`,
`detections.parquet`). It mirrors the `(event_time, source)` ordering of
[`replay/stream.py`](../data_simulation/replay/stream.py).

## Exported JSON (`frontend/public/data/`)

| File | What it holds |
|---|---|
| `incidents.json` | 529 incidents (`incidents_scored` ⟕ `incidents_triaged`), each with top-8 member events by `p_event` |
| `events.json` | 9,857 enriched events + `p_event` + `incident_id` (Resource Explorer table) |
| `metrics.json` | KPIs, alert-fatigue funnel, severity/cohort/source/MITRE aggregates, riskiest namespaces/cohorts/principals |
| `reports.json` | top-20 triaged incidents formatted as documents |
| `notifications.json` | recent CRITICAL/HIGH findings |
| `replay.json` | time-ordered events + 15-min `timeline_bins` + per-incident formation/scan times + `demo_window` |

## Pages

Dashboard · Risk Findings (+ triage drawer) · Resource Explorer · Analytics · AI Risk Analyst (canned,
triage-driven) · Reports · Notifications · Settings. No login/MFA — `/` redirects to `/app`.

## Real-time replay (the headline feature)

[`src/lib/ReplayEngine.jsx`](frontend/src/lib/ReplayEngine.jsx) drives a virtual clock; the Dashboard's
[`ReplayPanel`](frontend/src/components/ReplayPanel.jsx) animates events arriving and incidents forming.
**Speed is relative to a fixed real-time budget** (`TARGET_DURATION_S = 120` → the active range plays in
~2 min at 1×; slider 0.5×/1×/2×) — "1×" is **not** wall-clock real-time. The chart is fed by 15-minute
bins to avoid per-event re-renders. The demo window is the **densest CRITICAL** incident
(`max(event_count)`, currently INC-0230), and a before/after marker contrasts pipeline detection time
against the next daily scan ("Traditional scan misses this for N hours").

## Note on naming

The event table is labelled **Resource Explorer** (route `/app/resources`) to honor the design
handoff's IOC-Explorer → Resource-Explorer mapping (§7); it surfaces the enriched event/resource stream.
