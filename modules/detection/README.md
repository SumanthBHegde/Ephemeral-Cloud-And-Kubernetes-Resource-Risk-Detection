# Stage 2 — Two-Stage Detection

Reads the enriched event table from Stage 1 (`data/processed/events_enriched.parquet`) and
flags risky events in two stages plus an always-on rule layer. The design rationale lives in
[docs/ephemeral_risk_detection_analysis.md](../../docs/ephemeral_risk_detection_analysis.md)
§3, §7, §16; this is the implementation.

## Run

```bash
pip install -r requirements.txt                       # adds scikit-learn, pyod, scipy
python -m modules.ingest_enrich.build                 # produce the enriched table first
python -m modules.detection.build                     # -> data/processed/detections.parquet
python -m modules.detection.evaluate                  # precision/recall/F1 + ablation table
python -m pytest tests/test_stage2.py -q
```

## The three layers

1. **Always-on tripwires** (`detect/tripwires.py`) — deterministic rules that force
   `predicted_risky=1` and a severity floor regardless of the ML score: NodePort `0.0.0.0/0`,
   bare privileged pod, `burst_rate > 10`, broad RBAC. (Design doc §3 step 2.)
2. **Stage 1 — recall-first anomaly ensemble** (`detect/anomaly.py`) — **unsupervised**, over
   the §5 feature matrix. Two complementary detectors vote and their min-max-normalized scores
   are averaged:
   - **Isolation Forest** (scikit-learn) — primary; ~10k×8 tabular is its sweet spot.
   - **ECOD** (PyOD) — required second vote; parameter-free, deterministic, with interpretable
     per-dimension outlier contributions.

   Tuned for high recall — over-flagging here is expected and acceptable.
   (TabPFN and a PyTorch/Keras autoencoder were considered and rejected — see design doc §16.)
3. **Stage 2 — cohort-aware suppression** (`detect/suppression.py`) — rule/statistical, no ML.
   Drops candidates that are normal *for their cohort* (low `cohort_deviation`, complete tags,
   in-cohort hours). The `unknown` cohort and tripwire hits are **never** suppressed. This is
   where precision is won without sacrificing Stage-1 recall.

`predicted_risky = (is_candidate & ~is_suppressed) | tripwire_hit`.

## What it produces

`data/processed/detections.parquet` — the enriched rows plus: `if_score`, `ecod_score`,
`ensemble_score`, `is_candidate`, `tripwire_hit`, `is_suppressed`, `predicted_risky`,
`severity_floor`. This is the input to Stage 3 (graph correlation).

## Labels stay separate

`evaluate.py` joins `data/raw/labels.jsonl` on `record_id` for precision/recall/F1, alert
reduction, and the ablation table (tripwires-only → +ensemble → +suppression). Labels are never
read into the detector itself — both detectors are unsupervised.

## Layout

```
detect/      tripwires.py   (always-on deterministic rules)
             anomaly.py     (Stage 1: IsolationForest + ECOD ensemble, recall-first)
             suppression.py (Stage 2: cohort-aware suppression, no ML)
pipeline.py  run_detection: enriched -> tripwires -> anomaly -> suppression -> flags
evaluate.py  label join + metrics + ablation table
build.py     CLI entrypoint -> data/processed/detections.parquet
```
