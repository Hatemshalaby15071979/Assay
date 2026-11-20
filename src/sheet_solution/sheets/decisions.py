"""The decision loop — a pure, fail-closed state machine.

This is the heart of "the machine never guesses, and when a proposed action
is denied it still offers ways to act and waits for a human". Every decision
walks an explicit path; there is no shortcut from a finding to an applied
change without a recorded human confirmation.

States::

    PROPOSED --approve(actor)--> APPROVED --apply(actor)--> APPLIED
        |                            |
        | decline(actor)             | decline(actor)
        v                            v
    DECLINED --re_propose(actor, action)--> PROPOSED  (offers an alternative)

Rules (all fail closed):
* only a human (a non-empty actor) may approve, decline or apply;
* APPLIED is terminal; an unknown/illegal transition raises DecisionError;
* declining never deletes the finding -- it re-opens with remaining options;
* when the human declines an option, `alternatives()` still returns the other
  declared options, so there is always a way to act; if none remain, the
  finding stays DECLINED with a flag_for_human path offered;
* nothing here touches the clock, randomness, the network or the filesystem.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from sheet_solution.core.errors import SignoffError
from sheet_solution.sheets.rules import registry as _rules

PROPOSED = "PROPOSED"
APPROVED = "APPROVED"
DECLINED = "DECLINED"
APPLIED = "APPLIED"
STATES = (PROPOSED, APPROVED, DECLINED, APPLIED)

# The always-available safe path: it changes no data, only asks a person to
# look. Offered when a human declines every declared option.
SAFE_FALLBACK = "flag_for_human"


class DecisionError(SignoffError):
    code = "DECISION_ERROR"


@dataclass(frozen=True)
class Finding:
    """One row-level problem the machine detected and cannot resolve alone."""

    finding_id: str
    check_id: str
    row_id: str
    column: str
    value: str
    detail: str

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id, "check_id": self.check_id,
            "row_id": self.row_id, "column": self.column,
            "value": self.value, "detail": self.detail,
        }


@dataclass(frozen=True)
class Decision:
    decision_id: str
    finding: Finding
    proposed_action: str
    options: tuple[str, ...]
    state: str = PROPOSED
    actor: str = ""
    note: str = ""
    applied_action: str = ""

    def to_dict(self) -> dict:
        """Deterministic projection. Actor/note are runtime ledger evidence."""
        return {
            "decision_id": self.decision_id,
            "finding": self.finding.to_dict(),
            "proposed_action": self.proposed_action,
            "options": list(self.options),
            "state": self.state,
            "applied_action": self.applied_action,
        }

    def alternatives(self) -> tuple[str, ...]:
        """Options still available to act with (never includes the declined one)."""
        if self.state == DECLINED:
            remaining = tuple(o for o in self.options if o != self.proposed_action)
            return remaining or (SAFE_FALLBACK,)
        return self.options


def decision_from_dict(data: dict) -> Decision:
    """Rebuild a Decision from its deterministic projection (actor/note excluded)."""
    f = data["finding"]
    finding = Finding(
        finding_id=f["finding_id"], check_id=f["check_id"], row_id=f["row_id"],
        column=f["column"], value=f["value"], detail=f["detail"],
    )
    return Decision(
        decision_id=data["decision_id"], finding=finding,
        proposed_action=data["proposed_action"], options=tuple(data["options"]),
        state=data.get("state", PROPOSED),
        applied_action=data.get("applied_action", ""),
    )


def propose(
    finding: Finding,
    options: tuple[str, ...],
    *,
    default_action: str = "",
) -> Decision:
    """Create a PROPOSED decision. At least one option is required."""
    if not options:
        raise DecisionError(f"finding {finding.finding_id}: no actions available to propose")
    chosen = default_action or options[0]
    if chosen not in options:
        raise DecisionError(
            f"finding {finding.finding_id}: default action {chosen!r} not in options")
    return Decision(
        decision_id=finding.finding_id, finding=finding,
        proposed_action=chosen, options=tuple(options), state=PROPOSED)


def _require_actor(actor: str) -> str:
    if not isinstance(actor, str) or not actor.strip():
        raise DecisionError("a named human actor is required to change a decision")
    return actor.strip()


def approve(decision: Decision, actor: str) -> Decision:
    """Human confirms the currently proposed action (PROPOSED/DECLINED -> APPROVED)."""
    actor = _require_actor(actor)
    if decision.state not in (PROPOSED, DECLINED):
        raise DecisionError(
            f"cannot approve a {decision.state} decision ({decision.decision_id})")
    return replace(decision, state=APPROVED, actor=actor,
                   note="human approved the proposed action")


def decline(decision: Decision, actor: str, reason: str = "") -> Decision:
    """Human denies the action. Fail closed: it is NOT applied; re-open with options."""
    actor = _require_actor(actor)
    if decision.state not in (PROPOSED, APPROVED):
        raise DecisionError(
            f"cannot decline a {decision.state} decision ({decision.decision_id})")
    return replace(decision, state=DECLINED, actor=actor,
                   note=reason or "human declined the proposed action; alternatives offered")


def re_propose(decision: Decision, actor: str, action: str) -> Decision:
    """Offer a different action after a denial (DECLINED -> PROPOSED)."""
    actor = _require_actor(actor)
    if decision.state != DECLINED:
        raise DecisionError(
            f"can only re-propose a declined decision ({decision.decision_id})")
    if action != SAFE_FALLBACK and action not in decision.alternatives():
        raise DecisionError(
            f"action {action!r} is not an available alternative for {decision.decision_id}")
    new_options = tuple(dict.fromkeys((*decision.options, action)))
    return replace(decision, state=PROPOSED, proposed_action=action,
                   options=new_options, actor=actor,
                   note="human chose an alternative to act with")


def mark_applied(decision: Decision, actor: str) -> Decision:
    """Record that the approved action was applied (APPROVED -> APPLIED, terminal)."""
    actor = _require_actor(actor)
    if decision.state != APPROVED:
        raise DecisionError(
            f"only an APPROVED decision can be applied ({decision.decision_id} is "
            f"{decision.state}); a proposal or denial is never applied")
    return replace(decision, state=APPLIED, actor=actor,
                   applied_action=decision.proposed_action,
                   note="approved action applied and recorded")


def apply_ok(decision: Decision) -> bool:
    """An action may be executed only after explicit approval."""
    return decision.state == APPROVED


# --- proposals from a policy + check results --------------------------------
def finding_id(check_id: str, row_id: str, column: str) -> str:
    from sheet_solution.core.engine.hash_chain import sha256_text
    raw = f"{check_id}\x1f{row_id}\x1f{column}"
    return "F-" + sha256_text(raw)[:16]


def build_findings(
    results: list[dict],
    policy_checks: dict,
    *,
    fallback_action: str = SAFE_FALLBACK,
) -> list[Decision]:
    """Turn failed check results into fail-closed PROPOSED decisions.

    `results` are rows from ``check-results.csv`` (dicts with at least
    ``check_id``, ``outcome``, ``failed_row_ids``). `policy_checks` maps a
    check id to a validated policy ``PolicyCheck``. Every failing row becomes
    a decision whose options are the policy's declared on_fail actions; if the
    policy declared none, the safe flag_for_human path is offered so the human
    always has a way to act. No action is applied here.
    """
    decisions: list[Decision] = []
    for result in results:
        if str(result.get("outcome", "")).upper() != "FAIL":
            continue
        cid = str(result.get("check_id", ""))
        pc = policy_checks.get(cid)
        column = getattr(pc, "column", "") if pc is not None else ""
        declared = tuple(getattr(getattr(pc, "on_fail", None), "actions", ()) or ()) if pc else ()
        options = declared or (fallback_action,)
        row_ids = [r for r in str(result.get("failed_row_ids", "")).split(";") if r]
        for row_id in row_ids:
            fid = finding_id(cid, row_id, column)
            finding = Finding(
                finding_id=fid, check_id=cid, row_id=row_id, column=column,
                value="", detail=str(result.get("detail", "")))
            decisions.append(propose(finding, options))
    return decisions
