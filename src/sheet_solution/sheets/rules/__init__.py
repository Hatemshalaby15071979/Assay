"""Named, deterministic row rules -- one registry, stable ids.

The plain-English check runner and the policy layer both evaluate through
here. Every rule is a pure function of (value, params, row, rows): no wall
clock, no randomness, no network, no model. Unknown rule ids fail closed.

The id list is validated against ``core.policy.schema.RULE_NAMES`` so a rule
can never be added to one side without the other noticing.
"""
from sheet_solution.sheets.rules import registry
from sheet_solution.sheets.rules.registry import (
    RULES,
    apply,
    numeric_ok,
    rule_ids,
)

__all__ = ["registry", "RULES", "apply", "numeric_ok", "rule_ids"]
