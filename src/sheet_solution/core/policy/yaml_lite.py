"""A deliberately small, safe YAML subset parser -- no third-party dependency.

The platform ships offline with only stdlib + a few pinned pure-Python libs.
PyYAML is not pinned, so instead of adding an unpinned runtime dependency we
parse the *subset* of YAML our policy files need:

* block mappings (``key: value``) and block sequences (``- value``),
* flow sequences ``[a, b]`` and flow mappings ``{k: v}``,
* scalars: quoted strings, integers, floats, booleans, ``null``,
* ``#`` comments on their own line or trailing a value.

Everything else is refused with ``ConfigError``: anchors (``&``), aliases
(``*``), tags (``!``), merge keys, multi-document streams (``---``), tabs for
indentation, duplicate keys, and ambiguous unterminated quotes/flows. This is
fail-closed by design: a policy that uses YAML features we do not fully
understand is rejected rather than silently mis-parsed.
"""
from __future__ import annotations

import re
from typing import Any

from sheet_solution.core.errors import ConfigError

_INT = re.compile(r"[+-]?\d+\Z")
_FLOAT = re.compile(r"[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?\Z")


def loads(text: str) -> Any:
    """Parse a restricted-YAML document into plain dict/list/scalars."""
    rows = _tokenise(text)
    if not rows:
        return {}
    parser = _BlockParser(rows)
    value = parser.parse_block(rows[0][0])
    if parser.pos != len(rows):
        _, content, lineno = rows[parser.pos]
        raise ConfigError(f"yaml_lite: unexpected content at line {lineno}: {content!r}")
    return value


