#!/usr/bin/env bash
# Sheet Solution — one-click local run for non-technical users.
# Usage: ./run.sh <sheet.xlsx-or-.csv> <check-template.txt> [out_dir]
#
# If you do not have the tool installed, this script installs it into a
# local virtualenv (offline wheels if vendored, else from the pinned set)
# and runs the audit. No cloud, no network needed at run time.
set -euo pipefail

SHEET="${1:?usage: ./run.sh <sheet> <template> [out]}"
TEMPLATE="${2:?usage: ./run.sh <sheet> <template> [out]}"
OUT="${3:-out/report}"

# Prefer an installed/venv python; fall back to a fresh venv.
if [ -d ".venv" ]; then
  PY=".venv/bin/python"
else
  python3 -m venv .venv
  PY=".venv/bin/python"
  "$PY" -m pip install --quiet --upgrade pip
  # Offline: install from the vendored wheels if present, else pinned set.
  if [ -d "vendor/wheels" ]; then
    "$PY" -m pip install --no-index --find-links vendor/wheels \
        --require-hashes -r requirements.lock
  else
    "$PY" -m pip install --quiet -r requirements.lock
  fi
fi

cd "$(dirname "$0")"
# Prefer the installed package (wheel in the bundle venv); fall back to a
# source checkout (PYTHONPATH=src) if running from a repo instead.
if "$PY" -c "import sheet_solution" 2>/dev/null; then
  "$PY" -m sheet_solution run --sheet "$SHEET" --template "$TEMPLATE" --out "$OUT"
else
  PYTHONPATH=src "$PY" -m sheet_solution run --sheet "$SHEET" --template "$TEMPLATE" --out "$OUT"
fi

echo
echo "Report pack written to: $OUT"
echo "  check-results.csv   (the report)   audit-log.jsonl   (the log)"
echo "Open $OUT/media/ for any images a check needed a human to review."
