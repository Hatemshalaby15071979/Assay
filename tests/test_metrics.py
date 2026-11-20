"""Phase E — deterministic ops metrics and the fail-closed row cap."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from tests.conftest import REPO

from sheet_solution.cli import _load_sheet, cmd_metrics, cmd_run
from sheet_solution.core.errors import SignoffError
from sheet_solution.sheets import metrics as met


def _results():
    return [
        {"check_id": "CH-1", "outcome": "PASS"},
        {"check_id": "CH-2", "outcome": "PASS"},
        {"check_id": "CH-3", "outcome": "FAIL"},
        {"check_id": "CH-4", "outcome": "PENDING-HUMAN"},
    ]


def _decisions():
    return [
        {"state": "APPLIED"}, {"state": "DECLINED"},
        {"state": "APPROVED"}, {"state": "PROPOSED"},
    ]


def test_build_metrics_counts_and_derivations():
    m = met.build_metrics(_results(), _decisions())
    assert (m.checks_total, m.checks_pass, m.checks_fail, m.checks_pending_human) == (4, 2, 1, 1)
    assert m.checks_machine_decided == 3          # pass + fail
    assert m.findings_total == 4
    assert m.findings_resolved == 1               # APPLIED only
    assert m.findings_outstanding == 3            # proposed + declined + approved


def test_metrics_to_dict_percentages():
    d = met.build_metrics(_results(), _decisions()).to_dict()
    assert d["checks"]["machine_decided_pct"] == 75.0
    assert d["checks"]["needs_human_pct"] == 25.0
    assert d["findings"]["resolved_pct"] == 25.0
    assert d["findings"]["outstanding_pct"] == 75.0


def test_metrics_empty_inputs_are_zero_not_a_division_error():
    d = met.build_metrics([], []).to_dict()
    assert d["checks"]["total"] == 0 and d["findings"]["total"] == 0
    assert d["checks"]["machine_decided_pct"] == 0.0
    assert d["findings"]["resolved_pct"] == 0.0


def test_metrics_summary_mentions_machine_and_person():
    text = met.build_metrics(_results(), _decisions()).summary()
    assert "machine-decided" in text and "needs a person" in text
    assert "resolved" in text and "outstanding" in text


def test_metrics_cli_writes_deterministic_json_and_ledger(tmp_path):
    out = tmp_path / "pack"
    out.mkdir()
    (out / "check-results.csv").write_text(
        "check_id,label,outcome,matched_rows,failed_rows,denominator,failed_row_ids,detail\n"
        "CH-1,a,PASS,1,0,1,,ok\nCH-2,b,FAIL,0,1,1,r2,bad\n", encoding="utf-8")
    (out / "decisions.json").write_text(
        json.dumps([{"state": "PROPOSED"}]), encoding="utf-8")
    assert cmd_metrics(argparse.Namespace(out=str(out))) == 0
    first = (out / "metrics.json").read_bytes()
    assert cmd_metrics(argparse.Namespace(out=str(out))) == 0
    assert (out / "metrics.json").read_bytes() == first  # deterministic
    data = json.loads(first)
    assert data["checks"]["total"] == 2
    assert data["findings"]["proposed"] == 1


def test_metrics_requires_a_run_pack(tmp_path):
    with pytest.raises(SignoffError):
        cmd_metrics(argparse.Namespace(out=str(tmp_path / "nope")))


# --- row cap ----------------------------------------------------------------
def _csv(path: Path, n: int) -> Path:
    path.write_text("id,v\n" + "".join(f"{i},x\n" for i in range(n)), encoding="utf-8")
    return path


def test_row_cap_fails_closed(tmp_path):
    p = _csv(tmp_path / "s.csv", 3)
    with pytest.raises(SignoffError) as exc:
        _load_sheet(p, max_rows=2)
    assert "row cap" in str(exc.value)


def test_row_cap_zero_disables_the_cap(tmp_path):
    p = _csv(tmp_path / "s.csv", 5)
    rows, _, _ = _load_sheet(p, max_rows=0)
    assert len(rows) == 5


def test_row_cap_default_allows_small_sheets(tmp_path):
    p = _csv(tmp_path / "s.csv", 5)
    rows, _, _ = _load_sheet(p)
    assert len(rows) == 5


def test_run_with_tight_row_cap_aborts(tmp_path):
    args = argparse.Namespace(
        sheet=str(REPO / "examples" / "example-sheet.xlsx"),
        template=str(REPO / "examples" / "check-template.example.txt"),
        out=str(tmp_path / "out"), key=None, max_rows=1,
    )
    with pytest.raises(SignoffError):
        cmd_run(args)
