#!/usr/bin/env bash
# Sheet Solution — open the drag-and-drop + visual-cards GUI.
#
#   ./gui.sh              # uses ./.venv if present, else creates it (with [gui])
#   ./gui.sh --port 9000  # pick a different port
#
# Then open http://127.0.0.1:8477 (or your chosen port) in a browser.
# Everything is local — no cloud, no data leaves the machine.
set -euo pipefail
cd "$(dirname "$0")"

if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  python3 -m venv .venv
  PY=".venv/bin/python"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -e ".[xlsx,gui]"
fi

exec "$PY" gui/main.py "$@"
