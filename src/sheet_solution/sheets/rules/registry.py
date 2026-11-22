"""Deterministic named rules with stable ids.

Every rule is ``fn(value: str, params: dict, row: dict, rows: list[dict]) -> bool``:
pure, offline, no model, no wall clock. The four legacy plain-English
predicates (not-blank, is-blank, equals, numeric) are expressed here as named
rules and reused by ``runner._predicate_for`` with byte-identical behaviour;
the extra rules back policy checks in later phases.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Callable

from sheet_solution.core.errors import ConfigError
from sheet_solution.core.policy.schema import RULE_NAMES

Predicate = Callable[[str, dict, dict, list[dict]], bool]

_NUMERIC_RE = re.compile(r"(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+[1-9]\d{1,14}$")  # E.164 (requires leading +)
_IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{1,30}$")


def numeric_ok(value: str, rule: str) -> bool:
    """Legacy numeric predicate, kept as the single implementation."""
    m = _NUMERIC_RE.search(rule)
    if not m:
        return False
    try:
        num = float(value)
    except (ValueError, TypeError):
        return False
    op, target = m.group(1), float(m.group(2))
    return {">=": num >= target, "<=": num <= target,
            ">": num > target, "<": num < target}[op]


def _not_blank(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    return value.strip() != ""


def _is_blank(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    return value.strip() == ""


def _equals(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    expected = str(params.get("value", "")).strip().lower()
    return value.strip().lower() == expected


def _numeric_range(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    rule = str(params.get("expr", ""))
    if rule:
        return numeric_ok(value, rule)
    lo = params.get("min")
    hi = params.get("max")
    try:
        num = float(value)
    except (ValueError, TypeError):
        return False
    if lo is not None and num < float(lo):
        return False
    if hi is not None and num > float(hi):
        return False
    return True


def _one_of(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    choices = [str(v) for v in params.get("values", [])]
    return value.strip().lower() in {c.lower() for c in choices}


def _regex(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    pattern = str(params.get("pattern", ""))
    try:
        return re.search(pattern, value) is not None
    except re.error as exc:
        raise ConfigError(f"invalid regex pattern {pattern!r}: {exc}") from exc


def _date_before(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    try:
        candidate = dt.date.fromisoformat(value.strip())
        limit = dt.date.fromisoformat(str(params["than"]).strip())
    except (ValueError, KeyError):
        return False
    return candidate < limit


def _cross_column(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    other_col = str(params.get("column", ""))
    op = str(params.get("op", "equals"))
    other = str(row.get(other_col, ""))
    if op == "equals":
        return value.strip() == other.strip()
    try:
        left, right = float(value), float(other)
    except (ValueError, TypeError):
        return False
    return {">=": left >= right, "<=": left <= right,
            ">": left > right, "<": left < right}.get(op, False)


def _lookup_in(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    column = str(params.get("column", ""))
    allowed = {str(r.get(column, "")).strip() for r in rows if column in r}
    return value.strip() in allowed


def _unique(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    if not value.strip():
        return False
    column = str(params.get("column", ""))
    if not column:
        return True
    return sum(1 for r in rows if str(r.get(column, "")).strip() == value.strip()) == 1


def _date_within_range(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    """Check if date is within N days of a reference date (default: today).
    Params: days (int), reference (ISO date string or 'today'), direction ('before'|'after'|'both')
    """
    try:
        candidate = dt.date.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return False
    days = int(params.get("days", 0))
    direction = str(params.get("direction", "both")).lower()
    ref_str = str(params.get("reference", "today")).strip().lower()
    if ref_str == "today":
        reference = dt.date.today()
    else:
        try:
            reference = dt.date.fromisoformat(ref_str)
        except ValueError:
            return False
    delta = (candidate - reference).days
    if direction == "before":
        return -days <= delta <= 0
    if direction == "after":
        return 0 <= delta <= days
    return abs(delta) <= days


def _date_before_today(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    """Check if date is not in the past (>= today)."""
    try:
        candidate = dt.date.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return False
    return candidate >= dt.date.today()


def _email_format(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    return _EMAIL_RE.match(value.strip()) is not None


def _phone_format(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    return _PHONE_RE.match(value.strip()) is not None


def _iban_format(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    v = value.strip().upper().replace(" ", "")
    if not _IBAN_RE.match(v):
        return False
    # IBAN checksum validation (MOD-97-10)
    rearranged = v[4:] + v[:4]
    numeric = "".join(str(int(ch, 36)) for ch in rearranged)
    return int(numeric) % 97 == 1


def _starts_with(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    prefix = str(params.get("prefix", ""))
    return value.strip().startswith(prefix)


def _ends_with(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    suffix = str(params.get("suffix", ""))
    return value.strip().endswith(suffix)


def _contains_any(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    choices = [str(v).strip().lower() for v in params.get("values", [])]
    val = value.strip().lower()
    return any(c in val for c in choices)


def _contains_all(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    choices = [str(v).strip().lower() for v in params.get("values", [])]
    val = value.strip().lower()
    return all(c in val for c in choices)


def _cross_sheet_lookup(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    """Look up value in another sheet loaded via params['sheet_rows'] (list[dict])."""
    column = str(params.get("column", ""))
    sheet_rows = params.get("sheet_rows", [])
    if not column or not sheet_rows:
        return False
    allowed = {str(r.get(column, "")).strip() for r in sheet_rows if column in r}
    return value.strip() in allowed


def _unique_across_sheets(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    """Check uniqueness across current sheet + additional sheets in params['other_sheets']."""
    if not value.strip():
        return False
    column = str(params.get("column", ""))
    if not column:
        return True
    count = sum(1 for r in rows if str(r.get(column, "")).strip() == value.strip())
    for other in params.get("other_sheets", []):
        count += sum(1 for r in other if str(r.get(column, "")).strip() == value.strip())
    return count == 1


def _checksum_valid(value: str, params: dict, row: dict, rows: list[dict]) -> bool:
    """Generic checksum: params['algorithm'] in ('iban', 'luhn', 'mod97')."""
    algo = str(params.get("algorithm", "")).lower()
    v = value.strip()
    if algo == "iban":
        v = v.upper().replace(" ", "")
        if not _IBAN_RE.match(v):
            return False
        rearranged = v[4:] + v[:4]
        numeric = "".join(str(int(ch, 36)) for ch in rearranged)
        return int(numeric) % 97 == 1
    if algo == "luhn":
        digits = [int(ch) for ch in v if ch.isdigit()]
        if not digits:
            return False
        total = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10 == 0
    if algo == "mod97":
        # MOD-97: treat the string as a large integer (base-36 for alphanumeric)
        # but only if it's all digits or valid IBAN-like format
        try:
            # Try as pure numeric first
            numeric = "".join(ch for ch in v if ch.isdigit())
            if numeric:
                return int(numeric) % 97 == 0
            # Fallback: alphanumeric base-36
            numeric = "".join(str(int(ch, 36)) for ch in v.upper() if ch.isalnum())
            return int(numeric) % 97 == 0
        except (ValueError, OverflowError):
            return False
    return False


RULES: dict[str, Predicate] = {
    "not_blank": _not_blank,
    "is_blank": _is_blank,
    "equals": _equals,
    "numeric_range": _numeric_range,
    "one_of": _one_of,
    "regex": _regex,
    "date_before": _date_before,
    "date_within_range": _date_within_range,
    "date_before_today": _date_before_today,
    "cross_column": _cross_column,
    "lookup_in": _lookup_in,
    "unique": _unique,
    "unique_across_sheets": _unique_across_sheets,
    "email_format": _email_format,
    "phone_format": _phone_format,
    "iban_format": _iban_format,
    "starts_with": _starts_with,
    "ends_with": _ends_with,
    "contains_any": _contains_any,
    "contains_all": _contains_all,
    "cross_sheet_lookup": _cross_sheet_lookup,
    "checksum_valid": _checksum_valid,
}


def rule_ids() -> tuple[str, ...]:
    return tuple(sorted(RULES))


def apply(
    rule_id: str,
    value: str,
    params: dict | None = None,
    row: dict | None = None,
    rows: list[dict] | None = None,
) -> bool:
    """Apply a named rule; unknown ids fail closed."""
    fn = RULES.get(rule_id)
    if fn is None:
        raise ConfigError(
            f"unknown rule {rule_id!r}; known rules: {', '.join(rule_ids())}")
    return fn(str(value), params or {}, row or {}, rows or [])


# Fail-closed vocabulary check: the registry and the policy schema must agree
# exactly, so a rule can never exist in one place but not the other.
_registry_ids = frozenset(RULES)
_schema_ids = frozenset(RULE_NAMES)
if _registry_ids != _schema_ids:
    raise ConfigError(
        "rules registry and policy schema disagree on rule ids "
        f"(registry-only={sorted(_registry_ids - _schema_ids)}, "
        f"schema-only={sorted(_schema_ids - _registry_ids)})")
