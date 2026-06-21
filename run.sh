#!/usr/bin/env bash
#
# run.sh — one-shot setup + full pipeline + dashboard for
# Ephemeral Cloud & Kubernetes Resource Risk Detection.
#
# Installs Python + npm dependencies, runs all six pipeline stages from scratch
# (deterministic, seed 1337), exports the dashboard JSON, then starts the React
# dev server at http://localhost:5173/app.
#
# Usage (from repo root, in Git Bash or WSL):
#   ./run.sh                 # full run, then launch the dashboard
#   SKIP_INSTALL=1 ./run.sh  # skip dependency install (deps already present)
#   SKIP_PIPELINE=1 ./run.sh # skip the pipeline, just (install +) launch dashboard
#
set -euo pipefail

# Resolve to the script's own directory so it works from anywhere.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- pick a Python launcher -------------------------------------------------
# On Windows the interpreter is usually `python`; fall back to `py -3`.
if command -v python >/dev/null 2>&1; then
  PYTHON="python"
elif command -v py >/dev/null 2>&1; then
  PYTHON="py -3"
else
  echo "ERROR: no Python interpreter found on PATH (need python or py)." >&2
  exit 1
fi
echo "==> Using Python: $($PYTHON --version 2>&1)"

# ---------------------------------------------------------------------------
# 1. Install dependencies
# ---------------------------------------------------------------------------
if [[ "${SKIP_INSTALL:-0}" != "1" ]]; then
  echo "==> Installing Python dependencies (requirements.txt)"
  $PYTHON -m pip install -r requirements.txt

  echo "==> Installing frontend dependencies (npm install)"
  ( cd modules/dashboard/frontend && npm install )
else
  echo "==> SKIP_INSTALL=1 — skipping dependency install"
fi

# ---------------------------------------------------------------------------
# 2. Full pipeline (deterministic, seed 1337)
# ---------------------------------------------------------------------------
if [[ "${SKIP_PIPELINE:-0}" != "1" ]]; then
  echo "==> [1/7] Generating simulated logs        -> data/raw/"
  $PYTHON -m modules.data_simulation.generator.build

  echo "==> [2/7] Ingest + enrich                  -> events_enriched.parquet"
  $PYTHON -m modules.ingest_enrich.build

  echo "==> [3/7] Detection (tripwires + ensemble) -> detections.parquet"
  $PYTHON -m modules.detection.build

  echo "==> [4/7] Graph correlation                -> incidents.parquet"
  $PYTHON -m modules.correlation.build

  echo "==> [5/7] Risk fusion (incident scoring)   -> incidents_scored.parquet"
  $PYTHON -m modules.risk_fusion.build

  echo "==> [6/7] LLM triage (offline, --no-llm)   -> incidents_triaged.parquet"
  $PYTHON -m modules.llm_triage.build --no-llm

  echo "==> [7/7] Export dashboard JSON            -> frontend/public/data/*.json"
  $PYTHON -m modules.dashboard.build
else
  echo "==> SKIP_PIPELINE=1 — skipping pipeline, using committed data JSON"
fi

# ---------------------------------------------------------------------------
# 3. Launch the dashboard
# ---------------------------------------------------------------------------
echo "==> Starting the dashboard at http://localhost:5173/app  (Ctrl+C to stop)"
cd modules/dashboard/frontend
exec npm run dev
