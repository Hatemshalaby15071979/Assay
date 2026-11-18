"""Sheet Solution — report assembly.

Builds the check-results report (CSV) and routes image/semantic checks to
the inherited hash-chain + render + verify pipeline so the output stays
auditable and re-verifiable. The deterministic spine does the heavy lifting
here; this module just shapes the new `check-results` artifact.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sheet_solution.sheets.runner import CheckResult


def render_results_csv(results: list[CheckResult]) -> str:
    header = ("check_id,label,outcome,matched_rows,failed_rows,denominator,"
              "failed_row_ids,detail\n")
    lines = []
    for r in results:
        failed = ";".join(r.failed_row_ids)
        lines.append(
            f"{_csv(r.check_id)},{_csv(r.label)},{r.outcome},"
            f"{r.matched_rows},{r.failed_rows},{r.denominator},"
            f"{_csv(failed)},{_csv(r.detail)}")
    return header + "\n".join(lines) + "\n"


def _csv(value: str) -> str:
    """Quote a CSV field when needed; neutralise formula injection.

    A field that could be read as a spreadsheet formula (leading = + - @ or
    tab/CR) is always quoted so CSV consumers (Excel, LibreOffice, Google
    Sheets) treat it as inert text, not an executable formula. This mirrors
    the inherited spine's CSV-injection neutralisation on export paths.
    """
    needs_quote = (
        any(c in value for c in ',"\n')
        or value[:1] in ("=", "+", "-", "@", "\t", "\r")
    )
    return ('"' + value.replace('"', '""') + '"' if needs_quote else value)


def summary(results: list[CheckResult]) -> str:
    n_pass = sum(1 for r in results if r.outcome == "PASS")
    n_fail = sum(1 for r in results if r.outcome == "FAIL")
    n_human = sum(1 for r in results if r.outcome == "PENDING-HUMAN")
    return (f"{n_pass} passed, {n_fail} failed, "
            f"{n_human} awaiting human review, {len(results)} total.")
