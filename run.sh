#!/usr/bin/env bash
# Assay — one-click local run for non-technical users.
# Usage: ./run.sh <sheet.xlsx-or-.csv> <check-template.txt> [out_dir]
#
# If you do not have the tool installed, this script installs it into a
# local virtualenv (offline wheels if vendored, else from the pinned set)
# and runs the audit. No cloud, no network needed at run time.
set -euo pipefail

SHEET="${1:?usage: ./run.sh <sheet> <template> [out]}"
TEMPLATE="${2:?usage: ./run.sh <sheet> <template> [out]}"
OUT="${3:-out/report}"

cd "$(dirname "$0")"
# Where does the tool itself come from?
if ls ./*.whl >/dev/null 2>&1; then BUNDLE=1; else BUNDLE=0; fi

# Prefer an installed/venv python; build one if missing.
if [ -d ".venv" ]; then
  PY=".venv/bin/python"
else
  python3 -m venv .venv
  PY=".venv/bin/python"
  "$PY" -m pip install --quiet --upgrade pip
  # Deps: hash-locked offline wheels in a bundle; otherwise the plain pinned
  # set (hash locks are for the 3.11 Docker image, so don't enforce them on a
  # foreign host python — install the same versions unpinned).
  if [ "$BUNDLE" = 1 ] && [ -d "vendor/wheels" ]; then
    "$PY" -m pip install --no-index --find-links vendor/wheels fpdf2 openpyxl || true
  else
    "$PY" -m pip install --quiet "fpdf2==2.8.8" "openpyxl==3.1.5" || \
      "$PY" -m pip install --quiet fpdf2 openpyxl
  fi
  # The tool itself: the bundled wheel, or the source tree.
  if [ "$BUNDLE" = 1 ]; then
    "$PY" -m pip install --no-index --find-links vendor/wheels ./*.whl
  else
    # source checkout: run straight from src (no install needed).
    export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"
  fi
fi

if [ -n "${PYTHONPATH:-}" ] && "$PY" -c "import sheet_solution" 2>/dev/null; then
  :
elif "$PY" -c "import sheet_solution" 2>/dev/null; then
  :
else
  export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"
fi

"$PY" -m sheet_solution run --sheet "$SHEET" --template "$TEMPLATE" --out "$OUT"

echo
echo "Report pack written to: $OUT"
echo "  check-results.csv   (the report)   audit-log.jsonl   (the log)"
echo "Open $OUT/media/ for any images a check needed a human to review."
