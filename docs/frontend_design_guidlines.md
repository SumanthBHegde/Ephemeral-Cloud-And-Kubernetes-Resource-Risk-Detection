# ThreatLens Design Handoff

Use this document as the design and UI implementation brief for a new application similar to ThreatLens: **Ephemeral Cloud & Kubernetes Resource Risk Detection**. The goal is to reuse the complete visual language, component patterns, and interaction model from ThreatLens while renaming the domain vocabulary to cloud and Kubernetes resource risk.

This is a design handoff, not a full product blueprint. Do not invent deep backend workflows, schemas, or product roadmap unless explicitly requested. Build a polished frontend experience that feels like the same enterprise security console.

## 1. Design Intent

ThreatLens is a compact, analyst-first enterprise security console. It should feel like an operational SOC tool: fast to scan, information dense, status heavy, and quiet rather than promotional.

Core traits:

- Enterprise security dashboard, not a marketing site.
- Dense but readable layout with compact cards, tables, badges, charts, and drawers.
- Light theme by default with a complete dark mode.
- Red primary brand accent: `#C8102E`.
- Data-rich surfaces: KPIs, severity/risk badges, activity timelines, chart panels, filter bars, drawers, command palette, and sortable tables.
- Interaction language: filtering, searching, toggling, exporting, opening detail drawers, command palette navigation, bulk actions, and modal setup flows.
- Icons: use `lucide-react` consistently.
- Charts: use `recharts` with restrained grid lines, muted axes, custom tooltips, and semantic colors.

For the Kubernetes/cloud risk app, keep this exact visual style. Replace threat-intel nouns with cloud/Kubernetes nouns only where needed.

## 2. Recommended Stack

Use the same frontend stack:

```txt
React 19
Vite
Tailwind CSS v3
react-router-dom
lucide-react
recharts
clsx
tailwind-merge
```

Use hand-rolled shadcn-style primitives rather than importing a large component library. Keep components small, composable, and Tailwind-based.

Suggested structure:

```txt
src/
  App.jsx
  main.jsx
  index.css
  components/
    ui/index.jsx
    shared.jsx
    layout/AppShell.jsx
    layout/CommandPalette.jsx
  lib/
    theme.jsx
    utils.js
    mockData.js
  pages/
    Dashboard.jsx
    Resources.jsx
    Findings.jsx
    Analytics.jsx
    Chat.jsx
    Reports.jsx
    Settings.jsx
    Notifications.jsx
    Login.jsx
```

## 3. Theme Tokens

Use CSS custom properties and Tailwind token aliases. Keep the current colors and behavior.

### CSS Variables

```css
:root {
  --background: 0 0% 100%;
  --foreground: 215 25% 17%;
  --surface: 210 17% 98%;
  --card: 0 0% 100%;
  --card-foreground: 215 25% 17%;
  --popover: 0 0% 100%;
  --popover-foreground: 215 25% 17%;
  --primary: 351 85% 42%; /* #C8102E */
  --primary-foreground: 0 0% 100%;
  --muted: 210 17% 96%;
  --muted-foreground: 220 9% 46%;
  --border: 220 13% 91%;
  --input: 220 13% 91%;
  --ring: 351 85% 42%;
  --success: 142 71% 45%;
  --warning: 38 92% 50%;
  --danger: 0 84% 60%;
  --info: 217 91% 60%;
}

.dark {
  --background: 222 30% 7%;
  --foreground: 213 27% 92%;
  --surface: 220 26% 11%;
  --card: 220 26% 11%;
  --card-foreground: 213 27% 92%;
  --popover: 220 26% 11%;
  --popover-foreground: 213 27% 92%;
  --primary: 351 83% 53%;
  --primary-foreground: 0 0% 100%;
  --muted: 220 22% 16%;
  --muted-foreground: 217 12% 60%;
  --border: 220 20% 18%;
  --input: 220 20% 18%;
  --ring: 351 83% 53%;
  --success: 142 65% 50%;
  --warning: 38 92% 55%;
  --danger: 0 84% 65%;
  --info: 217 91% 65%;
}
```

### Tailwind Extensions

