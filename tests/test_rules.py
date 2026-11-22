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


# --- new rules (Phase B expansion) -------------------------------------------
def test_date_within_range():
    # direction=both (default): within N days before or after reference
    assert registry.apply("date_within_range", "2026-11-25", {"days": 10, "reference": "2026-11-20"}) is True
    assert registry.apply("date_within_range", "2026-11-05", {"days": 10, "reference": "2026-11-20"}) is False
    # direction=before: candidate must be before reference but within N days
    assert registry.apply("date_within_range", "2026-11-15", {"days": 10, "reference": "2026-11-20", "direction": "before"}) is True
    assert registry.apply("date_within_range", "2026-11-25", {"days": 10, "reference": "2026-11-20", "direction": "before"}) is False
    # direction=after: candidate must be after reference but within N days
    assert registry.apply("date_within_range", "2026-11-25", {"days": 10, "reference": "2026-11-20", "direction": "after"}) is True
    assert registry.apply("date_within_range", "2026-11-15", {"days": 10, "reference": "2026-11-20", "direction": "after"}) is False
    # invalid date
    assert registry.apply("date_within_range", "not-a-date", {"days": 10}) is False


def test_date_before_today():
    # uses actual today; just test logic with a future date
    from datetime import date, timedelta
    future = (date.today() + timedelta(days=10)).isoformat()
    assert registry.apply("date_before_today", future) is True
    past = (date.today() - timedelta(days=10)).isoformat()
    assert registry.apply("date_before_today", past) is False
    assert registry.apply("date_before_today", "not-a-date") is False


def test_email_format():
    assert registry.apply("email_format", "user@example.com") is True
    assert registry.apply("email_format", "user.name+tag@sub.example.co.uk") is True
    assert registry.apply("email_format", "invalid") is False
    assert registry.apply("email_format", "@example.com") is False
    assert registry.apply("email_format", "user@") is False


def test_phone_format():
    assert registry.apply("phone_format", "+1234567890") is True
    assert registry.apply("phone_format", "+442071234567") is True
    assert registry.apply("phone_format", "1234567890") is False  # missing +
    assert registry.apply("phone_format", "+") is False


def test_iban_format():
    # Valid IBAN (GB29 NWBK 6016 1331 9268 19)
    assert registry.apply("iban_format", "GB29NWBK60161331926819") is True
    assert registry.apply("iban_format", "GB29 NWBK 6016 1331 9268 19") is True  # with spaces
    # Invalid checksum
    assert registry.apply("iban_format", "GB29NWBK60161331926818") is False
    # Invalid format
    assert registry.apply("iban_format", "INVALID") is False


def test_starts_with_ends_with():
    assert registry.apply("starts_with", "INV-123", {"prefix": "INV-"}) is True
    assert registry.apply("starts_with", "INV-123", {"prefix": "CR-"}) is False
    assert registry.apply("ends_with", "report.pdf", {"suffix": ".pdf"}) is True
    assert registry.apply("ends_with", "report.doc", {"suffix": ".pdf"}) is False


def test_contains_any_all():
    assert registry.apply("contains_any", "urgent review needed", {"values": ["urgent", "critical"]}) is True
    assert registry.apply("contains_any", "needs review", {"values": ["urgent", "critical"]}) is False
    assert registry.apply("contains_all", "urgent critical review", {"values": ["urgent", "critical"]}) is True
    assert registry.apply("contains_all", "urgent review", {"values": ["urgent", "critical"]}) is False


def test_cross_sheet_lookup():
    other_sheet = [{"customer_id": "C001"}, {"customer_id": "C002"}]
    assert registry.apply("cross_sheet_lookup", "C001", {"column": "customer_id", "sheet_rows": other_sheet}) is True
    assert registry.apply("cross_sheet_lookup", "C999", {"column": "customer_id", "sheet_rows": other_sheet}) is False
    # missing params
    assert registry.apply("cross_sheet_lookup", "C001", {}) is False


def test_unique_across_sheets():
    rows = [{"id": "A"}, {"id": "B"}]
    other = [{"id": "C"}, {"id": "D"}]
    assert registry.apply("unique_across_sheets", "A", {"column": "id", "other_sheets": [other]}, {}, rows) is True
    # other_sheets is a list of sheets (each sheet is a list of rows)
    assert registry.apply("unique_across_sheets", "A", {"column": "id", "other_sheets": [[{"id": "A"}]]}, {}, rows) is False


def test_checksum_valid():
    # IBAN checksum
    assert registry.apply("checksum_valid", "GB29NWBK60161331926819", {"algorithm": "iban"}) is True
    assert registry.apply("checksum_valid", "GB29NWBK60161331926818", {"algorithm": "iban"}) is False
    # Luhn checksum (valid Visa test number)
    assert registry.apply("checksum_valid", "4532015112830366", {"algorithm": "luhn"}) is True
    assert registry.apply("checksum_valid", "4532015112830367", {"algorithm": "luhn"}) is False
    # MOD97 (numeric only - valid MOD97 number that gives remainder 0)
    assert registry.apply("checksum_valid", "97", {"algorithm": "mod97"}) is True
    assert registry.apply("checksum_valid", "194", {"algorithm": "mod97"}) is True
    assert registry.apply("checksum_valid", "100", {"algorithm": "mod97"}) is False
    # Unknown algorithm
    assert registry.apply("checksum_valid", "x", {"algorithm": "unknown"}) is False
