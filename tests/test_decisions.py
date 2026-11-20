"""Phase C — fail-closed decision loop and named action executors."""
from __future__ import annotations

import pytest

from sheet_solution.sheets.actions import apply_action
from sheet_solution.sheets.ledger import Ledger, LedgerError
from sheet_solution.core.errors import ConfigError
from sheet_solution.core.policy.schema import ACTION_NAMES
from sheet_solution.sheets import actions, decisions
from sheet_solution.sheets.decisions import (
    APPROVED, APPLIED, DECLINED, PROPOSED, SAFE_FALLBACK,
    DecisionError, Finding,
)


def _finding(fid: str = "F-1", col: str = "qa_score") -> Finding:
    return Finding(fid, "CH-1", "r2", col, "0", "failed check")


# --- action registry --------------------------------------------------------
def test_action_ids_match_policy_schema():
    assert set(actions.action_ids()) == set(ACTION_NAMES)


def test_unknown_action_fails_closed():
    with pytest.raises(ConfigError):
        actions.apply_action("delete_everything", {})


def test_named_actions_are_pure_row_transforms():
    assert actions.apply_action("tag_row", {"id": "1"},
                                {"column": "status", "value": "fixed"}).row["status"] == "fixed"
    assert actions.apply_action("flag_for_human", {"id": "1"}).row["__needs_human"] == "yes"
    assert actions.apply_action("emit_corrected_copy", {"id": "1"}).row["__corrected"] == "yes"
    assert actions.apply_action("escalate", {"id": "1"}).row["__escalated"] == "yes"
    drop = actions.apply_action("drop_row", {"id": "1"}, {"note": "bad row"})
    assert drop.drop is True and drop.note == "bad row"


def test_action_does_not_mutate_input_row():
    row = {"id": "1"}
    actions.apply_action("tag_row", row, {"column": "x", "value": "y"})
    assert row == {"id": "1"}


# --- propose ----------------------------------------------------------------
def test_propose_requires_an_option():
    with pytest.raises(DecisionError):
        decisions.propose(_finding(), ())


def test_propose_rejects_unknown_default():
    with pytest.raises(DecisionError):
        decisions.propose(_finding(), ("tag_row",), default_action="drop_row")


def test_propose_starts_in_proposed_state():
    d = decisions.propose(_finding(), ("tag_row", "flag_for_human"))
    assert d.state == PROPOSED
    assert d.proposed_action == "tag_row"
    assert d.alternatives() == ("tag_row", "flag_for_human")


# --- approve / actor --------------------------------------------------------
def test_transitions_require_a_named_actor():
    d = decisions.propose(_finding(), ("tag_row",))
    for bad in ("", "   ", None):
        with pytest.raises(DecisionError):
            decisions.approve(d, bad)


def test_approve_moves_proposed_to_approved():
    d = decisions.propose(_finding(), ("tag_row",))
    approved = decisions.approve(d, "alice")
    assert approved.state == APPROVED
    assert approved.actor == "alice"
    assert decisions.apply_ok(approved) is True


def test_apply_gate_closed_without_approval():
    d = decisions.propose(_finding(), ("tag_row",))
    assert decisions.apply_ok(d) is False
    with pytest.raises(DecisionError):
        decisions.mark_applied(d, "alice")


# --- decline is fail closed -------------------------------------------------
def test_declined_decision_is_never_applicable():
    d = decisions.propose(_finding(), ("tag_row", "flag_for_human"))
    declined = decisions.decline(d, "alice", "too risky")
    assert declined.state == DECLINED
    assert decisions.apply_ok(declined) is False
    with pytest.raises(DecisionError):
        decisions.mark_applied(declined, "alice")
    assert declined.applied_action == ""


def test_decline_keeps_remaining_options():
    d = decisions.propose(_finding(), ("tag_row", "flag_for_human", "escalate"))
    declined = decisions.decline(d, "alice")
    assert "tag_row" not in declined.alternatives()
    assert declined.alternatives() == ("flag_for_human", "escalate")


def test_decline_everything_still_offers_safe_fallback():
    d = decisions.propose(_finding(), ("tag_row",))
    declined = decisions.decline(d, "alice")
    assert declined.alternatives() == (SAFE_FALLBACK,)


def test_re_propose_from_decline_with_alternative():
    d = decisions.propose(_finding(), ("tag_row", "flag_for_human"))
    declined = decisions.decline(d, "alice")
    reopened = decisions.re_propose(declined, "bob", SAFE_FALLBACK)
    assert reopened.state == PROPOSED
    assert reopened.proposed_action == SAFE_FALLBACK
    assert decisions.apply_ok(reopened) is False  # still needs approval


