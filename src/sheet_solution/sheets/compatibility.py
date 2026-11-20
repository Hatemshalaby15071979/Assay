"""Compatibility check — "can these two sheets be combined safely?"

Distinct from row-level ``compare``: compatibility is a first-class ops task
that answers schema and domain questions using the policy's declared
``required_columns`` and ``allowed_values``:

* required columns present in both sheets;
* shared columns carry the same inferred type;
* every value in a constrained column is in the policy's allowed set.

Every finding names the exact column and value; verdict is a defensible
COMPATIBLE / INCOMPATIBLE, never "looks fine". Pure function of its inputs.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sheet_solution.sheets.analyze import _classify, _q

COMPATIBLE = "COMPATIBLE"
INCOMPATIBLE = "INCOMPATIBLE"


@dataclass
class Finding:
    code: str
    column: str
    detail: str


@dataclass
class CompatibilityResult:
    verdict: str
    required_columns: tuple[str, ...]
    findings: list[Finding] = field(default_factory=list)

    def summary(self) -> str:
        counts = "no findings" if not self.findings else \
            f"{len(self.findings)} finding(s): " + ", ".join(f.code for f in self.findings)
        return f"{self.verdict} — {counts}"

    def csv(self) -> str:
        header = "code,column,detail\n"
        lines = [header]
        for f in self.findings:
            lines.append(",".join([_q(f.code), _q(f.column), _q(f.detail)]))
        return "\n".join(lines) + "\n"


def compatibility(
    a_rows: list[dict],
    b_rows: list[dict],
    required_columns: tuple[str, ...] = (),
    allowed_values: dict | None = None,
) -> CompatibilityResult:
    allowed_values = allowed_values or {}
    findings: list[Finding] = []
    cols_a = _union_columns(a_rows)
    cols_b = _union_columns(b_rows)

    for col in required_columns:
        if col not in cols_a:
            findings.append(Finding("REQUIRED_MISSING_IN_A", col,
                                    f"required column {col!r} absent from sheet A"))
        if col not in cols_b:
            findings.append(Finding("REQUIRED_MISSING_IN_B", col,
                                    f"required column {col!r} absent from sheet B"))

    shared = [c for c in cols_a if c in cols_b]
    for col in shared:
        ta = _classify([str(r.get(col, "")) for r in a_rows])
        tb = _classify([str(r.get(col, "")) for r in b_rows])
        if ta != tb:
            findings.append(Finding(
                "TYPE_MISMATCH", col,
                f"column {col!r} is {ta} in A but {tb} in B"))

    for col, choices in allowed_values.items():
        allowed = {str(v).strip() for v in choices}
        for label, rows in (("A", a_rows), ("B", b_rows)):
            for i, row in enumerate(rows):
                value = str(row.get(col, "")).strip()
                if value and value not in allowed:
                    findings.append(Finding(
                        "DOMAIN_VIOLATION", col,
                        f"{label} row {i}: {col}={value!r} not in allowed set"))

    verdict = INCOMPATIBLE if findings else COMPATIBLE
    return CompatibilityResult(
        verdict=verdict, required_columns=tuple(required_columns),
        findings=findings)


def _union_columns(rows: list[dict]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return columns