def _tokenise(text: str) -> list[tuple[int, str, int]]:
    rows: list[tuple[int, str, int]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise ConfigError(f"yaml_lite: tabs are not allowed for indentation (line {lineno})")
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("---") or stripped == "...":
            raise ConfigError(f"yaml_lite: document markers are not supported (line {lineno})")
        indent = len(raw) - len(raw.lstrip(" "))
        content = _strip_comment(raw[indent:])
        if not content:
            continue
        _reject_dangerous(content, lineno)
        rows.append((indent, content, lineno))
    return rows


def _strip_comment(text: str) -> str:
    quote: str | None = None
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "#" and (i == 0 or text[i - 1] in (" ", "\t")):
            return text[:i].rstrip()
    return text.rstrip()


def _reject_dangerous(content: str, lineno: int) -> None:
    # Check both a bare value and the value half of a "key: value" pair, plus
    # sequence items ("- ..."), so anchors/tags cannot hide after a key.
    candidates = [content.lstrip()]
    pair = _split_kv(content)
    if pair is not None:
        candidates.append(pair[1].lstrip())
    if content.startswith("-"):
        candidates.append(content[1:].lstrip())
    for lead_text in candidates:
        if lead_text[:1] in ("&", "*", "!"):
            raise ConfigError(
                f"yaml_lite: anchors, aliases and tags are not supported "
                f"(line {lineno}: {content!r})")
        if lead_text.startswith("<<"):
            raise ConfigError(f"yaml_lite: merge keys are not supported (line {lineno})")


class _BlockParser:
    def __init__(self, rows: list[tuple[int, str, int]]) -> None:
        self.rows = rows
        self.pos = 0

    def parse_block(self, indent: int) -> Any:
        if self.pos >= len(self.rows):
            return None
        content = self.rows[self.pos][1]
        if content == "-" or content.startswith("- "):
            return self._parse_sequence(indent)
        if _split_kv(content) is not None:
            return self._parse_mapping(indent)
        # A bare scalar block is not part of the policy grammar.
        _, _, lineno = self.rows[self.pos]
        raise ConfigError(f"yaml_lite: expected mapping or sequence at line {lineno}: {content!r}")

    def _parse_mapping(self, indent: int) -> dict:
        out: dict[str, Any] = {}
        while self.pos < len(self.rows):
            row_indent, content, lineno = self.rows[self.pos]
            if row_indent < indent:
                break
            if row_indent > indent:
                raise ConfigError(f"yaml_lite: bad indentation at line {lineno}: {content!r}")
            if content == "-" or content.startswith("- "):
                break
            pair = _split_kv(content)
            if pair is None:
                raise ConfigError(f"yaml_lite: expected 'key: value' at line {lineno}: {content!r}")
            key, value_text = pair
            if key in out:
                raise ConfigError(f"yaml_lite: duplicate key {key!r} at line {lineno}")
            self.pos += 1
            if value_text:
                out[key] = _scalar(value_text, lineno)
            elif self.pos < len(self.rows) and self.rows[self.pos][0] > indent:
                out[key] = self.parse_block(self.rows[self.pos][0])
            else:
                out[key] = None
        return out

    def _parse_sequence(self, indent: int) -> list:
        out: list[Any] = []
        while self.pos < len(self.rows):
            row_indent, content, lineno = self.rows[self.pos]
            if row_indent < indent:
                break
            if row_indent > indent:
                raise ConfigError(f"yaml_lite: bad indentation at line {lineno}: {content!r}")
            if not (content == "-" or content.startswith("- ")):
                break
            item_text = content[1:].lstrip()
            self.pos += 1
            if not item_text:
                if self.pos < len(self.rows) and self.rows[self.pos][0] > indent:
                    out.append(self.parse_block(self.rows[self.pos][0]))
                else:
                    out.append(None)
            elif _split_kv(item_text) is not None:
                # Inline first key of a mapping item, e.g. "- id: CH-001".
                key, value_text = _split_kv(item_text)  # type: ignore[misc]
                item: dict[str, Any] = {}
                if key in item:
                    raise ConfigError(f"yaml_lite: duplicate key {key!r} at line {lineno}")
                if value_text:
                    item[key] = _scalar(value_text, lineno)
                elif self.pos < len(self.rows) and self.rows[self.pos][0] > indent:
                    item[key] = self.parse_block(self.rows[self.pos][0])
                else:
                    item[key] = None
                # Remaining keys of this item are indented deeper than the dash.
                while (self.pos < len(self.rows)
                       and self.rows[self.pos][0] > indent
                       and _split_kv(self.rows[self.pos][1]) is not None):
                    child_indent, child_content, child_lineno = self.rows[self.pos]
                    pair = _split_kv(child_content)
                    if pair is None:  # pragma: no cover - guarded by while
                        break
                    ckey, cval = pair
                    if ckey in item:
                        raise ConfigError(f"yaml_lite: duplicate key {ckey!r} at line {child_lineno}")
                    self.pos += 1
                    if cval:
                        item[ckey] = _scalar(cval, child_lineno)
                    elif self.pos < len(self.rows) and self.rows[self.pos][0] > child_indent:
                        item[ckey] = self.parse_block(self.rows[self.pos][0])
                    else:
                        item[ckey] = None
                out.append(item)
            else:
                out.append(_scalar(item_text, lineno))
        return out


def _split_kv(text: str) -> tuple[str, str] | None:
    quote: str | None = None
    depth = 0
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch in ("[", "{"):
            depth += 1
        elif ch in ("]", "}"):
            depth -= 1
        elif ch == ":" and depth == 0 and (i + 1 == len(text) or text[i + 1] in (" ", "\t")):
            key = text[:i].strip()
            if not key:
                return None
            return key, text[i + 1:].strip()
    return None


def _scalar(text: str, lineno: int) -> Any:
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        return [_scalar(p, lineno) for p in _split_flow(text[1:-1])]
    if text.startswith("{") and text.endswith("}"):
        out: dict[str, Any] = {}
        for part in _split_flow(text[1:-1]):
            pair = _split_kv(part)
            if pair is None:
                raise ConfigError(f"yaml_lite: bad flow mapping at line {lineno}: {part!r}")
            key, val = pair
            if key in out:
                raise ConfigError(f"yaml_lite: duplicate key {key!r} at line {lineno}")
            out[key] = _scalar(val, lineno)
        return out
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1]
    if text[0] in ("[", "{") or text[-1:] in ("]", "}"):
        raise ConfigError(f"yaml_lite: unterminated flow value at line {lineno}: {text!r}")
    low = text.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~", "none"):
        return None
    if _INT.match(text):
        return int(text)
    if _FLOAT.match(text):
        return float(text)
    return text


def _split_flow(inner: str) -> list[str]:
    if not inner.strip():
        return []
    parts: list[str] = []
    quote: str | None = None
    depth = 0
    start = 0
    for i, ch in enumerate(inner):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch in ("[", "{"):
            depth += 1
        elif ch in ("]", "}"):
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(inner[start:i].strip())
            start = i + 1
    parts.append(inner[start:].strip())
    if quote is not None or depth != 0:
        raise ConfigError("yaml_lite: unbalanced flow value")
    return parts
