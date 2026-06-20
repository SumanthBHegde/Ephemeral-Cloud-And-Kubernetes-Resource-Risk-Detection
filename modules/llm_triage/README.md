# Stage 5 — LLM Triage

Turns the CRITICAL/HIGH incidents from Stage 4 into **validated structured triage JSON** (design doc
§10): `likely_intent`, `confidence`, `mitre`, `key_evidence`, `disambiguation`,
`recommended_guardrails`. A *triage agent*, not a prose generator — it classifies an already-scored,
already-clustered incident and explains why it is (or isn't) the benign look-alike.

## Inputs / outputs

| | |
|---|---|
| **In** | `data/processed/incidents_scored.parquet` (Stage 4), `events_enriched.parquet` (Stage 1), `events_scored.parquet` (Stage 4, per-event `p_event`) |
| **Out** | `data/processed/incidents_triaged.parquet` + one `data/processed/triage_cache/INC-XXXX.json` per incident |

Only `risk_band ∈ {CRITICAL, HIGH}` incidents are triaged (the sharp end of the queue).

## Run

```bash
# offline — deterministic templated triage, no API key, no network (tests/CI/demo):
python -m modules.llm_triage.build --no-llm

# live — gpt-4o-mini structured-output triage (needs OPENAI_API_KEY in .env):
cp .env.example .env   # then fill in OPENAI_API_KEY
python -m modules.llm_triage.build                 # reuses existing cache files; only triages missing ones
python -m modules.llm_triage.build --force-refresh # ignore cache, regenerate all (re-spends the API)

# evaluation (coverage, provenance, canonical spot-check, ablation row):
python -m modules.llm_triage.evaluate

# tests (offline):
python -m pytest tests/test_stage5.py -q
```

## How it works

`pipeline.run_triage()` builds a compact, JSON-serializable **evidence bundle** per incident
(`triage/evidence.py`): incident aggregates + the top-`MAX_MEMBER_EVENTS` member events ranked by
`p_event`, carrying the confusability fields (cohort, tag completeness, controller_owner, exposure,
off-hours). For each incident it resolves triage in order:

1. **cache** — `triage/cache.py`. Reuse is **existence-based**: if `INC-XXXX.json` already exists it
   is reused and the LLM is never re-called, so a rerun never re-spends the paid API (`provenance:
   cache=N`). Pass `--force-refresh` to ignore existing files and regenerate. Each file also stores a
   `sort_keys` MD5 `evidence_hash` so staleness (data changed since triage) is detectable, and
   `cache.get()` offers strict hash-checked reuse for callers that want it;
2. **LLM** — `triage/client.py` calls `gpt-4o-mini` with strict `json_schema` structured output
   (`triage/schema.py`), then validates (MITRE format, non-empty lists) and retries on bad output;
3. **templated fallback** — `triage/fallback.py`, a deterministic, **label-free** template derived
   from runtime signals only (`edge_types`, `risk_band`, `severity_floor`, `any_privileged`, source
   mix, `max_privilege_level`, exposure). Guarantees a valid record with no network.

Every record carries a `triage_source` (`llm` / `cache` / `template`) for provenance. The stage never
crashes — a failed API call degrades to the template.

## Config

`OPENAI_API_KEY` via a gitignored `.env` (see `.env.example`). Model / timeout / retry constants live
in `triage/__init__.py` (`OPENAI_MODEL`, `REQUEST_TIMEOUT_S=30`, `MAX_RETRIES=3`).
