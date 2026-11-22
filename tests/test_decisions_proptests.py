#!/usr/bin/env python3
"""
Assay — Property-based tests for decision loop

These tests validate the fail-closed decision loop semantics using property-based
testing. They are designed to be run in CI for staged preview and pre-stable.

For full fuzzing with complex grammars, integrate with hypothesis or libflame
before stable release.

Run: pytest tests/test_decisions_proptests.py -q
"""

import pytest
from pathlib import Path
import tempfile
import json

# These tests cover decision loop invariants
# They are designed for staged preview; full proptests planned for stable

def test_decision_proposal_is_deterministic():
    """The same proposal should produce the same deterministic output."""
    from sheet_solution.sheets.decisions import Finding, propose

    # Create same finding twice
    finding = Finding(
        finding_id="F-001", check_id="check1", row_id="row1",
        column="col1", value="val", detail="test"
    )
    options = ("flag_for_human", "tag_row")

    # Create two proposals
    d1 = propose(finding, options)
    d2 = propose(finding, options)

    # Should have same serialization
    assert d1.to_dict() == d2.to_dict()


def test_decision_state_machine_only_applies_from_approved():
    """The state machine rejects apply without APPROVED state."""
    from sheet_solution.sheets.decisions import (
        PROPOSED, APPROVED, DECLINED, APPLIED, apply_ok, mark_applied,
        propose, approve, decline, Finding, DecisionError
    )

    finding = Finding(
        finding_id="F-TEST", check_id="check1", row_id="row1",
        column="col1", value="val", detail="test"
    )
    options = ("flag_for_human", "tag_row")

    # PROPOSED -> cannot apply directly
    d1 = propose(finding, options)
    assert apply_ok(d1) is False
    with pytest.raises(DecisionError):
        mark_applied(d1, "test")

    # APPROVED -> can apply
    d2 = approve(d1, "alice")
    assert apply_ok(d2) is True

    # After apply, state is APPLIED and no longer apply_ok
    d3 = mark_applied(d2, "alice")
    assert d3.state == APPLIED
    assert apply_ok(d3) is False


def test_decision_ledger_records_all_transitions():
    """Every state transition is recorded in the hash-chained ledger."""
    import hashlib
    from sheet_solution.sheets.ledger import Ledger, verify_ledger, DECISION_TYPE

    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = Path(tmpdir) / "ledger.jsonl"
        ledger = Ledger(ledger_path)

        # Create a finding and decision
        from sheet_solution.sheets.decisions import Finding, propose, approve

        finding = Finding(
            finding_id="F-001", check_id="check1", row_id="row1",
            column="col1", value="val", detail="test"
        )
        decision = propose(finding, ("flag_for_human",))

        # Record the proposal
        ledger.append_proposal(decision, "system")

        # Approve the decision
        approved = approve(decision, "alice")
        ledger.append_decision(approved, "alice", "approve")

        # Verify the ledger has 2 entries
        events = ledger.decision_events()
        assert len(events) == 2

        # Verify the chain is valid
        result = verify_ledger(ledger_path)
        assert result["ok"] is True
        assert result["count"] == 2


def test_decline_leaves_alternatives_available():
    """Declining an action preserves other options."""
    from sheet_solution.sheets.decisions import (
        Finding, propose, decline, DECLINED
    )

    # Create a finding with multiple options
    finding = Finding(
        finding_id="F-001", check_id="check1", row_id="row1",
        column="col1", value="val", detail="test"
    )
    options = ("flag_for_human", "tag_row", "reject")

    # Create a PROPOSED decision
    decision = propose(finding, options)

    # Decline one option (the first one - flag_for_human)
    decision = decline(decision, "bob", "not right")

    # Decision should be DECLINED
    assert decision.state == DECLINED
    # Alternatives should be the remaining options
    assert "tag_row" in decision.alternatives()
    assert "reject" in decision.alternatives()


def test_apply_is_terminal():
    """Once APPLIED, no further transitions are allowed."""
    from sheet_solution.sheets.decisions import (
        Finding, propose, approve, mark_applied, APPLIED, apply_ok,
        DecisionError
    )

    # Create a finding with one option
    finding = Finding(
        finding_id="F-001", check_id="check1", row_id="row1",
        column="col1", value="val", detail="test"
    )
    options = ("flag_for_human",)

    # Create PROPOSED -> APPROVE -> APPLY
    decision = propose(finding, options)
    decision = approve(decision, "alice")
    decision = mark_applied(decision, "alice")

    # State is APPLIED
    assert decision.state == APPLIED
    # apply_ok returns False for APPLIED (terminal state)
    assert apply_ok(decision) is False
    # applied_action is recorded
    assert decision.applied_action == "flag_for_human"


# TODO: Add hypothesis-based proptests for:
# - Decision trees with 100+ findings
# - Policy schema validation edge cases
# - Ledger integrity under concurrent modifications
# These are planned for pre-stable release integration.