```js
extend: {
  colors: {
    border: "hsl(var(--border))",
    input: "hsl(var(--input))",
    ring: "hsl(var(--ring))",
    background: "hsl(var(--background))",
    foreground: "hsl(var(--foreground))",
    surface: "hsl(var(--surface))",
    primary: {
      DEFAULT: "hsl(var(--primary))",
      foreground: "hsl(var(--primary-foreground))",
    },
    muted: {
      DEFAULT: "hsl(var(--muted))",
      foreground: "hsl(var(--muted-foreground))",
    },
    card: {
      DEFAULT: "hsl(var(--card))",
      foreground: "hsl(var(--card-foreground))",
    },
    popover: {
      DEFAULT: "hsl(var(--popover))",
      foreground: "hsl(var(--popover-foreground))",
    },
    success: "hsl(var(--success))",
    warning: "hsl(var(--warning))",
    danger: "hsl(var(--danger))",
    info: "hsl(var(--info))",
  },
  fontFamily: {
    sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
    mono: ["JetBrains Mono", "ui-monospace", "monospace"],
  },
  borderRadius: {
    btn: "8px",
    card: "12px",
    dialog: "16px",
  },
  boxShadow: {
    sm: "0 1px 2px 0 rgb(0 0 0 / 0.05)",
    md: "0 4px 12px -2px rgb(0 0 0 / 0.08), 0 2px 6px -2px rgb(0 0 0 / 0.05)",
    lg: "0 12px 32px -4px rgb(0 0 0 / 0.12), 0 4px 12px -4px rgb(0 0 0 / 0.08)",
  },
}
```

### Typography And Spacing

- Use `Inter` for UI text.
- Use `JetBrains Mono` for resource IDs, CVEs, IPs, hashes, Kubernetes object names, namespaces, and API tokens.
- Page titles: `text-2xl font-bold tracking-tight`.
- Card titles: `font-semibold leading-tight tracking-tight`.
- Body text: `text-sm`.
- Metadata: `text-xs text-muted-foreground`.
- Use an 8px spacing rhythm: `p-3`, `p-4`, `p-5`, `gap-3`, `gap-4`.
- Prefer compact layouts over large airy hero sections inside the app.

### Motion

Use subtle motion only:

- `animate-fade-in`: opacity plus `translateY(4px)`, `0.3s ease-out`.
- `animate-slide-in`: small horizontal slide, `0.25s ease-out`.
- `animate-pulse-dot`: status/live indicators.
- Skeleton shimmer for loading placeholders.

## 4. Layout System

### App Shell

The main app uses a fixed-height console layout:

- Root: `flex h-screen overflow-hidden bg-surface`.
- Sidebar: fixed on mobile, static on large screens.
- Content: topbar plus scrollable main region.
- Main content width: `mx-auto max-w-[1400px] p-4 sm:p-6`.
- Scrollbars: thin custom scrollbar utility.

### Sidebar

Behavior:

- Width `w-64` expanded, `w-[72px]` collapsed.
- Border right, card background.
- Group nav items into sections with uppercase labels.
- Active route has `bg-primary/10 text-primary` plus a tiny red left indicator.
- Collapsed state shows icons only with `title` tooltips.
- Mobile state opens as a drawer with dark backdrop.

Recommended cloud/Kubernetes nav labels, keeping structure flexible:

- Overview: Dashboard, Resource Feed, Risk Explorer, Analytics.
- Intelligence: AI Analyst, Sources/Integrations, Reports, Search.
- Workspace: History, Notifications, Admin, Settings.

These labels are examples. Do not treat them as a full product blueprint.

### Topbar

Elements:

- Mobile menu icon.
- Global search button styled like an input.
- `Cmd/Ctrl + K` command hint.
- Live status badge.
- Theme toggle.
- Notifications dropdown.
- Help icon.
- User avatar dropdown.

Search placeholder should adapt to the new domain, for example:

```txt
Search resources, clusters, namespaces...
```

### Command Palette

Use a centered modal at top offset `pt-[12vh]`.

Pattern:

- Backdrop: `bg-black/50 backdrop-blur-sm`.
- Dialog: `max-w-xl rounded-dialog border border-border bg-popover shadow-lg`.
- Search row: 48px tall with icon, input, ESC key.
- Results grouped by uppercase group label.
- Active item: `bg-primary/10 text-primary`.
- Keyboard controls: up/down, enter, escape.

Adapt result groups to pages, resources, findings, clusters, namespaces, or policies.

### Page Header

Use a shared `PageHeader`:

- Optional breadcrumb line.
- Title and description on the left.
- Actions on the right.
- Responsive stack on small screens.

Example:

```jsx
<PageHeader
  title="Resource Dashboard"
  description="Live overview of ephemeral cloud and Kubernetes resource risk."
  breadcrumb={["Console", "Resources"]}
>
  <Button variant="outline" size="sm">Refresh</Button>
  <Button size="sm">Export</Button>
</PageHeader>
```

## 5. Component Guide

### Button

Variants:

