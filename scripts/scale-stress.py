#!/usr/bin/env python3
"""Bounded scale smoke for the two-sheet compare path.

Generates two synthetic CSVs, runs the same deterministic compare used by the
CLI and GUI, and prints elapsed time and peak traced memory. This is a smoke,
not a capacity claim: it documents the practical ceiling on the host that ran
it, on synthetic data only.

Usage:
    PYTHONPATH=src python scripts/scale-stress.py --rows 10000
"""
from __future__ import annotations

import argparse
import csv
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sheet_solution.cli import _load_sheet  # noqa: E402
from sheet_solution.sheets import compare as cmp_mod  # noqa: E402


def _make_csv(
    path: Path,
    rows: int,
    *,
    offset: int = 0,
    bump: bool = False,
    extra: int = 0,
) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["id", "amount", "status"])
        for i in range(rows):
            amount = i * 10 + (1 if bump and i == rows // 2 else 0)
            writer.writerow([f"K{i + offset}", amount, "ok" if i % 3 else "warn"])
        for j in range(extra):
            writer.writerow([f"EXTRA{j}", 0, "new"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=10_000)
    parser.add_argument("--out", default="", help="keep the generated CSVs here")
    args = parser.parse_args()
    if args.rows < 1:
        print("rows must be positive", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="ss-scale-") as tmp:
        base = Path(args.out) if args.out else Path(tmp)
        base.mkdir(parents=True, exist_ok=True)
        a = base / "a.csv"
        b = base / "b.csv"
        _make_csv(a, args.rows)
        _make_csv(b, args.rows, bump=True, extra=1)

        a_rows, _, _ = _load_sheet(a)
        b_rows, _, _ = _load_sheet(b)

        tracemalloc.start()
        started = time.perf_counter()
        result = cmp_mod.compare(a_rows, b_rows, "id", ["amount", "status"])
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

    print(
        f"rows={args.rows} elapsed={elapsed:.3f}s "
        f"peak={peak / (1024 * 1024):.2f}MiB "
        f"matched={result.matched} changed={result.changed} "
        f"only_a={result.only_a} only_b={result.only_b}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
