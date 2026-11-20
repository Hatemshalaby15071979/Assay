"""Policy loaders: three input formats, one canonical raw dict.

File first (``.json`` / ``.yaml`` / ``.yml``), sheet second
(``.csv`` / ``.xlsx`` key/value long-form). A *policy sheet* is a two-column
table ``key,value`` where ``key`` is a dotted path into the canonical schema
and ``value`` is a scalar (coerced) or a JSON flow value starting with ``[``
or ``{``. Every loader returns a plain dict; :mod:`validator` does all
semantics so the formats cannot diverge.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from sheet_solution.core.errors import ConfigError
from sheet_solution.core.policy import yaml_lite

_SHEET_KEYS = {"key", "path"}


def load_policy(path: Path | str, *, sheet: str = "") -> dict:
    """Load a policy file into the canonical raw dict (validation is separate).

    ``sheet`` selects the worksheet name for ``.xlsx`` policies; ignored for
    other formats. Files are read by extension; unknown extensions fail closed.
    """
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".json":
        return _load_json(p)
    if ext in (".yaml", ".yml"):
        return _load_yaml(p)
    if ext == ".csv":
        return _load_csv(p)
    if ext == ".xlsx":
        return _load_xlsx(p, sheet=sheet)
    raise ConfigError(
        f"unsupported policy file type {ext!r} for {p.name}; "
        "expected .json, .yaml, .yml, .csv or .xlsx")


def _load_json(p: Path) -> dict:
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read policy JSON {p.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"policy JSON {p.name} must be an object at the top level")
    return data


def _load_yaml(p: Path) -> dict:
    try:
        data = yaml_lite.loads(p.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise ConfigError(f"cannot read policy YAML {p.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"policy YAML {p.name} must be a mapping at the top level")
    return data


def _load_csv(p: Path) -> dict:
    try:
        with p.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh))
    except OSError as exc:
        raise ConfigError(f"cannot read policy sheet {p.name}: {exc}") from exc
    return _rows_to_raw(rows, p.name)


def _load_xlsx(p: Path, *, sheet: str) -> dict:
    try:
        import openpyxl  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ConfigError(
            f"{p.name}: .xlsx policies need the 'xlsx' extra — "
            "pip install 'sheet_solution[xlsx]'") from exc
    try:
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        ws = wb[sheet] if sheet else wb[wb.sheetnames[0]]
        rows = [["" if c is None else str(c) for c in row]
                for row in ws.iter_rows(values_only=True)]
    except (OSError, KeyError, ValueError) as exc:
        raise ConfigError(f"cannot read policy sheet {p.name}: {exc}") from exc
    return _rows_to_raw(rows, p.name)


def _rows_to_raw(rows: list[list[str]], name: str) -> dict:
    """Two-column ``key,value`` long form -> nested canonical raw dict."""
    rows = [[c.strip() for c in row] for row in rows if any(str(c).strip() for c in row)]
    if not rows:
        raise ConfigError(f"policy sheet {name} is empty")
    header = [c.lower() for c in rows[0]]
    if len(header) != 2 or header[0] not in _SHEET_KEYS or header[1] != "value":
        raise ConfigError(
            f"policy sheet {name} must have exactly two columns: key,value "
            f"(got {rows[0]!r})")
    raw: dict[str, Any] = {}
    for lineno, row in enumerate(rows[1:], start=2):
        if len(row) != 2:
            raise ConfigError(f"policy sheet {name} line {lineno}: expected 2 columns, got {len(row)}")
        key, value = row
        if "." in key and not all(part for part in key.split(".")):
            raise ConfigError(f"policy sheet {name} line {lineno}: empty path segment in {key!r}")
        _set_path(raw, key.split("."), _cell(value), name, lineno)
    return raw


def _cell(text: str) -> Any:
    """Coerce a sheet cell: JSON flow/scalar when possible, else plain text."""
    text = text.strip()
    if text.startswith(("[", "{")):
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"invalid JSON value in policy cell {text!r}: {exc}") from exc
    low = text.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~", "none"):
        return None
    if _is_int(text):
        return int(text)
    if _is_float(text):
        return float(text)
    return text


def _is_int(text: str) -> bool:
    body = text[1:] if text[:1] in ("+", "-") else text
    return bool(body) and body.isdigit()


def _is_float(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return any(c in text for c in ".eE")


def _set_path(root: dict, parts: list[str], value: Any, name: str, lineno: int) -> None:
    node: Any = root
    for i, part in enumerate(parts[:-1]):
        nxt = parts[i + 1]
        is_index = nxt.isdigit()
        if isinstance(node, list):
            if not part.isdigit():
                raise ConfigError(
                    f"policy sheet {name} line {lineno}: expected a list index, got {part!r}")
            idx = int(part)
            _ensure_index(node, idx, is_index, name, lineno)
            node = node[idx]
        else:
            if part not in node:
                node[part] = [] if is_index else {}
            node = node[part]
    last = parts[-1]
    if last.isdigit():
        raise ConfigError(f"policy sheet {name} line {lineno}: path cannot end in an index")
    if isinstance(node, list):
        raise ConfigError(f"policy sheet {name} line {lineno}: expected a mapping at {parts!r}")
    if last in node:
        raise ConfigError(f"policy sheet {name} line {lineno}: duplicate key path {'.'.join(parts)!r}")
    node[last] = value


def _ensure_index(node: list, idx: int, is_container: bool, name: str, lineno: int) -> None:
    while len(node) <= idx:
        node.append(None)
    if node[idx] is None:
        node[idx] = [] if is_container else {}
    if node[idx] is None or not isinstance(node[idx], (dict, list)):
        raise ConfigError(f"policy sheet {name} line {lineno}: path traversal conflict at index {idx}")
