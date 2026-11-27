"""Assay — offline, deterministic, auditable sheet-audit platform.

Rebranded from the Signoff 0.1.0 spine (see docs/archive/PROVENANCE.md). Runs on any
hardware, fully offline: no network, no cloud, no AI model in the check
path. Structured checks are deterministic; image/semantic checks are
flagged for a named human and recorded in the audit log.
"""

__version__ = "0.4.0"

# Re-export the core config at the package root so `from sheet_solution import
# config` resolves for the test suite and operators. The real module is
# `sheet_solution.core.config` (inherited, unchanged from Signoff 0.1.0).
from sheet_solution.core import config  # noqa: E402
