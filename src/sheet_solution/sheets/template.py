"""Sheet Solution — check-template config engine.

Users (non-technical) fill a plain-English template. This module turns
that template into a structured, validated CheckConfig and REFUSES to
produce one on ambiguity or missing fields (fail-closed).

The template is a flat, human-readable text file:

    # one [CHECK] block per thing the user looks for

    [CHECK]
    check_id = CHECK-001
    what_is_this_check_for = Passport photo attached
    what_to_look_at = photo column, one photo per applicant row
    expected_value_or_rule = a photo exists for every applicant (no blank)
    when_it_fails_say = No passport photo for this applicant
    machine_can_check = yes
    example_that_passes = applicant row with a photo in the cell
    example_that_fails = applicant row with an empty photo cell

The user never sees YAML/JSON. The engine validates every field and the
two examples must be internally consistent with the rule.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from sheet_solution.core.errors import ConfigError

# ---------------------------------------------------------------------------
# Required fields, in plain-English names (the labels users actually read).
# ---------------------------------------------------------------------------
REQUIRED_FIELDS = (
    "check_id",
    "what_is_this_check_for",
    "what_to_look_at",
    "expected_value_or_rule",
    "when_it_fails_say",
    "machine_can_check",
)

# Optional fields a user may add. example_* are optional: they help the user
# think through their rule but the engine never uses them, so forcing them
# was pure friction for non-technical users.
OPTIONAL_FIELDS = (
    "tolerance",
    "column_name",
    "row_key_column",
    "human_review_note",
    "example_that_passes",
    "example_that_fails",
)

# Optional fields a user may add.


MACHINE_CHECK_VALUES = {"yes", "no"}

_BLOCK_HEADER = re.compile(r"^\[CHECK\]\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Check:
    """One validated check block."""
    check_id: str
    what_is_this_check_for: str
    what_to_look_at: str
    expected_value_or_rule: str
    when_it_fails_say: str
    machine_can_check: bool
    example_that_passes: str = ""
    example_that_fails: str = ""
    tolerance: str = ""
    column_name: str = ""
    row_key_column: str = ""
    human_review_note: str = ""

    @property
    def needs_human(self) -> bool:
        return not self.machine_can_check


@dataclass
class CheckConfig:
    """A validated set of checks plus the persona the user is acting as."""
    persona: str                 # "auditor" | "verifier"
    sheet_path: str
    checks: list[Check] = field(default_factory=list)

    def check_ids(self) -> list[str]:
        return [c.check_id for c in self.checks]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def _split_blocks(text: str) -> list[str]:
    parts = _BLOCK_HEADER.split(text)
    # Element 0 is the preamble (free text before the first [CHECK]); each
    # subsequent element starts with its [CHECK] block. Drop empty pieces and
    # any piece with no key/value content (a stray [CHECK] with nothing under it).
    blocks: list[str] = []
    for part in parts:
        kv_present = "=" in part and any(
            ln.strip().startswith("check_id") or re.match(r"^\w+\s*=", ln.strip())
            for ln in part.splitlines() if ln.strip())
        if part.strip() and kv_present:
            blocks.append(part)
    return blocks


def _parse_kv(block: str) -> dict[str, str]:
    kv: dict[str, str] = {}
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue  # continuation of a multi-line value belongs to prior key
        key, _, value = stripped.partition("=")
        kv[key.strip().lower()] = value.strip()
    return kv


def parse_template(path: Path, sheet_path: str) -> CheckConfig:
    """Read the plain-English template and return a validated CheckConfig."""
    text = Path(path).read_text(encoding="utf-8-sig")
    blocks = _split_blocks(text)
    if not blocks:
        raise ConfigError(
            "no [CHECK] blocks found in the template. Add at least one "
            "[CHECK] section describing what to look for.")

    checks: list[Check] = []
    seen_ids: set[str] = set()
    for block in blocks:
        kv = _parse_kv(block)
        missing = [f for f in REQUIRED_FIELDS if not kv.get(f, "").strip()]
        if missing:
            raise ConfigError(
                f"check block starting at {block.strip()[:40]!r}... is missing "
                f"required field(s): {', '.join(missing)}. Every field in the "
                "template is required — fill each one in plain English.")
        check_id = kv["check_id"].strip()
        if check_id in seen_ids:
            raise ConfigError(f"duplicate check_id {check_id!r} — each check needs a unique id")
        seen_ids.add(check_id)
        machine = kv["machine_can_check"].strip().lower()
        if machine not in MACHINE_CHECK_VALUES:
            raise ConfigError(
                f"check {check_id}: machine_can_check must be 'yes' or 'no', "
                f"got {kv['machine_can_check']!r}")
        checks.append(Check(
            check_id=check_id,
            what_is_this_check_for=kv["what_is_this_check_for"].strip(),
            what_to_look_at=kv["what_to_look_at"].strip(),
            expected_value_or_rule=kv["expected_value_or_rule"].strip(),
            when_it_fails_say=kv["when_it_fails_say"].strip(),
            machine_can_check=(machine == "yes"),
            example_that_passes=kv.get("example_that_passes", "").strip(),
            example_that_fails=kv.get("example_that_fails", "").strip(),
            tolerance=kv.get("tolerance", "").strip(),
            column_name=kv.get("column_name", "").strip(),
            row_key_column=kv.get("row_key_column", "").strip(),
            human_review_note=kv.get("human_review_note", "").strip(),
        ))

    persona = _infer_persona(checks)
    return CheckConfig(persona=persona, sheet_path=sheet_path, checks=checks)


def _infer_persona(checks: list[Check]) -> str:
    """verifier if any check asserts an expected value must be present;
    auditor otherwise (a pass/fail against a standard)."""
    for c in checks:
        text = c.expected_value_or_rule.lower()
        if any(k in text for k in ("present", "must contain", "includes",
                                   "listed", "must equal", "equals", "is listed")):
            return "verifier"
    return "auditor"


# ---------------------------------------------------------------------------
# Self-check loop (the "not a toy" feature): prove the config back to the user.
# ---------------------------------------------------------------------------
def config_echo(config: CheckConfig) -> str:
    """Plain-English confirmation of what the user actually configured."""
    lines = [f"persona: {config.persona}", f"sheet: {config.sheet_path}",
             f"checks: {len(config.checks)}"]
    for c in config.checks:
        mode = "machine" if c.machine_can_check else "HUMAN REVIEW"
        lines.append(f"  - {c.check_id} [{mode}] {c.what_is_this_check_for}")
    return "\n".join(lines)
