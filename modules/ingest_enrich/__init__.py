"""Stage 1 — Ingest & Enrich.

Reads the three authentic Stage-Zero sources (CloudTrail / K8s audit / IdP), normalizes
them into one unified event schema, cleans the data, assigns a behavioral cohort, and
computes the per-event context features the two-stage detector consumes.

Public entrypoints:
    from modules.ingest_enrich.pipeline import build_enriched, enrich_stream
"""