- `default`: red primary background, white text.
- `secondary`: surface background, border.
- `outline`: transparent with border.
- `ghost`: hover muted.
- `danger`: danger background.
- `link`: primary underline.

Sizes:

- `default`: `h-9 px-4 text-sm`.
- `sm`: `h-8 px-3 text-xs`.
- `lg`: `h-11 px-6 text-base`.
- `icon`: `h-9 w-9`.

Rules:

- Include icons for clear actions.
- Use `lucide-react` icons.
- Keep button text short.
- Use icon-only buttons for repeated table/drawer actions.

### Card

Base:

```txt
rounded-card border border-border bg-card text-card-foreground shadow-sm
```

Use cards for:

- KPI tiles.
- Chart panels.
- Tables.
- Repeated grid items.
- Modals/drawers.
- Settings sections.

Avoid nested cards unless the inner element is genuinely framed content.

### Badge

Base:

```txt
inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium
```

Variants:

- `primary`: red-tinted.
- `success`: green-tinted.
- `warning`: amber-tinted.
- `danger`: red danger.
- `info`: blue.
- `outline`: neutral.

Use badges heavily for severity, risk, health, status, source type, TLP/classification, namespaces, and environment labels.

### Severity Or Risk Badge

Current mapping:

- Critical -> `danger`.
- High -> `warning`.
- Medium -> `info`.
- Low -> `success`.
- Info -> `outline`.

For the cloud/Kubernetes app, the same component can display:

- Critical, High, Medium, Low, Info.
- Or Risk: Critical, High, Medium, Low.
- Include a small colored dot before the label.

### Inputs And Search

Inputs:

- Height `h-9`.
- `rounded-btn border border-input bg-background`.
- Focus ring uses `ring`.

Search input:

- Wrap input in relative container.
- Left search icon.
- Padding `pl-9`.

Use filter bars with search plus selects plus clear action.

### Select

Use native styled select:

- `appearance-none`.
- Right `ChevronDown`.
- Height `h-9`.
- Same border and focus treatment as inputs.

### Switch

Use for binary settings, feed/source enablement, alert preferences, and feature toggles.

Visual:

- Track: `h-5 w-9 rounded-full`.
- On: primary background.
- Off: muted foreground at 30%.
- Thumb: `h-4 w-4 bg-white shadow`.

### Tabs And Segmented Controls

Tabs list:

```txt
inline-flex items-center gap-1 rounded-btn bg-surface border border-border p-1
```

Active tab:

```txt
bg-card text-foreground shadow-sm
```

Use for filters like All, Unread, Critical, or page-local modes.

### Dropdown

Use lightweight dropdowns for user menu, notifications, card actions, and row actions.

Surface:

```txt
absolute z-50 mt-2 min-w-[200px] rounded-card border border-border bg-popover p-1.5 shadow-lg
```

Items:

```txt
flex w-full items-center gap-2 rounded-[6px] px-2.5 py-2 text-sm hover:bg-muted
```

### Modal And Drawer

Modal:

- Full-screen fixed overlay.
- Backdrop: `bg-black/50 backdrop-blur-sm`.
- Dialog: `max-w-lg rounded-dialog border bg-card p-6 shadow-lg`.
- Close icon top right.
- Footer actions right aligned.

Detail drawer:

- Use for resource/finding detail.
- Fixed overlay with backdrop.
- Panel anchored right.
- Width: `w-full max-w-lg`.
- Border left, card background, scrollable body, sticky action footer.

Drawer sections should include:

- Header with severity/risk badge and IDs.
- AI or summary panel tinted `primary/5`.
- Details grid.
- Tags/labels.
- Related indicators/resources.
- Action footer.

### Progress

Use for confidence, risk score, coverage, drift score, policy pass rate, or scan progress.

Base:

```txt
h-2 w-full overflow-hidden rounded-full bg-muted
```

Bar color:

- Primary by default.
- Success for strong/good.
- Warning for medium.
- Danger for risky/failed.

### Avatar

Use initials when no image exists.

Style:

```txt
flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary
```

### Skeleton

Use shimmer utility with `rounded-md bg-muted`.

### Checkbox

Use custom button checkbox:

- `h-4 w-4 rounded border`.
- Checked: primary background and check icon.
- Used for table row selection and bulk actions.

### Empty State

Use dashed border, centered icon, title, description, and optional action.

Pattern:

```txt
flex flex-col items-center justify-center rounded-card border border-dashed border-border py-16 text-center
```

### Stat Cards

Use a compact card with icon, value, label, trend, and optional sparkline.

Pattern:

