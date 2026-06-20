# Stage 4 — Risk Fusion & Calibration

Scores the Stage-3 incidents at the **incident level** — the non-negotiable "score AFTER clustering"
ordering catch (design doc §3). This is where the event-level precision that *intentionally* dropped to
~24% at correlation (benign bridge events joining incidents) is recovered as **incident-level risk
ranking**: rank incidents so the real attacks rise to the top of the analyst queue.

## Pipeline

```
detections.parquet (per-event §5 features + ensemble_score + tripwire_hit + severity_floor)
incidents.parquet  (Stage-3 incidents, one row each)
        |
        v
  score.py     event-level raw_risk = fixed-weight fusion          (LABEL-FREE)
  calibrate.py out-of-fold isotonic raw_risk -> p_event            (the one label touch)
  aggregate.py member p_event -> incident risk_score (max+mean)    (LABEL-FREE)
               + severity floor + bands + rank
        |
        v
incidents_scored.parquet  (primary)   events_scored.parquet (secondary)
```

### `score.py` — fused raw score (§9)
`raw_risk = 0.30·anomaly + 0.25·signal + 0.20·exposure + 0.10·privilege + 0.15·novelty`
- `anomaly = ensemble_score` (IF+ECOD, already [0,1]); `signal = tripwire_hit`.
- `exposure = 0.5·public_exposure_flag + 0.5·norm(exposure_window_s)` (NaN window = not exposed = 0).
- `privilege = norm(privilege_level)`, `novelty = norm(principal_novelty)`.
- Weights are **fixed expert constants** (`WEIGHTS` in `fuse/__init__.py`), not learned — so this layer
  never touches labels.

### `calibrate.py` — out-of-fold isotonic (the one sanctioned label touch)
`StratifiedKFold(5, shuffle, random_state=1337)` + `IsotonicRegression` per fold, predicting the held
fold, so a `risk_score = 0.82` behaves like a probability and **no event is scored by a calibrator that
saw it**. Stratified (not plain KFold) because at a ~17% risky rate a plain fold can contain too few
positives and fit a degenerate curve. §9/§16 explicitly permit held-out-label calibration; this is the
only place the pipeline reads `labels.jsonl`.

### `aggregate.py` — incident scoring (§9)
`risk_score = 0.7·max(p_event) + 0.3·mean(p_event)` over members (max lets one decisive event drive the
incident, mean dampens noise). Tripwire `severity_floor` forces a minimum via
`FLOOR_THRESHOLDS = {"CRITICAL": 0.80, "HIGH": 0.60}`. Bands: CRITICAL ≥0.80, HIGH ≥0.60, MEDIUM ≥0.35,
else LOW. `risk_rank` = order by `risk_score` desc (ties by `incident_id`). Evidence columns
(`max_exposure_window_s`, `max_privilege_level`, `max_novelty`, `any_privileged`, `mean_p_event`) are
surfaced for the LLM bundle / dashboard.

> **CRITICAL floor is deferred.** Stage 2/3 currently emit `severity_floor ∈ {HIGH, NONE}` only — no
> CRITICAL exists yet, so the `FLOOR_THRESHOLDS["CRITICAL"]` branch is dormant (forward-compatible). A
> future stage can promote the strongest tripwires to CRITICAL without touching this code.

## Output

- `data/processed/incidents_scored.parquet` — Stage-3 incident schema + `risk_score`, `risk_band`,
  `risk_rank`, `mean_p_event`, `max_exposure_window_s`, `max_privilege_level`, `max_novelty`,
  `any_privileged`. Primary input to Stage 5 (LLM triage) and the dashboard's ranked queue.
- `data/processed/events_scored.parquet` — `record_id`, `raw_risk`, `p_event` (dashboard "top risky
  resources/identities" + the LLM evidence bundle).

## Run

```bash
python -m modules.risk_fusion.build       # -> incidents_scored.parquet + events_scored.parquet
python -m modules.risk_fusion.evaluate    # precision/recall@K, recovery, calibration table, ablation
python -m pytest tests/test_stage4.py -q
```

## Evaluation (design doc §13)

Incident ground-truth severity = max `severity` over `is_risky=1` members; benign-only → `none`.
- **precision/recall@K** ranking incidents by `risk_score`; relevant = GT severity ≥ HIGH.
- **Precision recovery** at `risk_band ≥ HIGH` (the shipping operating point) — target **>75%**.
- **Calibration reliability** — observed `is_risky` rate per predicted-probability bin.
- **Extended ablation** — Stage 0–3 rows + a `+ risk fusion (incident, band>=HIGH)` row.
