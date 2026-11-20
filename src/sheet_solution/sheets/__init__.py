"""Sheet Solution — sheets package.

The product-specific layer: the plain-English check template, the two
personas (auditor / verifier), embedded-image extraction, and the
deterministic check runner. Deterministic spine (hash chain, render,
verify, ingest, mapping) is inherited from `sheet_solution.core`.

No AI model in the check path. Image/semantic checks are flagged for a
named human and recorded in the audit log.
"""
from sheet_solution.sheets import (
    template, runner, report, images, compare, analyze, compatibility, rules,
    actions, decisions, metrics,
)

__all__ = [
    "template", "runner", "report", "images", "compare",
    "analyze", "compatibility", "rules", "actions", "decisions", "metrics",
]
