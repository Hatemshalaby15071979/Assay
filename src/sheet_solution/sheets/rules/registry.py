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


RULES: dict[str, Predicate] = {
    "not_blank": _not_blank,
    "is_blank": _is_blank,
    "equals": _equals,
    "numeric_range": _numeric_range,
    "one_of": _one_of,
    "regex": _regex,
    "date_before": _date_before,
    "cross_column": _cross_column,
    "lookup_in": _lookup_in,
    "unique": _unique,
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
