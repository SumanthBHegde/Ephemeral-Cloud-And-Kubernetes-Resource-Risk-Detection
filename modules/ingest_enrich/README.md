# Stage 1 — Ingest & Enrich

Reads the three authentic Stage-Zero sources, normalizes them into **one unified event
schema**, cleans the data, assigns each event a **behavioral cohort** (§6), and computes the
per-event **context features** (§5) the two-stage detector consumes. This is where the
project's central thesis becomes code: at the raw-event level a malicious burst and a benign
one are identical, so the separating signal must be engineered here, in context.

## Run

```bash
pip install -r requirements.txt                       # adds pandas, pyarrow
python -m modules.data_simulation.generator.build     # produce data/raw/ first
python -m modules.ingest_enrich.build                 # -> data/processed/events_enriched.parquet
python -m pytest tests/test_stage1.py -q
```

## What it produces

`data/processed/events_enriched.parquet` — one row per source record, in the unified schema
(`modules/ingest_enrich/normalize/__init__.py :: UNIFIED_FIELDS`) plus `cohort` and these
§5 feature columns:

| Feature | Meaning |
|---|---|
| `burst_rate` | same-action events by the same principal in a trailing 5-min window |
| `principal_novelty` / `is_novel_principal` | prior appearances of this principal before this event |
| `tag_completeness` | fraction of the cohort's `expected_tags` present (EC2 tags + K8s labels) |
| `privilege_level` | 0–3 from privileged / hostNetwork / broad RBAC / spot+public |
| `public_exposure_flag` | exposure weighted by resource type (LB=0.3 normal, NodePort 0.0.0.0/0=1.0 risky) |
| `exposure_window_s` | observed pod create→delete lifetime, or session TTL |
| `off_hours_flag` | event outside the assigned cohort's active hours |
| `cohort_deviation` | z-distance from the cohort's **empirical** feature centroid (key contextual feature) |

Output is **Parquet only** (design doc §16) — it carries nested/list columns (`tags`,
`labels`, `raw`) that CSV cannot represent without loss.

## Two consumption modes

- **Batch** (`pipeline.build_enriched`) — reads the three JSONL files directly, the
  deterministic path detection reads. Default.
- **Live** (`pipeline.enrich_stream`) — wraps the Stage-Zero replay streamer
  (`replay_events()`) to normalize + cohort-assign events as they "arrive", for the
  dashboard's live tile. Windowed features stay a batch concern (consistent with the
  score-after-clustering ordering).

## Cohort assignment (rule-assisted, deterministic)

`enrich/cohorts.py` maps each principal to `ci_runner | hpa_autoscaler | human_dev |
scheduled_lambda` using authentic identity fields in priority order: K8s service-account
subject → CloudTrail role / service `invokedBy` → IdP email prefix → source-IP CIDR.
Cohort *names*, active hours, and expected tags come from
`modules/data_simulation/config/simulation.yaml` (single source of truth); the matching
rules are grounded in the fields that actually appear in the rendered records.

**Unmatched → `unknown`, by design.** On the current seed this is 629 rows, and *every one*
is the `identity_anomaly` attack (`contractor-*` federated users assuming `data-access-role`
from public IPs — all `is_risky=1`). A principal that fits no known cohort is itself a
signal; forcing it into the nearest benign cohort would mask exactly what the pipeline must
catch. Cohort accuracy on the 9,228 recognizable principals is **100%** against ground truth.

## Labels stay separate

The enriched table carries `record_id` (CloudTrail `eventID` / K8s `auditID` / IdP `uuid`)
so evaluation can join `data/raw/labels.jsonl` **1:1**, but labels are never read into the
runtime feature table — keeping the eval honest.

## Layout

```
normalize/   cloudtrail.py / k8s_audit.py / idp_session.py  (record -> unified row)
             dispatch.py   (_source -> parser)   __init__.py  (UNIFIED_FIELDS)
enrich/      cohorts.py    (rule-assisted assignment)
             features.py   (§5 features + empirical cohort deviation)
pipeline.py  batch build + live stream wrapper
build.py     CLI entrypoint
```
