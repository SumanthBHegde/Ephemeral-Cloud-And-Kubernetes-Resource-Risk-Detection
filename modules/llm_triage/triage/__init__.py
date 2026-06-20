"""Triage layers for Stage 5 (design doc §10).

  schema.py    the strict json_schema for OpenAI structured output + a stdlib validator
  evidence.py  build_evidence_bundle(incident_row, enriched, events_scored) -> compact dict
  prompt.py    SYSTEM_PROMPT + render_user_prompt(evidence)
  client.py    OpenAI call (strict json_schema, bounded retry, timeout=30) -> parsed dict
  cache.py     per-incident JSON cache keyed by incident_id + sort_keys hash of the bundle
  fallback.py  deterministic, LABEL-FREE templated triage when the API is unavailable/invalid

Constants shared across layers live here so every layer reads the same values.
"""
from __future__ import annotations

from modules.llm_triage.triage.schema import (  # noqa: F401
    TRIAGE_FIELDS,
    TRIAGE_SCHEMA,
    ValidationError,
    validate_triage,
)

# Stage 5 triages only the sharp end of the queue (design doc §10: "start with the CRITICAL band").
BANDS_TO_TRIAGE = ("CRITICAL", "HIGH")

# columns of the incidents_triaged.parquet table (incident keys + the 7 §10 triage fields + provenance).
TRIAGE_COLS = [
    "incident_id",
    "risk_rank",
    "risk_band",
    "risk_score",
    "likely_intent",
    "confidence",
    "mitre",
    "key_evidence",
    "disambiguation",
    "recommended_guardrails",
    "triage_source",   # "llm" | "cache" | "template" — provenance for evaluate.py
]

# the LLM model and request timeout (seconds). gpt-4o-mini structured calls are ~2-5s.
OPENAI_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT_S = 30
MAX_RETRIES = 3