- Top row: icon tile plus sparkline or badge.
- Main value: `text-2xl font-bold`.
- Label: `text-sm text-muted-foreground`.
- Trend: tiny arrow icon, semantic color, comparison text.

## 6. Page Pattern Guide

### Dashboard

Use the dashboard as the primary first screen after login.

Pattern:

- PageHeader with refresh/export actions.
- 4 KPI cards in responsive grid.
- Main chart row: large trend chart plus donut/breakdown.
- Lower row: latest findings/resources list plus activity timeline.
- Additional row: volume bars plus top entities list.

For cloud/Kubernetes, rename data only:

- Active Threats -> Active Risk Findings.
- IOCs -> Ephemeral Resources.
- Feeds Monitored -> Connected Accounts/Clusters.
- Critical Alerts -> Critical Exposures.
- Threat Volume -> Risk Findings by Severity.
- Latest Threats -> Latest Risk Findings.
- Top Threat Actors -> Riskiest Clusters/Namespaces/Accounts.

### Feed Or Grid/List Page

Use for resource risk findings or resource feed.

Pattern:

- PageHeader with grid/list segmented control.
- Filter bar card: search, severity/risk select, category/type select, clear, result count.
- Grid view: cards with severity badge, time, title, summary, tags, source, counts.
- List view: compact rows with severity, title, summary, metadata.
- Click opens right-side detail drawer.

### Detail Drawer

Use the Threat drawer pattern for finding/resource detail.

Keep:

- Severity/risk badge.
- ID badge in monospace.
- Optional critical identifier badge.
- Source/time metadata.
- AI summary or risk explanation panel.
- Two-column details grid.
- Tags/labels.
- Related objects list.
- Footer actions.

Cloud/Kubernetes copy examples:

- "Risk Summary" instead of "AI Summary".
- "Related resources" instead of "Extracted IOCs".
- "Ask AI Analyst" can remain if the app includes an analyst chat.

### Table Explorer

Use for Kubernetes objects, cloud resources, findings, policies, or accounts.

Pattern:

- KPI mini-cards above the table.
- Card-wrapped table.
- Toolbar with search and type/status filters.
- Row selection with bulk action bar.
- Sortable headers with chevron icon.
- Monospace identifiers.
- Severity/risk badge column.
- Progress column for confidence or score.
- Pagination footer.
- Horizontal scroll on small screens.

### Analytics

Use multiple card-based chart panels.

Patterns:

- Line chart for risk trend.
- Vertical bar chart for resource or finding type distribution.
- Radar chart for environment/sector/category intensity if useful.
- Donut chart with legend for source or severity distribution.
- Heatmap grid for activity by day/hour or resource lifetime buckets.

Chart style:

- Recharts `ResponsiveContainer`.
- Axes use `fontSize: 12` and muted foreground.
- Grid uses `hsl(var(--border))`, dashed.
- Tooltip is custom, `rounded-btn border bg-popover px-3 py-2 text-xs shadow-md`.
- Primary bars use `hsl(var(--primary))`.
- Semantic series use danger, warning, info, success.

### Chat Surface

Use if the new app has AI analysis.

Pattern:

- Full-height app panel: `h-[calc(100vh-7rem)]`.
- Optional left conversation rail.
- Main card with top status/model selector.
- Scrollable message list.
- User bubbles: primary background.
- Assistant bubbles: card background with border.
- Citations as small pill links.
- Composer at bottom with paperclip, textarea, send button.
- Suggested prompts as rounded chips.
- Streaming simulated with pulsing dots if needed.

### Reports Preview

Use for generated risk reports.

Pattern:

- Left report list.
- Right document preview card.
- Toolbar with print/share/download icon buttons.
- Document header with AI-generated/reviewed badges.
- Sections with confidence progress bars.
- Referenced findings/resources list.
- Footer disclaimer.

### Notifications

Pattern:

- Filter segmented control: All, Unread, Critical.
- List card with rows.
- Severity icon tile.
- Badge for severity.
- Unread dot.
- Preferences side card with switches.

### Settings

Pattern:

- Left local side nav.
- Right content cards.
- Tabs: Account, Security, API Keys, Appearance, Preferences.
- Use forms, switches, API key rows, theme selection cards, and separators.

### Auth

Pattern:

- Split layout on desktop.
- Left brand panel with primary background, stat callouts, and grid texture.
- Right form centered with `max-w-sm`.
- Login stage with SSO buttons, email/password inputs, remember checkbox.
- MFA stage with 6 OTP boxes and passkey option.

For the new app, brand copy should change but layout should stay identical.

