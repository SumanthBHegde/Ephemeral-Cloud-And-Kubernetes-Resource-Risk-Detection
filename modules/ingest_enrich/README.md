# Stage 1 — Ingest & Enrich

Not yet built. Consumes the Stage Zero replay stream (`modules/data_simulation/replay/stream.py`),
normalizes the three source schemas into one event model, and attaches cohort/identity enrichment
(behavioral cohort lookup, resource metadata) ahead of detection.
