// Steps for the judge walkthrough (driver.js spotlight tour).
//
// Each step: { route, element?, popover }
//   - route:   path navigated to before the step is shown (incl. query for deep-links)
//   - element: CSS selector of the data-tour anchor to spotlight (omit for a centered popover)
//   - popover: driver.js popover config (title/description support a little inline HTML)
//
// `incidentId` is injected at runtime so the Risk Findings deep-link is never hardcoded.
export function buildTourSteps(incidentId) {
  const findingsRoute = incidentId
    ? `/app/findings?incident=${incidentId}`
    : "/app/findings";

  return [
    {
      route: "/app",
      popover: {
        title: "A 90-second tour",
        description:
          "A legitimate autoscaler burst and a crypto-mining hijack look <b>identical</b> at the event level — same API calls, same rate. This console separates them by detecting on <b>context</b>, not events. Here are the four parts that make that work.",
      },
    },
    {
      route: "/app",
      element: '[data-tour="replay"]',
      popover: {
        title: "1 · Live replay — caught before it vanishes",
        description:
          "Five days of CloudTrail, Kubernetes and identity events replayed in seconds. Watch incidents form in real time — flagged <b>while the ephemeral resource still exists</b>, not hours after it's gone.",
        side: "top",
        align: "center",
      },
    },
    {
      route: findingsRoute,
      element: '[data-tour="incident-drawer"]',
      popover: {
        title: "2 · One incident, fully triaged",
        description:
          "Graph correlation collapses dozens of raw alerts into a single incident spanning cloud, K8s and IdP. The LLM triage adds likely <b>intent</b>, <b>MITRE ATT&CK</b> techniques, key evidence, a forensic snapshot that survives the resource, and recommended guardrails.",
        side: "left",
        align: "start",
      },
    },
    {
      route: "/app/analytics",
      element: '[data-tour="funnel"]',
      popover: {
        title: "3 · ~89% fewer alerts to triage",
        description:
          "The alert-fatigue funnel: thousands of raw events compress to a few hundred ranked incidents — <b>without</b> sacrificing recall. Cohort-aware suppression is what buys this.",
        side: "top",
        align: "center",
      },
    },
    {
      route: "/app/analytics",
      element: '[data-tour="calibration"]',
      popover: {
        title: "4 · Scores you can trust",
        description:
          "Risk scores are calibrated — a 0.8 really means ~80% likely malicious. The ranked incident queue reaches <b>96% precision@50</b>. That's the whole thesis: context beats events.",
        side: "left",
        align: "center",
      },
    },
  ];
}
