"""Assay — deterministic check runner.

Runs machine-checkable rules against a loaded sheet. Every result carries
full source traceability (row, column, before/expected). Checks that need
a human are NOT guessed — they are flagged PENDING-HUMAN and the embedded
image (if any) is extracted so the reviewer can confirm. No model is used.

Determinism: the runner is a pure function of (checks, sheet, as_of). No
randomness, no wall clock. Identical inputs -> identical output.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from sheet_solution.sheets.template import Check, CheckConfig
from sheet_solution.core.errors import ConfigError

# Outcome labels are the report's vocabulary. Never a third "maybe".
# Outcome label, not a credential (bandit B105 false positive).
PASS = "PASS"  # nosec B105
FAIL = "FAIL"
PENDING_HUMAN = "PENDING-HUMAN"
UNMAPPED = "UNMAPPED"


@dataclass
class CheckResult:
    check_id: str
    label: str                 # plain-English name of the check
    outcome: str               # PASS | FAIL | PENDING-HUMAN | UNMAPPED
    matched_rows: int
    failed_rows: int
    denominator: int
    detail: str
    failed_row_ids: list[str] = field(default_factory=list)
    extracted_image_paths: list[str] = field(default_factory=list)


def run_machine_check(check: Check, rows: list[dict], key: str = "row") -> CheckResult:
    """Deterministic rule evaluation over already-loaded rows.

    `rows` are dicts keyed by the sheet's columns; the engine inspects the
    column named in `check.column_name` (or the first column if unset).
    The pass/fail predicate is derived from the plain-English rule via the
    documented, hand-maintained predicate table in _predicate_for. Anything
    the table cannot express is PENDING-HUMAN, never a guess.
    """
    col = check.column_name or (next(iter(rows[0]), "") if rows else "")
    label = check.what_is_this_check_for or check.check_id

    pred, resolvable = _predicate_for(check.expected_value_or_rule, col, rows)
    if not resolvable:
        # Machine can't express this rule deterministically -> human decides.
        return CheckResult(
            check_id=check.check_id, label=label, outcome=PENDING_HUMAN,
            matched_rows=0, failed_rows=0, denominator=len(rows),
            detail=f"Rule {check.expected_value_or_rule!r} needs human review: "
                   f"{check.human_review_note or 'no automatic predicate available.'}",
        )
    if check.machine_can_check is False:
        # User explicitly marked this a human call even if a predicate exists.
        return CheckResult(
            check_id=check.check_id, label=label, outcome=PENDING_HUMAN,
            matched_rows=0, failed_rows=0, denominator=len(rows),
            detail=f"Marked for human review: {check.human_review_note or label}.",
        )

    matched = 0
    failed: list[str] = []
    for i, row in enumerate(rows):
        value = str(row.get(col, ""))
        row_id = str(row.get(key, f"row-{i}"))
        if pred(value):
            matched += 1
        else:
            failed.append(row_id)
    outcome = PASS if not failed else FAIL
    return CheckResult(
        check_id=check.check_id, label=label, outcome=outcome,
        matched_rows=matched, failed_rows=len(failed), denominator=len(rows),
        detail=(f"{matched}/{len(rows)} rows satisfied {check.expected_value_or_rule!r} "
                f"in column {col!r}."),
        failed_row_ids=failed,
    )


def _predicate_for(rule: str, col: str, rows: list[dict]):
    """Translate the plain-English rule into a named, deterministic predicate.

    The four legacy predicate families now resolve through the rules registry
    (``sheets.rules``) so the plain-English template and the policy layer share
    one implementation. Returns (predicate, resolvable); unresolvable rules
    return (None, False) so the caller routes them to a human, never a guess.
    """
    from sheet_solution.sheets.rules import registry as _rules

    text = rule.strip().lower()
    if text in ("no blank", "cannot be blank", "not blank", "no blanks",
                "cannot be empty", "not empty"):
        return (lambda v: _rules.apply("not_blank", v)), True
    if text in ("is blank", "is empty", "blank", "empty"):
        return (lambda v: _rules.apply("is_blank", v)), True
    for marker in ("must equal", "equals", "must be"):
        if marker in text:
            expected = text.split(marker, 1)[1].strip()
            return (lambda v: _rules.apply("equals", v, {"value": expected})), True
    # Numeric comparison (the registry owns the expression parser).
    if any(op in text for op in (">=", "<=", ">", "<")):
        return (lambda v: _rules.apply("numeric_range", v, {"expr": text})), True
    # Unexpressible -> human. Never invent a predicate.
    return (None, False)


def _numeric_ok(value: str, rule: str) -> bool:
    """Backward-compatible alias to the registry's numeric implementation."""
    from sheet_solution.sheets.rules import registry as _rules
    return _rules.numeric_ok(value, rule)


def run(config: CheckConfig, rows: list[dict], key: str = "row") -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in config.checks:
        results.append(run_machine_check(check, rows, key=key))
    return results
