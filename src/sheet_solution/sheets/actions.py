"""Named, deterministic action executors for the decision loop.

A policy may only *name* an action id and pass data params; it can never
carry code. The executor is looked up in this fixed registry, so applying a
decision cannot execute arbitrary input. Every action is a pure row
transform: same (row, params) -> same result, offline, no model, no clock.

The id vocabulary is shared with ``core.policy.schema.ACTION_NAMES``; the
module refuses to load if the two ever disagree.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sheet_solution.core.errors import ConfigError
from sheet_solution.core.policy.schema import ACTION_NAMES

Executor = Callable[[dict, dict], tuple[dict, str, bool]]


@dataclass(frozen=True)
class ActionResult:
    action: str
    row: dict
    note: str
    drop: bool = False


def _tag_row(row: dict, params: dict) -> tuple[dict, str, bool]:
    column = str(params.get("column", "__action"))
    value = str(params.get("value", "tagged"))
    out = dict(row)
    out[column] = value
    return out, f"set {column}={value!r}", False


def _flag_for_human(row: dict, params: dict) -> tuple[dict, str, bool]:
    column = str(params.get("column", "__needs_human"))
    out = dict(row)
    out[column] = "yes"
    return out, f"flagged for human review in {column}", False


def _emit_corrected_copy(row: dict, params: dict) -> tuple[dict, str, bool]:
    # The corrected copy is emitted by the orchestrator for all applied rows;
    # this action marks the row as included (an honest, side-effect-free tag).
    column = str(params.get("column", "__corrected"))
    out = dict(row)
    out[column] = "yes"
    return out, "included in corrected copy", False


def _drop_row(row: dict, params: dict) -> tuple[dict, str, bool]:
    note = params.get("note", "row marked for removal")
    return dict(row), str(note), True


def _escalate(row: dict, params: dict) -> tuple[dict, str, bool]:
    column = str(params.get("column", "__escalated"))
    out = dict(row)
    out[column] = "yes"
    return out, "escalated for a named owner", False


ACTIONS: dict[str, Executor] = {
    "tag_row": _tag_row,
    "flag_for_human": _flag_for_human,
    "emit_corrected_copy": _emit_corrected_copy,
    "drop_row": _drop_row,
    "escalate": _escalate,
}


def action_ids() -> tuple[str, ...]:
    return tuple(sorted(ACTIONS))


def apply_action(action_id: str, row: dict, params: dict | None = None) -> ActionResult:
    """Execute a named action on a row; unknown ids fail closed."""
    fn = ACTIONS.get(action_id)
    if fn is None:
        raise ConfigError(
            f"unknown action {action_id!r}; known actions: {', '.join(action_ids())}")
    new_row, note, drop = fn(dict(row), params or {})
    return ActionResult(action=action_id, row=new_row, note=note, drop=drop)


_registry_ids = frozenset(ACTIONS)
_schema_ids = frozenset(ACTION_NAMES)
if _registry_ids != _schema_ids:
    raise ConfigError(
        "actions registry and policy schema disagree on action ids "
        f"(registry-only={sorted(_registry_ids - _schema_ids)}, "
        f"schema-only={sorted(_schema_ids - _registry_ids)})")
