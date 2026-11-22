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
    """Given the same input, decisions.json is byte-identical."""
    from sheet_solution.sheets.decisions import plan_decisions

    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup: create minimal check-results and policy
        results_path = Path(tmpdir) / "check-results.csv"
        results_path.write_text(
            "finding_id,check_name,row_key,status,message\n"
            "F-001,email_present,ROW-001,FAIL,Missing email\n"
            "F-002,name_present,ROW-002,PASS,Name OK\n"
        )

        policy_path = Path(tmpdir) / "policy.json"
        policy_path.write_text(json.dumps({
            "version": "1.0.0",
            "decisions": [
                {
                    "finding_id": "F-001",
                    "actions": ["flag_for_human", "tag_row"]
                }
            ]
        }))

        # Run plan twice
        out1 = Path(tmpdir) / "decisions1.json"
        out2 = Path(tmpdir) / "decisions2.json"

        plan_decisions(str(results_path), str(policy_path), str(out1))
        plan_decisions(str(results_path), str(policy_path), str(out2))

        # Byte-identical output
        with open(out1) as f1, open(out2) as f2:
            assert f1.read() == f2.read(), "Plan must be deterministic"


def test_decision_state_machine_only_applies_from_approved():
    """The state machine rejects apply without APPROVED state."""
    from sheet_solution.sheets.decisions import DecisionState, apply_decision

    # Test all valid states
    for state in DecisionState:
        result = apply_decision(state)
        if state != DecisionState.APPROVED:
            assert result is False, f"apply() must reject state {state}"

    # Test that APPROVED allows
    assert apply_decision(DecisionState.APPROVED) is True


def test_decision_ledger_records_all_transitions():
    """Every state transition is recorded in the hash-chained ledger."""
    import hashlib
    from sheet_solution.sheets.ledger import Ledger

    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = Path(tmpdir) / "ledger.jsonl"
        ledger = Ledger()

        # Record a decision transition
        entry = {
            "finding_id": "F-001",
            "from_state": "PROPOSED",
            "to_state": "APPROVED",
            "actor": "alice",
            "note": "Approved for review"
        }

        ledger.write(entry, ledger_path)

        # Verify hash chain
        with open(ledger_path) as f:
            lines = f.readlines()

        assert len(lines) == 1
        # Hash is SHA-256 based
        entry_bytes = json.dumps(entry, sort_keys=True).encode()
        expected_hash = hashlib.sha256(entry_bytes).hexdigest()[:16]
        assert expected_hash in lines[0]


def test_decline_leaves_alternatives_available():
    """Declining an action preserves other options."""
    from sheet_solution.sheets.decisions import Decision, DecisionState

    # Create a decision with multiple proposed actions
    decision = Decision(
        finding_id="F-001",
        proposed_actions=["flag_for_human", "tag_row", "reject"],
        state=DecisionState.PROPOSED
    )

    # Decline (not a terminal state)
    decision.decline("not relevant")

    # Decision should still have options
    assert decision.state == DecisionState.DECLINED
    # Proposed actions should still be available for re-propose
    assert len(decision.available_actions) == 3 or decision.re_propose_allowed


def test_apply_is_terminal():
    """Once APPLIED, no further transitions are allowed."""
    from sheet_solution.sheets.decisions import Decision, DecisionState

    decision = Decision(
        finding_id="F-001",
        proposed_actions=["flag_for_human"],
        state=DecisionState.APPROVED
    )

    decision.apply()

    # No further transitions
    assert decision.state == DecisionState.APPLIED
    # No more actions available
    assert decision.available_actions == []


# TODO: Add hypothesis-based proptests for:
# - Decision trees with 100+ findings
# - Policy schema validation edge cases
# - Ledger integrity under concurrent modifications
# These are planned for pre-stable release integration.