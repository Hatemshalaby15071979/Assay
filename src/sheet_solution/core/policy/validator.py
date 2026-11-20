"""Fail-closed policy validation.

The single semantic gate for every input format. Anything ambiguous, unknown,
duplicated or mistyped is a ``ConfigError`` -- never a silent default. The
validator also applies defaults explicitly so all three formats converge on
the exact same :class:`Policy` value, which is the "one schema" guarantee.
"""
from __future__ import annotations

from typing import Any

from sheet_solution.core.errors import ConfigError
from sheet_solution.core.policy.schema import (
    ACTION_NAMES,
    ON_UNRESOLVED_CHOICES,
    POLICY_SCHEMA_VERSION,
    RULE_NAMES,
    SEVERITY_CHOICES,
    Compatibility,
    Defaults,
    OnFail,
    Policy,
    PolicyCheck,
)

_TOP_KEYS = {"version", "defaults", "checks", "compatibility"}
_CHECK_KEYS = {"id", "column", "rule", "params", "severity", "on_fail"}
_ON_FAIL_KEYS = {"actions", "confirm_required"}
_COMPAT_KEYS = {"required_columns", "allowed_values"}


def validate_policy(raw: Any) -> Policy:
    """Validate a canonical raw dict into a frozen :class:`Policy`.

    Fail closed on: wrong version, unknown top-level keys, missing/invalid
    defaults, empty or malformed check list, duplicate check ids, unknown rule
    or action ids, wrong types anywhere, and unknown compatibility keys.
    """
    if not isinstance(raw, dict):
        raise ConfigError("policy must be a mapping at the top level")
    _only_keys(raw, _TOP_KEYS, "policy")

    version = raw.get("version", POLICY_SCHEMA_VERSION)
    if version != POLICY_SCHEMA_VERSION:
        raise ConfigError(
            f"unsupported policy version {version!r}; expected {POLICY_SCHEMA_VERSION}")
    # Version is optional in the file (defaults to the current version) but we
    # echo the resolved value so all formats agree on one schema.

    defaults = _defaults(raw.get("defaults"))
    checks = _checks(raw.get("checks", []))
    compatibility = _compatibility(raw.get("compatibility"))
    return Policy(
        version=version, defaults=defaults,
        checks=tuple(checks), compatibility=compatibility)


def _only_keys(mapping: dict, allowed: set[str], where: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ConfigError(f"{where}: unknown field(s): {', '.join(unknown)}")


def _defaults(value: Any) -> Defaults:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ConfigError("policy.defaults must be a mapping")
    _only_keys(value, {"on_unresolved", "confirm_required"}, "policy.defaults")
    on_unresolved = value.get("on_unresolved", "propose")
    if on_unresolved not in ON_UNRESOLVED_CHOICES:
        raise ConfigError(
            f"policy.defaults.on_unresolved {on_unresolved!r} not in "
            f"{list(ON_UNRESOLVED_CHOICES)}")
    confirm = value.get("confirm_required", True)
    if not isinstance(confirm, bool):
        raise ConfigError("policy.defaults.confirm_required must be true or false")
    return Defaults(on_unresolved=on_unresolved, confirm_required=confirm)


def _checks(value: Any) -> list[PolicyCheck]:
    if not isinstance(value, list):
        raise ConfigError("policy.checks must be a list")
    out: list[PolicyCheck] = []
    seen: set[str] = set()
    for i, item in enumerate(value):
        where = f"policy.checks[{i}]"
        if not isinstance(item, dict):
            raise ConfigError(f"{where} must be a mapping")
        _only_keys(item, _CHECK_KEYS, where)
        cid = _required_str(item, "id", where)
        if cid in seen:
            raise ConfigError(f"duplicate policy check id {cid!r}")
        seen.add(cid)
        column = _required_str(item, "column", where)
        rule = _required_str(item, "rule", where)
        if rule not in RULE_NAMES:
            raise ConfigError(
                f"{where}: unknown rule {rule!r}; known rules: {', '.join(RULE_NAMES)}")
        params = item.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ConfigError(f"{where}.params must be a mapping")
        severity = item.get("severity", "medium")
        if severity not in SEVERITY_CHOICES:
            raise ConfigError(
                f"{where}: severity {severity!r} not in {list(SEVERITY_CHOICES)}")
        on_fail = _on_fail(item.get("on_fail"), where)
        out.append(PolicyCheck(
            id=cid, column=column, rule=rule, params=dict(params),
            severity=severity, on_fail=on_fail))
    return out


def _on_fail(value: Any, where: str) -> OnFail:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ConfigError(f"{where}.on_fail must be a mapping")
    _only_keys(value, _ON_FAIL_KEYS, f"{where}.on_fail")
    actions = value.get("actions", [])
    if actions is None:
        actions = []
    if not isinstance(actions, list) or not all(isinstance(a, str) for a in actions):
        raise ConfigError(f"{where}.on_fail.actions must be a list of strings")
    for action in actions:
        if action not in ACTION_NAMES:
            raise ConfigError(
                f"{where}: unknown action {action!r}; known actions: {', '.join(ACTION_NAMES)}")
    confirm = value.get("confirm_required", True)
    if not isinstance(confirm, bool):
        raise ConfigError(f"{where}.on_fail.confirm_required must be true or false")
    return OnFail(actions=tuple(actions), confirm_required=confirm)


def _compatibility(value: Any) -> Compatibility:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ConfigError("policy.compatibility must be a mapping")
    _only_keys(value, _COMPAT_KEYS, "policy.compatibility")
    required = value.get("required_columns", [])
    if required is None:
        required = []
    if not isinstance(required, list) or not all(isinstance(c, str) for c in required):
        raise ConfigError("policy.compatibility.required_columns must be a list of strings")
    allowed = value.get("allowed_values", {})
    if allowed is None:
        allowed = {}
    if not isinstance(allowed, dict):
        raise ConfigError("policy.compatibility.allowed_values must be a mapping")
    clean: dict[str, tuple[str, ...]] = {}
    for column, values in allowed.items():
        if not isinstance(column, str):
            raise ConfigError("policy.compatibility.allowed_values keys must be column names")
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ConfigError(
                f"policy.compatibility.allowed_values[{column!r}] must be a list of strings")
        clean[column] = tuple(values)
    return Compatibility(
        required_columns=tuple(required), allowed_values=clean)


def _required_str(mapping: dict, key: str, where: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where}.{key} is required and must be a non-empty string")
    return value.strip()