def test_re_propose_rejects_declined_action():
    d = decisions.propose(_finding(), ("tag_row", "flag_for_human"))
    declined = decisions.decline(d, "alice")
    with pytest.raises(DecisionError):
        decisions.re_propose(declined, "bob", "tag_row")


def test_re_propose_only_from_declined():
    d = decisions.propose(_finding(), ("tag_row", "flag_for_human"))
    with pytest.raises(DecisionError):
        decisions.re_propose(d, "bob", SAFE_FALLBACK)


# --- apply / terminal state -------------------------------------------------
def test_approve_then_apply_is_terminal():
    d = decisions.propose(_finding(), ("flag_for_human",))
    approved = decisions.approve(d, "alice")
    applied = decisions.mark_applied(approved, "carol")
    assert applied.state == APPLIED
    assert applied.applied_action == "flag_for_human"
    with pytest.raises(DecisionError):
        decisions.approve(applied, "alice")
    with pytest.raises(DecisionError):
        decisions.decline(applied, "alice")


def test_decline_after_approval_is_allowed_but_never_applied():
    d = decisions.propose(_finding(), ("tag_row", "flag_for_human"))
    approved = decisions.approve(d, "alice")
    declined = decisions.decline(approved, "alice", "changed my mind")
    assert declined.state == DECLINED
    assert decisions.apply_ok(declined) is False


# --- build findings from check results --------------------------------------
class _OnFail:
    def __init__(self, acts):
        self.actions = tuple(acts)


class _Check:
    def __init__(self, column, acts):
        self.column = column
        self.on_fail = _OnFail(acts)


def test_build_findings_from_failed_results():
    results = [
        {"check_id": "CH-1", "outcome": "FAIL", "failed_row_ids": "r2;r4",
         "detail": "blank"},
        {"check_id": "CH-2", "outcome": "PASS", "failed_row_ids": "", "detail": ""},
    ]
    checks = {"CH-1": _Check("qa_score", ("tag_row", "flag_for_human"))}
    found = decisions.build_findings(results, checks)
    assert len(found) == 2
    assert all(d.state == PROPOSED for d in found)
    assert all(d.proposed_action == "tag_row" for d in found)
    assert {d.finding.row_id for d in found} == {"r2", "r4"}


def test_build_findings_offers_fallback_when_policy_has_no_actions():
    results = [{"check_id": "CH-9", "outcome": "FAIL", "failed_row_ids": "r1"}]
    found = decisions.build_findings(results, {})
    assert len(found) == 1
    assert found[0].options == (SAFE_FALLBACK,)


def test_finding_id_is_deterministic():
    a = decisions.finding_id("CH-1", "r2", "qa_score")
    b = decisions.finding_id("CH-1", "r2", "qa_score")
    c = decisions.finding_id("CH-1", "r3", "qa_score")
    assert a == b and a.startswith("F-") and a != c


# --- deterministic projection ----------------------------------------------
def test_decision_to_dict_excludes_runtime_evidence():
    d = decisions.approve(decisions.propose(_finding(), ("tag_row",)), "alice")
    data = d.to_dict()
    assert "actor" not in data and "note" not in data
    assert data["state"] == APPROVED
    assert data["finding"]["finding_id"] == "F-1"


# --- ledger decision evidence ----------------------------------------------
def _ledger(tmp_path):
    return Ledger(tmp_path / "ledger.jsonl", clock=lambda: "2026-11-20T00:00:00+00:00")


def test_ledger_records_full_decision_lifecycle(tmp_path):
    led = _ledger(tmp_path)
    d = decisions.propose(_finding(), ("tag_row", "flag_for_human"))
    led.append_proposal(d)
    declined = decisions.decline(d, "alice")
    led.append_decision(declined, "alice", "decline")
    reopened = decisions.re_propose(declined, "bob", SAFE_FALLBACK)
    led.append_decision(reopened, "bob", "re_propose")
    approved = decisions.approve(reopened, "carol")
    led.append_decision(approved, "carol", "approve")
    applied = decisions.mark_applied(approved, "carol")
    result = apply_action(applied.applied_action, {"qa_score": "0"})
    led.append_application(applied, "carol", result)

    events = led.decision_events()
    assert [e["type"] for e in events] == [
        "decision.proposed", "decision.recorded", "decision.recorded",
        "decision.recorded", "decision.applied",
    ]
    assert led.verify() is True
    assert [e["actor"] for e in events] == ["system", "alice", "bob", "carol", "carol"]


