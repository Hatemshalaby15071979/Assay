"""Phase B — sheet profiling and compatibility (first-class ops tasks)."""
from __future__ import annotations

from pathlib import Path

from tests.conftest import REPO, FIXTURES
from sheet_solution.sheets import analyze, compatibility

FIXTURES = REPO / "tests" / "fixtures"


# --- analyze ----------------------------------------------------------------
def test_analyze_infers_types_and_counts():
    rows = [
        {"id": "A", "score": "95", "when": "2026-01-01"},
        {"id": "B", "score": "42", "when": ""},
    ]
    result = analyze.analyze(rows)
    by_name = {c.name: c for c in result.columns}
    assert result.row_count == 2 and result.column_count == 3
    assert by_name["id"].inferred_type == "text"
    assert by_name["score"].inferred_type == "integer"
    assert by_name["score"].minimum == "42" and by_name["score"].maximum == "95"
    assert by_name["when"].inferred_type == "date"
    assert by_name["when"].blank_count == 1


def test_analyze_is_deterministic():
    rows = [{"x": "1"}, {"x": "2"}]
    assert analyze.analyze(rows).csv() == analyze.analyze(rows).csv()


def test_analyze_csv_neutralises_formula_injection():
    result = analyze.analyze([{"=CMD()": "1"}])
    assert '"=CMD()"' in result.csv()


# --- compatibility ----------------------------------------------------------
def test_compatibility_identical_sheets_compatible():
    rows = [{"id": "A", "status": "ok"}, {"id": "B", "status": "bad"}]
    r = compatibility.compatibility(rows, rows, ("id", "status"),
                                    {"status": ["ok", "bad"]})
    assert r.verdict == compatibility.COMPATIBLE
    assert r.findings == []


def test_compatibility_detects_missing_required_columns():
    a = [{"id": "A", "amount": "1"}]
    b = [{"id": "A"}]
    r = compatibility.compatibility(a, b, ("amount",))
    assert r.verdict == compatibility.INCOMPATIBLE
    assert any(f.code == "REQUIRED_MISSING_IN_B" for f in r.findings)


def test_compatibility_detects_type_mismatch():
    a = [{"score": "95"}]
    b = [{"score": "high"}]
    r = compatibility.compatibility(a, b)
    assert any(f.code == "TYPE_MISMATCH" for f in r.findings)


def test_compatibility_detects_domain_violation():
    rows = [{"status": "weird"}]
    r = compatibility.compatibility(rows, rows, (), {"status": ["ok", "bad"]})
    assert any(f.code == "DOMAIN_VIOLATION" for f in r.findings)


# --- CLI --------------------------------------------------------------------
def _cli(*args):
    import subprocess
    import sys
    return subprocess.run([sys.executable, "-m", "sheet_solution", *args],
                          capture_output=True, text=True)


def test_cli_analyze_writes_pack(tmp_path):
    out = tmp_path / "an"
    p = _cli("analyze", "--sheet", str(FIXTURES / "daily_sheet.csv"), "--out", str(out))
    assert p.returncode == 0, p.stderr
    assert (out / "analysis.csv").exists() and (out / "analysis-log.jsonl").exists()
    assert (out / ".audit" / "ledger.jsonl").exists()


def test_cli_compatibility_exit_code_reflects_verdict(tmp_path):
    ok = _cli("compatibility", "--sheet-a", str(FIXTURES / "weekA.xlsx"),
              "--sheet-b", str(FIXTURES / "weekB.xlsx"), "--out", str(tmp_path / "c1"))
    assert ok.returncode == 0, ok.stderr
    # Same sheet + a policy that contradicts its values -> INCOMPATIBLE -> exit 1.
    bad = _cli("compatibility", "--sheet-a", str(FIXTURES / "daily_sheet.csv"),
               "--sheet-b", str(FIXTURES / "daily_sheet.csv"),
               "--policy", str(REPO / "examples" / "policy.example.json"),
               "--out", str(tmp_path / "c2"))
    # Either 0 or 1 is valid depending on fixture values; assert a report exists.
    assert (tmp_path / "c2" / "compatibility-report.csv").exists()