## 7. Domain Adaptation Notes

Only adapt labels and examples. Preserve layout, component behavior, and theme.

Suggested vocabulary mappings:

```txt
ThreatLens -> chosen product name
Threat Dashboard -> Resource Risk Dashboard
Threat Feed -> Risk Findings
IOC Explorer -> Resource Explorer
Feed Sources -> Cloud Sources / Integrations
AI Analyst -> AI Risk Analyst
Threats -> Findings
IOCs -> Resources / Indicators
Severity -> Risk
Source -> Cloud account / cluster / scanner
Threat actor -> Cluster / namespace / account / workload group
CVE -> Policy / exposure / misconfiguration ID when appropriate
TLP -> Environment / sensitivity / data classification when appropriate
```

Possible resource/risk nouns:

- Cluster.
- Namespace.
- Pod.
- Deployment.
- Job/CronJob.
- Service.
- Ingress.
- Node.
- IAM role.
- Security group.
- Public IP.
- Load balancer.
- Ephemeral volume.
- Orphaned resource.
- Short-lived privileged workload.
- Misconfigured resource.

Keep this document design-focused. Do not define backend ingestion, cloud provider APIs, Kubernetes scanners, or risk scoring formulas unless a later request asks for that.

## 8. Visual QA Checklist

When implementation is ready, run the app and inspect these routes in both light and dark themes:

- `/` landing or direct app route, if a landing page exists.
- `/login`.
- `/app` dashboard.
- `/app/resources` or equivalent explorer/feed page.
- `/app/analytics`.
- `/app/chat`, if included.
- `/app/reports`, if included.
- `/app/notifications`.
- `/app/settings`.

Screenshot viewports:

- Desktop: `1440x900`.
- Laptop: `1280x800`.
- Tablet: `768x1024`.
- Mobile: `390x844`.

Check:

- Sidebar collapse works on desktop.
- Mobile sidebar opens as drawer.
- Topbar search and command palette are aligned.
- No text overlaps inside cards, buttons, badges, table cells, chart legends, or drawers.
- Tables scroll horizontally on mobile.
- Drawers and modals fit mobile width.
- Dark mode colors preserve contrast.
- Charts render with visible axes, legends, and tooltips.
- Red primary accent is used consistently but not overused.
- Empty/loading states look intentional.
- Keyboard navigation works in the command palette.

## 9. Copy-Paste Claude Code Starter Prompt

Use this prompt to start the new project:

```txt
Build a React + Vite + Tailwind CSS frontend for "Ephemeral Cloud & Kubernetes Resource Risk Detection" using the ThreatLens design handoff below as the source of truth.

Preserve the exact visual style:
- Enterprise SOC/security console.
- Light theme by default, dark mode toggle.
- Primary red #C8102E.
- Inter font, JetBrains Mono for IDs.
- Compact data-dense cards, tables, drawers, charts, badges, command palette, and settings forms.
- lucide-react icons.
- Recharts for charts.
- Hand-rolled shadcn-style UI primitives using Tailwind, clsx, and tailwind-merge.

Do not make a marketing-first site. The first authenticated screen should be a usable operational console. Keep implementation frontend-only with fabricated mock data unless told otherwise.

Adapt domain labels from threat intelligence to cloud/Kubernetes risk detection, but do not invent a complex backend architecture or full product roadmap. Focus on UI components, layout, visual consistency, and realistic mock interactions.

Implement:
- Theme tokens exactly as specified.
- AppShell with collapsible sidebar, topbar, command palette, dark mode, notifications, user menu.
- Reusable UI primitives: Button, Card, Badge, RiskBadge/SeverityBadge, Input, SearchInput, Select, Switch, Tabs, Dropdown, Modal, Progress, Avatar, Skeleton, Checkbox, Separator.
- Shared PageHeader, EmptyState, Sparkline, StatPill.
- Page patterns matching the handoff: dashboard, grid/list risk feed with drawer, table explorer, analytics charts, settings, notifications, auth. Include chat/reports only if scope allows.

After building, run the app and visually verify desktop and mobile layouts against the QA checklist.
```

## 10. Acceptance Criteria

The new UI should be considered aligned with ThreatLens if:

- It uses the same shell, spacing, colors, typography, radius, shadow, and component language.
- It feels like a security operations console rather than a landing page.
- It supports light/dark mode with the same token system.
- It includes compact dashboard, filtering, table, drawer, chart, notification, and settings patterns.
- It uses semantic risk/status colors consistently.
- It remains domain-adapted to ephemeral cloud and Kubernetes resource risk without over-specifying backend behavior.
