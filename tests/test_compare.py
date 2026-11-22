"""Assay — two-sheet comparison tests (deterministic + traceable)."""
from __future__ import annotations

from pathlib import Path

import pytest

from sheet_solution.sheets import compare as cmp_mod


def test_compare_all_matched():
    a = [{"id": "1", "name": "Ada", "amt": "100"},
         {"id": "2", "name": "Ben", "amt": "200"}]
    b = [{"id": "1", "name": "Ada", "amt": "100"},
         {"id": "2", "name": "Ben", "amt": "200"}]
    r = cmp_mod.compare(a, b, "id", ["name", "amt"])
    assert r.matched == 2 and r.changed == 0 and r.only_a == 0 and r.only_b == 0


def test_compare_changed_field_named():
    a = [{"id": "1", "name": "Ada", "amt": "100"}]
    b = [{"id": "1", "name": "Ada", "amt": "150"}]
    r = cmp_mod.compare(a, b, "id", ["name", "amt"])
    assert r.changed == 1
    row = r.rows[0]
    assert row.status == "CHANGED" and row.changed_fields == ["amt"]
    # traceability: both sides recorded
    assert row.a_value["amt"] == "100" and row.b_value["amt"] == "150"


def test_compare_only_in_a_and_b():
    a = [{"id": "1"}, {"id": "2"}]
    b = [{"id": "2"}, {"id": "3"}]
    r = cmp_mod.compare(a, b, "id", ["id"])
    assert r.only_a == 1 and r.only_b == 1 and r.matched == 1
    statuses = {row.status for row in r.rows}
    assert {"ONLY-IN-A", "ONLY-IN-B", "MATCHED"} <= statuses


def test_compare_numeric_tolerance():
    a = [{"id": "1", "amt": "100.00"}]
    b = [{"id": "1", "amt": "100.50"}]
    # within 1.0 -> matched
    r = cmp_mod.compare(a, b, "id", ["amt"], tolerance="1.0")
    assert r.matched == 1 and r.changed == 0
    # outside 0.1 -> changed
    r2 = cmp_mod.compare(a, b, "id", ["amt"], tolerance="0.1")
    assert r2.changed == 1 and r2.matched == 0


def test_compare_exact_when_no_tolerance():
    a = [{"id": "1", "amt": "100"}]
    b = [{"id": "1", "amt": "100.0"}]  # different string, exact -> changed
    r = cmp_mod.compare(a, b, "id", ["amt"])
    assert r.changed == 1


def test_compare_is_deterministic():
    a = [{"id": "3"}, {"id": "1"}, {"id": "2"}]
    b = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    r1 = cmp_mod.compare(a, b, "id", ["id"]).csv()
    r2 = cmp_mod.compare(list(reversed(a)), b, "id", ["id"]).csv()
    assert r1 == r2  # output does not depend on input row order


def test_compare_csv_neutralises_formula_keys():
    a = [{"id": "=A1"}, {"id": "x"}]
    b = [{"id": "x"}]
    r = cmp_mod.compare(a, b, "id", ["id"])
    text = r.csv()
    # the only-in-A key '=A1' must be quoted so it is inert in a spreadsheet.
    assert '"=A1"' in text


def test_compare_end_to_end_cli(tmp_path):
    from sheet_solution.cli import cmd_compare
    import argparse
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("id,amount\n1,100\n2,200\n")
    b.write_text("id,amount\n1,100\n2,250\n3,5\n")
    args = argparse.Namespace(
        sheet_a=str(a), sheet_b=str(b), key="id",
        fields="amount", tolerance="", out=str(tmp_path / "cmp"))
    assert cmd_compare(args) == 0
    report = (tmp_path / "cmp" / "compare-report.csv").read_text()
    log = (tmp_path / "cmp" / "compare-log.jsonl").read_text()
    assert "1 matched" not in report  # report has rows, summary printed separately
    import json
    data = json.loads(log)
    assert data["totals"]["matched"] == 1      # id 1 unchanged
    assert data["totals"]["changed"] == 1      # id 2 amount 200 -> 250
    assert data["totals"]["only_b"] == 1       # id 3 only in B
