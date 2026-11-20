"""Durable intent/result ledger: chain, recovery, anchoring, CLI integration."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from tests.conftest import REPO

from sheet_solution.cli import cmd_compare, cmd_run, cmd_verify
from sheet_solution.core.errors import SignoffError
from sheet_solution.sheets.ledger import Ledger, LedgerError, verify_ledger


def _fixed_clock() -> str:
    return "2026-11-20T00:00:00+00:00"


def _ledger(tmp_path: Path, name: str = "ledger.jsonl") -> Ledger:
    return Ledger(tmp_path / name, clock=_fixed_clock)


def _events(ledger: Ledger) -> list[dict]:
    return ledger.tail(10**9)


def test_missing_ledger_verifies_as_empty(tmp_path):
    result = verify_ledger(tmp_path / "absent.jsonl")
    assert result["ok"] is True
    assert result["count"] == 0
    assert result["head"] == "GENESIS"


def test_append_and_verify_chain(tmp_path):
    ledger = _ledger(tmp_path)
    first = ledger.append("run.intent", "cli", {"n": 1})
    second = ledger.append("run.completed", "cli", {"n": 2})
    assert first["seq"] == 1 and second["seq"] == 2
    assert second["prev_hash"] == first["hash"]
    result = verify_ledger(ledger.path)
    assert result["ok"] is True
    assert result["count"] == 2


def test_tampered_payload_is_detected(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.append("run.completed", "cli", {"ok": True})
    entry = json.loads(ledger.path.read_text(encoding="utf-8").splitlines()[0])
    entry["payload"]["ok"] = False
    ledger.path.write_text(json.dumps(entry, sort_keys=True) + "\n", encoding="utf-8")
    result = verify_ledger(ledger.path)
    assert result["ok"] is False
    assert result["reason"] == "bad_hash"


def test_broken_prev_hash_is_detected(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.append("a", "cli", {})
    ledger.append("b", "cli", {})
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    second = json.loads(lines[1])
    second["prev_hash"] = "0" * 64
    lines[1] = json.dumps(second, sort_keys=True)
    ledger.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = verify_ledger(ledger.path)
    assert result["ok"] is False
    assert result["reason"] == "chain_break"


def test_intent_result_pairing(tmp_path):
    ledger = _ledger(tmp_path)
    intent = ledger.append_intent("run", "cli", {"sheet": "s.xlsx"})
    result = ledger.append_result(intent, "run.completed", "cli", {"checks": 4})
    assert result["payload"]["intent_seq"] == intent["seq"]
    assert result["payload"]["intent_hash"] == intent["hash"]
    assert ledger.pending_intents() == []


def test_pending_intent_is_recoverable_after_interruption(tmp_path):
    ledger = _ledger(tmp_path)
    intent = ledger.append_intent("run", "cli", {"sheet": "s.xlsx"})
    # Simulate the process dying before append_result: reopen and inspect.
    reopened = _ledger(tmp_path)
    pending = reopened.pending_intents()
    assert [event["seq"] for event in pending] == [intent["seq"]]
    assert reopened.verify() is True


def test_append_result_requires_an_intent(tmp_path):
    ledger = _ledger(tmp_path)
    not_an_intent = ledger.append("run.completed", "cli", {})
    with pytest.raises(LedgerError):
        ledger.append_result(not_an_intent, "run.completed", "cli", {})


def test_append_refuses_a_broken_chain(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.append("a", "cli", {})
    ledger.path.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(LedgerError):
        ledger.append("b", "cli", {})


def test_anchor_and_check_anchor(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.append("a", "cli", {})
    receipt = ledger.anchor()
    assert receipt["provider"] == "local"
    assert receipt["prev_anchor_hash"] == "GENESIS"
    assert ledger.check_anchor()["ok"] is True


def test_anchor_detects_truncation(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.append("a", "cli", {})
    ledger.append("b", "cli", {})
    ledger.anchor()
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    ledger.path.write_text(lines[0] + "\n", encoding="utf-8")
    result = ledger.check_anchor()
    assert result["ok"] is False
    assert result["reason"] == "truncated"


def test_anchor_detects_rewrite(tmp_path):
    original = _ledger(tmp_path, "original.jsonl")
    original.append("run.completed", "cli", {"value": "original"})
    original.anchor()

    replacement = _ledger(tmp_path, "replacement.jsonl")
    replacement.append("run.completed", "cli", {"value": "replacement"})
    replacement_line = replacement.path.read_text(encoding="utf-8").splitlines()[0]

    original.path.write_text(replacement_line + "\n", encoding="utf-8")
    result = original.check_anchor()
    assert result["ok"] is False
    assert result["reason"] == "rewritten"


def test_anchor_receipt_tamper_is_detected(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.append("a", "cli", {})
    receipt = ledger.anchor()
    path = tmp_path / "anchors" / f"anchor-{receipt['seq']:08d}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["head_hash"] = "0" * 64
    path.write_text(json.dumps(data), encoding="utf-8")
    result = ledger.check_anchor()
    assert result["ok"] is False
    assert result["reason"] == "anchor_tampered"


def _run_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        sheet=str(REPO / "examples" / "example-sheet.xlsx"),
        template=str(REPO / "examples" / "check-template.example.txt"),
        out=str(tmp_path / "out"),
        key=None,
    )


def test_cmd_run_records_intent_and_result(tmp_path):
    assert cmd_run(_run_args(tmp_path)) == 0
    ledger_path = tmp_path / "out" / ".audit" / "ledger.jsonl"
    events = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    assert events[0]["type"] == "action.intent"
    assert events[-1]["type"] == "run.completed"
    assert events[-1]["payload"]["intent_seq"] == events[0]["seq"]
    assert events[-1]["payload"]["artifacts"]["check-results.csv"]
    assert verify_ledger(ledger_path)["ok"] is True
    assert Ledger(ledger_path).pending_intents() == []


def test_cmd_run_failure_records_failed_result(tmp_path):
    bad_template = tmp_path / "bad.txt"
    bad_template.write_text("not a template\n", encoding="utf-8")
    args = _run_args(tmp_path)
    args.template = str(bad_template)
    with pytest.raises(SignoffError):
        cmd_run(args)
    ledger_path = tmp_path / "out" / ".audit" / "ledger.jsonl"
    events = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    assert events[-1]["type"] == "run.failed"
    assert Ledger(ledger_path).pending_intents() == []


def test_cmd_compare_records_intent_and_result(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("id,amount\n1,100\n2,200\n", encoding="utf-8")
    b.write_text("id,amount\n1,100\n2,250\n3,5\n", encoding="utf-8")
    args = argparse.Namespace(
        sheet_a=str(a), sheet_b=str(b), key="id",
        fields="amount", tolerance="", out=str(tmp_path / "cmp"),
    )
    assert cmd_compare(args) == 0
    ledger_path = tmp_path / "cmp" / ".audit" / "ledger.jsonl"
    events = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    assert events[0]["type"] == "action.intent"
    assert events[-1]["type"] == "compare.completed"
    assert events[-1]["payload"]["totals"]["changed"] == 1


def test_cmd_verify_checks_the_ledger(tmp_path):
    assert cmd_run(_run_args(tmp_path)) == 0
    verify_args = argparse.Namespace(out=str(tmp_path / "out"))
    assert cmd_verify(verify_args) == 0
    ledger_path = tmp_path / "out" / ".audit" / "ledger.jsonl"
    ledger_path.write_text("{broken}\n", encoding="utf-8")
    assert cmd_verify(verify_args) == 1


def test_report_pack_stays_deterministic_across_runs(tmp_path):
    first = _run_args(tmp_path)
    first.out = str(tmp_path / "out-a")
    second = _run_args(tmp_path)
    second.out = str(tmp_path / "out-b")
    assert cmd_run(first) == 0
    assert cmd_run(second) == 0
    assert (tmp_path / "out-a" / "check-results.csv").read_bytes() == (
        tmp_path / "out-b" / "check-results.csv"
    ).read_bytes()
    assert verify_ledger(tmp_path / "out-a" / ".audit" / "ledger.jsonl")["ok"] is True
    assert verify_ledger(tmp_path / "out-b" / ".audit" / "ledger.jsonl")["ok"] is True
