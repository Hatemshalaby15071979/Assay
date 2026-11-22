"""The one canonical policy schema.

Every on-disk representation (JSON, the restricted YAML subset, or a
key/value policy sheet) normalises to a raw dict with exactly these shapes,
then :func:`sheet_solution.core.policy.validator.validate_policy` turns it
into the frozen :class:`Policy` value objects below.

``RULE_NAMES`` and ``ACTION_NAMES`` are the shared vocabulary: the rules
registry in ``sheets.rules`` and the future decision layer import these so a
policy can never name a rule or action the platform does not implement.
"""
from __future__ import annotations

from dataclasses import dataclass, field

POLICY_SCHEMA_VERSION = 1

# Fail-closed enums. A value outside these sets is a ConfigError, never a
# silent default -- "the machine never guesses" applies to policy too.
ON_UNRESOLVED_CHOICES = ("propose", "flag", "block")
SEVERITY_CHOICES = ("low", "medium", "high")

# Rule ids implemented by sheets.rules.registry (Phase B). Kept here so the
# validator can reject an unknown rule before any work starts.
RULE_NAMES = (
    "not_blank",
    "is_blank",
    "equals",
    "numeric_range",
    "one_of",
    "regex",
    "date_before",
    "date_within_range",
    "date_before_today",
    "cross_column",
    "lookup_in",
    "unique",
    "unique_across_sheets",
    "email_format",
    "phone_format",
    "iban_format",
    "starts_with",
    "ends_with",
    "contains_any",
    "contains_all",
    "cross_sheet_lookup",
    "checksum_valid",
)

# Declarative action ids. Phase A validates them; later phases execute them.
# Listing an action in a policy does not execute it in Phase A/B.
ACTION_NAMES = (
    "tag_row",
    "flag_for_human",
    "emit_corrected_copy",
    "drop_row",
    "escalate",
)


@dataclass(frozen=True)
class Defaults:
    on_unresolved: str
    confirm_required: bool


@dataclass(frozen=True)
class OnFail:
    actions: tuple[str, ...] = ()
    confirm_required: bool = True


@dataclass(frozen=True)
class PolicyCheck:
    id: str
    column: str
    rule: str
    params: dict = field(default_factory=dict)
    severity: str = "medium"
    on_fail: OnFail = field(default_factory=OnFail)


@dataclass(frozen=True)
class Compatibility:
    required_columns: tuple[str, ...] = ()
    allowed_values: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Policy:
    """A validated, human-authored policy. One schema, three input formats."""

    version: int
    defaults: Defaults
    checks: tuple[PolicyCheck, ...] = ()
    compatibility: Compatibility = field(default_factory=Compatibility)

    def echo(self) -> str:
        """Plain-English proof of what the machine understood (fail-closed echo)."""
        lines = [
            f"policy version: {self.version}",
            f"on_unresolved: {self.defaults.on_unresolved}",
            f"confirm_required: {str(self.defaults.confirm_required).lower()}",
            f"checks: {len(self.checks)}",
        ]
        for c in self.checks:
            actions = ",".join(c.on_fail.actions) or "none"
            lines.append(
                f"  - {c.id}: column={c.column!r} rule={c.rule} "
                f"severity={c.severity} on_fail=[{actions}] "
                f"confirm={str(c.on_fail.confirm_required).lower()}")
        lines.append(
            f"compatibility: required_columns="
            f"[{','.join(self.compatibility.required_columns)}] "
            f"allowed_values={len(self.compatibility.allowed_values)} column(s)")
        return "\n".join(lines)

    def to_raw(self) -> dict:
        """Round-trip back to the canonical raw dict (for equality tests)."""
        return {
            "version": self.version,
            "defaults": {
                "on_unresolved": self.defaults.on_unresolved,
                "confirm_required": self.defaults.confirm_required,
            },
            "checks": [
                {
                    "id": c.id, "column": c.column, "rule": c.rule,
                    "params": dict(c.params), "severity": c.severity,
                    "on_fail": {
                        "actions": list(c.on_fail.actions),
                        "confirm_required": c.on_fail.confirm_required,
                    },
                }
                for c in self.checks
            ],
            "compatibility": {
                "required_columns": list(self.compatibility.required_columns),
                "allowed_values": {k: list(v)
                                   for k, v in self.compatibility.allowed_values.items()},
            },
        }
