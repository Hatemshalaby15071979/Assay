#!/usr/bin/env bash
# Sheet Solution — recipient-side install + run (offline, no cloud).
#
# Usage (inside the extracted bundle):
#   ./install.sh            # build a local venv + install offline
#   ./run.sh <sheet> <template> [out]
#
# No network is required when the bundle's vendor/wheels set is present.
set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  echo ">> creating local virtualenv (no cloud)"
  python3 -m venv .venv
  "$PY" -m pip install --quiet --upgrade pip

  if [ -d "vendor/wheels" ] && ls *.whl >/dev/null 2>&1; then
    echo ">> installing tool + offline deps from vendored wheels (no network)"
    # Deps from the vendored wheel set (host-platform). Best-effort.
    "$PY" -m pip install --no-index --find-links vendor/wheels fpdf2 openpyxl || true
    # Optional GUI extra (flask) — best-effort, so the GUI works offline too.
    "$PY" -m pip install --no-index --find-links vendor/wheels flask 2>/dev/null || true
    # The tool itself, from the bundled wheel, offline.
    "$PY" -m pip install --no-index --find-links vendor/wheels ./*.whl
  else
    echo ">> no vendored wheels; installing pinned set (network)"
    "$PY" -m pip install fpdf2 openpyxl
    [ -f ./*.whl ] && "$PY" -m pip install ./*.whl
  fi
fi

echo ">> ready. Run: ./run.sh <sheet> <template> [out]"
