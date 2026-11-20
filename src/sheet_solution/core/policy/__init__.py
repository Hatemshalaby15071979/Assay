"""Versioned, single-schema policy model for sheet operations.

A policy is the human-authored answer to "what am I allowed to decide for
myself, and what must a person confirm?" It is untrusted input: every loader
(JSON, YAML subset, key/value sheet) normalises to one raw dict which the
validator either accepts into a :class:`Policy` or refuses (fail closed).

No model, no network, no environment reads. The vocabulary below is the
single source of truth shared with ``sheets.rules`` (rule ids) and the
decision layer to come (action ids).
"""
from sheet_solution.core.policy import schema, yaml_lite, loader, validator
from sheet_solution.core.policy.schema import (
    POLICY_SCHEMA_VERSION,
    RULE_NAMES,
    ACTION_NAMES,
    ON_UNRESOLVED_CHOICES,
    SEVERITY_CHOICES,
    Policy,
)
from sheet_solution.core.policy.loader import load_policy
from sheet_solution.core.policy.validator import validate_policy

__all__ = [
    "schema", "yaml_lite", "loader", "validator",
    "POLICY_SCHEMA_VERSION", "RULE_NAMES", "ACTION_NAMES",
    "ON_UNRESOLVED_CHOICES", "SEVERITY_CHOICES",
    "Policy", "load_policy", "validate_policy",
]
