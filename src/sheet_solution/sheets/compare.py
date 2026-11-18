"""Sheet Solution — two-sheet comparison.

Deterministic row-level comparison of two sheets that should agree (or of a
baseline vs. a new run). This is the "some of my people have two sheets and
want to compare" case, kept honest and logged like the rest of the platform:

- **No guessing.** Each row is classified by explicit rules against the
  row-key + compared columns. The outcome of the whole run is a count of
  matched / changed / only-in-A / only-in-B, never a soft "looks the same".
- **Traceability.** Every diff names the row key and the exact columns whose
  values differ, on both sides.
- **Numeric tolerance** is optional and explicit — a value is "changed" only
  when it differs beyond the declared tolerance (exact when none is given).
- **PII stays local.** Nothing leaves the machine; output is a CSV + JSON
  report pack that reuses the inherited hash-chain + verify for integrity.

The module is a pure function of (A, B, key, columns, tolerance).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Row classification labels — the report's vocabulary.
MATCHED = "MATCHED"
CHANGED = "CHANGED"
ONLY_A = "ONLY-IN-A"
ONLY_B = "ONLY-IN-B"


@dataclass
class DiffRow:
    key: str
    status: str
    changed_fields: list[str] = field(default_factory=list)
    a_value: dict = field(default_factory=dict)
    b_value: dict = field(default_factory=dict)


@dataclass
class CompareResult:
    key_column: str
    compared_fields: list[str]
    tolerance: str
    total_a: int
    total_b: int
    matched: int
    changed: int
    only_a: int
    only_b: int
    rows: list[DiffRow] = field(default_factory=list)

    def summary(self) -> str:
        return (f"{self.matched} matched, {self.changed} changed, "
                f"{self.only_a} only-in-A, {self.only_b} only-in-B "
                f"(A={self.total_a}, B={self.total_b}, key={self.key_column!r})")

    def csv(self) -> str:
        header = ("key,status,changed_fields,a_values,b_values\n")
        out = [header]
        for r in self.rows:
            out.append(",".join([
                _q(r.key), r.status, _q(";".join(r.changed_fields)),
                _q(_fmt(r.a_value)), _q(_fmt(r.b_value)),
            ]))
        return "\n".join(out) + "\n"


def _fmt(values: dict) -> str:
    return "; ".join(f"{k}={v}" for k, v in sorted(values.items())) or "-"


def _q(v: str) -> str:
    """Quote a CSV field; neutralise leading formula chars (matches report.py)."""
    return ('"' + v.replace('"', '""') + '"'
            if any(c in v for c in ',"\n') or v[:1] in ("=", "+", "-", "@") else v)


# ---------------------------------------------------------------------------
# tolerance
# ---------------------------------------------------------------------------
def _parse_tolerance(text: str) -> float | None:
    text = text.strip().lower()
    if not text or text in ("none", "exact", "0", "0.0"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _values_equal(a: str, b: str, tol: float | None, column: str) -> bool:
    if a == b:
        return True
    if tol is not None:
        try:
            return abs(float(a) - float(b)) <= tol
        except (ValueError, TypeError):
            return False
    return False


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------
def compare(
    a_rows: list[dict],
    b_rows: list[dict],
    key_column: str,
    compared_fields: list[str],
    tolerance: str = "",
) -> CompareResult:
    tol = _parse_tolerance(tolerance)

    a_index = _index(a_rows, key_column)
    b_index = _index(b_rows, key_column)

    all_keys = sorted(set(a_index) | set(b_index), key=str)
    rows: list[DiffRow] = []
    matched = changed = only_a = only_b = 0

    for key in all_keys:
        in_a = key in a_index
        in_b = key in b_index
        if in_a and not in_b:
            only_a += 1
            rows.append(DiffRow(str(key), ONLY_A, a_value=_pick(a_index[key], compared_fields)))
        elif in_b and not in_a:
            only_b += 1
            rows.append(DiffRow(str(key), ONLY_B, b_value=_pick(b_index[key], compared_fields)))
        else:
            ra = a_index[key]; rb = b_index[key]
            changed_fields = [
                f for f in compared_fields
                if not _values_equal(str(ra.get(f, "")), str(rb.get(f, "")), tol, f)
            ]
            if changed_fields:
                changed += 1
                rows.append(DiffRow(str(key), CHANGED, changed_fields,
                                    a_value=_pick(ra, compared_fields),
                                    b_value=_pick(rb, compared_fields)))
            else:
                matched += 1
                rows.append(DiffRow(str(key), MATCHED,
                                    a_value=_pick(ra, compared_fields),
                                    b_value=_pick(rb, compared_fields)))

    # Deterministic ordering: by key, then status, so identical inputs always
    # yield identical output.
    rows.sort(key=lambda r: (r.key, r.status))
    return CompareResult(
        key_column=key_column, compared_fields=list(compared_fields),
        tolerance=tolerance, total_a=len(a_rows), total_b=len(b_rows),
        matched=matched, changed=changed, only_a=only_a, only_b=only_b,
        rows=rows)


def _index(rows: list[dict], key_column: str) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for row in rows:
        key = str(row.get(key_column, "")).strip()
        if key and key not in index:  # first occurrence wins; dupes are data errors
            index[key] = row
    return index


def _pick(row: dict, fields: list[str]) -> dict:
    return {f: row.get(f, "") for f in fields}
