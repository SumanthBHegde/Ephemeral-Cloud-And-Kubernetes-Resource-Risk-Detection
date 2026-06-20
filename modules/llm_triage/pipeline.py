"""Stage 5 orchestrator: scored incidents -> validated triage JSON per incident (design doc §10).

    run_triage()  read incidents_scored.parquet + events_enriched.parquet + events_scored.parquet
                  (or accept DataFrames), build a per-incident evidence bundle for every CRITICAL/HIGH
                  incident, triage it (cache -> LLM -> templated fallback), and write
                  incidents_triaged.parquet plus one JSON per incident under triage_cache/.

This is the "easy hard part" (§1.4): the ML/graph work is done upstream; here we articulate and
VALIDATE the signal already present. The stage never crashes — a failed LLM call falls back to a
deterministic template. With use_llm=False the whole stage runs offline (tests, CI, the live demo).
"""
from __future__ import annotations

import pathlib
from typing import Optional

import pandas as pd

from modules.llm_triage.triage import BANDS_TO_TRIAGE, TRIAGE_COLS, TRIAGE_FIELDS
from modules.llm_triage.triage import cache as cache_mod
from modules.llm_triage.triage.evidence import build_evidence_bundle
from modules.llm_triage.triage.fallback import build_fallback
from modules.llm_triage.triage.schema import ValidationError, validate_triage

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_INCIDENTS = REPO_ROOT / "data" / "processed" / "incidents_scored.parquet"
DEFAULT_ENRICHED = REPO_ROOT / "data" / "processed" / "events_enriched.parquet"
DEFAULT_EVENTS_SCORED = REPO_ROOT / "data" / "processed" / "events_scored.parquet"
DEFAULT_OUT = REPO_ROOT / "data" / "processed" / "incidents_triaged.parquet"
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "processed" / "triage_cache"


def _read(source, what: str, builder_hint: str) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        return source.copy()
    path = pathlib.Path(source)
    if not path.exists():
        raise FileNotFoundError(f"{what} not found at {path}; run `{builder_hint}` first")
    return pd.read_parquet(path)


def _triage_one(incident_row, enriched, events_scored, cache_dir, use_llm,
                force_refresh: bool = False) -> dict:
    """Triage a single incident: existing cache -> LLM -> templated fallback. Returns a validated
    record tagged with its provenance (`triage_source`).

    Cache reuse is existence-based: if a (valid) cache file already exists for this incident it is
    reused and NO LLM call is made — the cost guard. `force_refresh=True` ignores existing files and
    regenerates. A corrupt/incomplete cache file falls through to regeneration.
    """
    incident_id = str(incident_row["incident_id"])
    bundle = build_evidence_bundle(incident_row, enriched, events_scored)
    ev_hash = cache_mod.evidence_hash(bundle)

    if cache_dir is not None and not force_refresh:
        existing = cache_mod.read(cache_dir, incident_id)
        if existing is not None and all(f in existing for f in TRIAGE_FIELDS):
            rec = {f: existing[f] for f in TRIAGE_FIELDS}
            try:
                validate_triage(rec)
                return rec | {"triage_source": "cache"}
            except ValidationError:
                pass  # corrupt cache entry -> fall through and regenerate

    if use_llm:
        try:
            from modules.llm_triage.triage.client import triage_incident
            rec = triage_incident(bundle)
            source = "llm"
        except Exception:
            rec = build_fallback(bundle)
            source = "template"
    else:
        rec = build_fallback(bundle)
        source = "template"

    rec = validate_triage(rec)
    record = {f: rec[f] for f in TRIAGE_FIELDS}
    record["triage_source"] = source
    if cache_dir is not None:
        cache_mod.put(cache_dir, incident_id, ev_hash, record)
    return record


def run_triage(
    incidents_scored: pd.DataFrame | pathlib.Path | str = DEFAULT_INCIDENTS,
    enriched: pd.DataFrame | pathlib.Path | str = DEFAULT_ENRICHED,
    events_scored: pd.DataFrame | pathlib.Path | str = DEFAULT_EVENTS_SCORED,
    out_path: Optional[pathlib.Path | str] = DEFAULT_OUT,
    cache_dir: Optional[pathlib.Path | str] = DEFAULT_CACHE_DIR,
    bands=BANDS_TO_TRIAGE,
    use_llm: bool = True,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Triage every incident whose risk_band is in `bands` (default CRITICAL+HIGH), in rank order.

    Sources are DataFrames or Parquet paths. Writes incidents_triaged.parquet (when out_path given)
    and one JSON per incident under cache_dir (when given). Returns the triaged DataFrame.
    With use_llm=False, every record is produced by the deterministic template — no key, no network.

    Cache reuse is existence-based: an incident that already has a cache file is reused (no LLM call),
    so a rerun never re-spends the paid API. Pass force_refresh=True to ignore existing cache files
    and regenerate every incident.
    """
    inc = _read(incidents_scored, "scored incidents", "python -m modules.risk_fusion.build")
    enr = _read(enriched, "enriched events", "python -m modules.ingest_enrich.build")
    evs = _read(events_scored, "scored events", "python -m modules.risk_fusion.build")

    selected = inc[inc["risk_band"].isin(bands)].sort_values("risk_rank")

    rows = []
    for _, incident_row in selected.iterrows():
        rec = _triage_one(incident_row, enr, evs, cache_dir, use_llm, force_refresh)
        rows.append({
            "incident_id": incident_row["incident_id"],
            "risk_rank": int(incident_row["risk_rank"]),
            "risk_band": incident_row["risk_band"],
            "risk_score": float(incident_row["risk_score"]),
            **rec,
        })

    triaged = pd.DataFrame(rows, columns=TRIAGE_COLS).sort_values("risk_rank").reset_index(drop=True)

    if out_path is not None:
        out_path = pathlib.Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        triaged.to_parquet(out_path, engine="pyarrow", index=False)
    return triaged