def test_ledger_rejects_invalid_decision_events(tmp_path):
    led = _ledger(tmp_path)
    d = decisions.propose(_finding(), ("tag_row",))
    with pytest.raises(LedgerError):
        led.append_proposal({"not": "a decision"})
    with pytest.raises(LedgerError):
        led.append_decision(d, "", "approve")
    with pytest.raises(LedgerError):
        led.append_application(d, "alice", apply_action("tag_row", {}))


# --- CLI end-to-end (file-first policy, fail-closed loop) -------------------
import argparse

from sheet_solution.cli import cmd_decisions
from sheet_solution.core.errors import SignoffError


def _pack(tmp_path, policy_actions='["tag_row","flag_for_human"]'):
    """Create a run pack with a failing check result + a declaring policy."""
    out = tmp_path / "pack"
    out.mkdir()
    (out / "check-results.csv").write_text(
        "check_id,label,outcome,matched_rows,failed_rows,denominator,failed_row_ids,detail\n"
        "CH-1,qa,FAIL,2,1,2,r2,blank\n",
        encoding="utf-8")
    policy = tmp_path / "policy.json"
    policy.write_text(
        '{"version":1,'
        '"defaults":{"on_unresolved":"propose","confirm_required":true},'
        '"checks":[{"id":"CH-1","column":"qa_score","rule":"not_blank",'
        '"params":{},"severity":"high",'
        '"on_fail":{"actions":' + policy_actions + ',"confirm_required":true}}]}',
        encoding="utf-8")
    return out, policy


def _args(op, out, **kw):
    defaults = dict(
        decision_action=op, out=str(out), policy="", sheet_name="",
        check_results="", finding_id="", action="", action_id="",
        actor="", reason="",
    )
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def _one_decision(out):
    import json
    return json.loads((out / "decisions.json").read_text(encoding="utf-8"))[0]


def test_cli_plan_builds_proposals_from_results_and_policy(tmp_path):
    out, policy = _pack(tmp_path)
    assert cmd_decisions(_args("plan", out, policy=str(policy))) == 0
    data = _one_decision(out)
    assert data["state"] == PROPOSED
    assert data["options"] == ["tag_row", "flag_for_human"]
    assert data["finding"]["row_id"] == "r2"
    led = Ledger(out / ".audit" / "ledger.jsonl")
    assert [e["type"] for e in led.decision_events()] == ["decision.proposed"]
    assert led.verify() is True


def test_cli_apply_requires_approval_and_actor(tmp_path):
    out, policy = _pack(tmp_path)
    cmd_decisions(_args("plan", out, policy=str(policy)))
    fid = _one_decision(out)["decision_id"]

    # apply before approval is refused; no corrected copy is produced.
    with pytest.raises(SignoffError):
        cmd_decisions(_args("decide", out, finding_id=fid, action="apply", actor="alice"))
    assert not (out / "corrected-copy.jsonl").exists()

    # actor is mandatory for approve.
    with pytest.raises(SignoffError):
        cmd_decisions(_args("decide", out, finding_id=fid, action="approve"))


def test_cli_deny_then_alternative_then_apply(tmp_path):
    out, policy = _pack(tmp_path)
    cmd_decisions(_args("plan", out, policy=str(policy)))
    fid = _one_decision(out)["decision_id"]

    # Deny -> fallback offered, nothing applied.
    cmd_decisions(_args("decide", out, finding_id=fid, action="decline",
                        actor="alice", reason="risky"))
    assert _one_decision(out)["state"] == DECLINED
    assert not (out / "corrected-copy.jsonl").exists()

    # Re-propose the safe fallback -> still needs approval.
    cmd_decisions(_args("decide", out, finding_id=fid, action="re-propose",
                        actor="bob", action_id=SAFE_FALLBACK))
    assert _one_decision(out)["proposed_action"] == SAFE_FALLBACK

    cmd_decisions(_args("decide", out, finding_id=fid, action="approve", actor="carol"))
    assert _one_decision(out)["state"] == APPROVED
    assert not (out / "corrected-copy.jsonl").exists()  # still not applied

    cmd_decisions(_args("decide", out, finding_id=fid, action="apply", actor="carol"))
    assert _one_decision(out)["state"] == APPLIED
    copy = (out / "corrected-copy.jsonl").read_text(encoding="utf-8")
    assert SAFE_FALLBACK in copy

    led = Ledger(out / ".audit" / "ledger.jsonl")
    types = [e["type"] for e in led.decision_events()]
    assert "decision.applied" in types
    assert led.verify() is True
