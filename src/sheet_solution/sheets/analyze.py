"""Sheet profiling — deterministic "what is in this sheet?" analysis.

A first-class ops task alongside audit and compare. For each column it
infers a type, counts blanks and distinct values, and (for numeric/date
columns) reports a deterministic min/max. No model, no wall clock, no
network: a pure function of the loaded rows.
"""
from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from dataclasses import dataclass, field

_INT = re.compile(r"[+-]?\d+\Z")
_FLOAT = re.compile(r"[+-]?(?:\d+\.\d*|\.\d+)\Z")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_TYPES = ("blank", "integer", "number", "date", "boolean", "text")


@dataclass
class ColumnProfile:
    name: str
    inferred_type: str
    rows: int
    blank_count: int
    distinct_count: int
    minimum: str = ""
    maximum: str = ""


@dataclass
class AnalysisResult:
    row_count: int
    column_count: int
    columns: list[ColumnProfile] = field(default_factory=list)

    def summary(self) -> str:
        return (f"analyzed {self.row_count} row(s), {self.column_count} column(s): "
                + ", ".join(f"{c.name}={c.inferred_type}" for c in self.columns))

    def csv(self) -> str:
        header = "column,inferred_type,rows,blank_count,distinct_count,minimum,maximum\n"
        lines = [header]
        for c in self.columns:
            lines.append(",".join([
                _q(c.name), c.inferred_type, str(c.rows), str(c.blank_count),
                str(c.distinct_count), _q(c.minimum), _q(c.maximum),
            ]))
        return "\n".join(lines) + "\n"


def _q(v: str) -> str:
    return ('"' + v.replace('"', '""') + '"'
            if any(c in v for c in ',"\n') or v[:1] in ("=", "+", "-", "@") else v)


def _classify(values: list[str]) -> str:
    nonblank = [v for v in values if v.strip()]
    if not nonblank:
        return "blank"
    if all(_INT.match(v) for v in nonblank):
        return "integer"
    if all(_FLOAT.match(v) or _INT.match(v) for v in nonblank):
        return "number"
    if all(_DATE.match(v) for v in nonblank):
        return "date"
    if all(v.strip().lower() in ("true", "false", "yes", "no") for v in nonblank):
        return "boolean"
    return "text"


def _extremes(values: list[str], kind: str) -> tuple[str, str]:
    if kind == "integer":
        nums = [int(v) for v in values if v.strip()]
        return (str(min(nums)), str(max(nums))) if nums else ("", "")
    if kind == "number":
        nums = [float(v) for v in values if v.strip()]
        return (_fmt(min(nums)), _fmt(max(nums))) if nums else ("", "")
    if kind == "date":
        dates = [dt.date.fromisoformat(v.strip()) for v in values if v.strip()]
        return (min(dates).isoformat(), max(dates).isoformat()) if dates else ("", "")
    return ("", "")


def _fmt(n: float) -> str:
    return str(int(n)) if n == int(n) else str(n)


def analyze(rows: list[dict]) -> AnalysisResult:
    """Profile rows; column order follows first appearance (deterministic)."""
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    profiles: list[ColumnProfile] = []
    for name in columns:
        values = [str(row.get(name, "")) for row in rows]
        kind = _classify(values)
        blank = sum(1 for v in values if not v.strip())
        distinct = len({v.strip() for v in values})
        lo, hi = _extremes(values, kind)
        profiles.append(ColumnProfile(
            name=name, inferred_type=kind, rows=len(rows),
            blank_count=blank, distinct_count=distinct,
            minimum=lo, maximum=hi))
    return AnalysisResult(
        row_count=len(rows), column_count=len(columns), columns=profiles)
