"""Phase B — named rules registry and plain-English migration parity."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import REPO
from sheet_solution.core.errors import ConfigError
from sheet_solution.core.policy.schema import RULE_NAMES
from sheet_solution.sheets import runner, template
from sheet_solution.sheets.rules import registry

FIXTURES = REPO / "tests" / "fixtures"


def _check(rule_text: str, column: str = "v"):
    text = (
        "[CHECK]\ncheck_id = C-1\nwhat_is_this_check_for = t\nwhat_to_look_at = v\n"
        f"expected_value_or_rule = {rule_text}\nwhen_it_fails_say = f\n"
        f"machine_can_check = yes\ncolumn_name = {column}\n"
        "example_that_passes = p\nexample_that_fails = f\n")
    p = Path("/tmp/_rule_check.txt")
    p.write_text(text)
    return template.parse_template(p, "s.xlsx").checks[0]


# --- registry vocabulary ----------------------------------------------------
def test_registry_ids_match_policy_schema():
    assert set(registry.rule_ids()) == set(RULE_NAMES)


def test_unknown_rule_fails_closed():
    with pytest.raises(ConfigError):
        registry.apply("delete_all", "x")


# --- each named rule --------------------------------------------------------
def test_not_blank_and_is_blank():
    assert registry.apply("not_blank", " x ") is True
    assert registry.apply("not_blank", "  ") is False
    assert registry.apply("is_blank", "  ") is True


def test_equals_is_case_insensitive():
    assert registry.apply("equals", " APPROVED ", {"value": "approved"}) is True
    assert registry.apply("equals", "x", {"value": "approved"}) is False


def test_numeric_range_expr_and_params():
    assert registry.apply("numeric_range", "95", {"expr": ">= 60"}) is True
    assert registry.apply("numeric_range", "42", {"expr": ">= 60"}) is False
    assert registry.apply("numeric_range", "95", {"min": 60, "max": 100}) is True
    assert registry.apply("numeric_range", "abc", {"expr": ">= 60"}) is False


def test_one_of_regex_date_before():
    assert registry.apply("one_of", "b", {"values": ["a", "B"]}) is True
    assert registry.apply("regex", "AB-123", {"pattern": r"^[A-Z]{2}-\d+$"}) is True
    assert registry.apply("date_before", "2026-01-01", {"than": "2026-06-01"}) is True
    assert registry.apply("date_before", "not-a-date", {"than": "2026-06-01"}) is False


def test_cross_column_lookup_in_unique():
    row = {"score": "80", "threshold": "60"}
    assert registry.apply("cross_column", "80", {"column": "threshold", "op": ">="}, row) is True
    rows = [{"status": "ok"}, {"status": "bad"}]
    assert registry.apply("lookup_in", "ok", {"column": "status"}, {}, rows) is True
    assert registry.apply("lookup_in", "missing", {"column": "status"}, {}, rows) is False
    rows = [{"id": "A"}, {"id": "A"}, {"id": "B"}]
    assert registry.apply("unique", "B", {"column": "id"}, {}, rows) is True
    assert registry.apply("unique", "A", {"column": "id"}, {}, rows) is False


def test_invalid_regex_fails_closed():
    with pytest.raises(ConfigError):
        registry.apply("regex", "x", {"pattern": "["})


# --- byte-identical migration: legacy plain English -> named rules ----------
@pytest.mark.parametrize("rule_text, values, failed", [
    ("no blank", ["a.png", "b.png"], []),
    ("no blank", ["a.png", ""], ["r2"]),
    ("is blank", ["", ""], []),
    (">= 60", ["95", "42"], ["r2"]),
    ("must equal APPROVED", ["approved", "pending"], ["r2"]),
])
def test_legacy_plain_english_still_runs(rule_text, values, failed):
    check = _check(rule_text, column="v")
    rows = [{"row": "r1", "v": values[0]}, {"row": "r2", "v": values[1]}]
    res = runner.run_machine_check(check, rows)
    assert res.failed_row_ids == failed


def test_legacy_numeric_alias_matches_registry():
    assert runner._numeric_ok("95", ">= 60") is True
    assert runner._numeric_ok("42", ">= 60") is False
