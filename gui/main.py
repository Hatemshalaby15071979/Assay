#!/usr/bin/env python3
"""Assay GUI — launcher.

Thin entry point so `python gui/main.py` (from the repo root or a bundle)
opens the offline drag-and-drop + visual-cards app. The real package is
`sheet_solution.gui`; this file just hands off to it.

    pip install "assay[gui]"
    python -m sheet_solution.gui.main        # or: python gui/main.py
    # -> http://127.0.0.1:8477  (local only, no cloud)
"""
import sys
from pathlib import Path

# Make the source tree importable whether this runs from a repo checkout
# (PYTHONPATH unset) or an installed package.
_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sheet_solution.gui.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
