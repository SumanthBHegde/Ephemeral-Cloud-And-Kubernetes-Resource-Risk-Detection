# ThreatLens — AI-Powered Threat Intelligence Feed Aggregator

Frontend mockup for **iHackMyPlace 2026** (Société Générale campus hackathon · Cybersecurity × AI).

> Consolidates cyber threat data from multiple online sources, auto-fetches posts from curated
> RSS/Atom feeds, extracts Indicators of Compromise (IOCs), and generates concise AI-driven
> threat summaries. **This is a UI mockup — all data is fabricated, there is no backend.**

## Tech stack

- **React 19 + Vite** — fast SPA
- **Tailwind CSS v3** — styling, with the Société Générale "Enterprise Banking" palette (`#C8102E`)
- **shadcn/ui-style components** (hand-rolled in `src/components/ui`)
- **Recharts** — area / line / bar / pie / radar charts + heatmap
- **lucide-react** — icons
- **react-router-dom** — routing
- Light theme by default with a working **dark mode** toggle (persisted to `localStorage`)

## Run it

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production build into dist/
```

## Screens

| Route | Page | Highlights |
|-------|------|-----------|
| `/` | Landing | Hero, features, "how it works", stats, CTA |
| `/login` | Auth | Email + password, social/SSO, **MFA OTP** step, passkey |
| `/app` | Dashboard | KPI cards w/ sparklines, severity area chart, donut, activity timeline, top actors, ingestion bars |
| `/app/feed` | Threat Feed | AI-summarized cards, grid/list views, filters, **detail drawer** with IOCs |
| `/app/iocs` | IOC Explorer | Sortable/filterable table, row selection, bulk actions, confidence bars, TLP, pagination, export |
| `/app/analytics` | Analytics | Trend lines, IOC distribution, sector radar, source donut, **activity heatmap** |
| `/app/chat` | AI Analyst | Full-screen chat, **simulated streaming**, typing indicator, source citations, model selector, suggested prompts |
| `/app/sources` | Feed Sources | RSS/Atom source cards, health status, enable/disable, **add-feed modal** |
| `/app/reports` | Reports | AI-generated threat brief w/ confidence scores, PDF-preview layout |
| `/app/search` | Search | Global search, tabs, saved & recent searches |
| `/app/history` | History | Audit trail / activity log |
| `/app/notifications` | Notifications | Sector-aware alerts, filters, preferences |
| `/app/admin` | Admin | Member/role table, system health |
| `/app/settings` | Settings | Account, security/2FA, API keys, appearance, preferences |
| `/app/profile` | Profile | Stats, contributions, achievements |

## Global UX

- **Command palette** — `Cmd/Ctrl + K` to search threats, IOCs and jump between pages
- Collapsible sidebar, responsive layout (mobile drawer), polished empty / loading states
- Accessible focus states, keyboard nav in the palette, 8-point spacing grid per the design guide

## Notes for judges / integration

Swap the contents of `src/lib/mockData.js` for live API responses to wire this up to a real
backend (feed ingestion + NLP IOC extraction + LLM summarization). Component props already match
that data shape.
