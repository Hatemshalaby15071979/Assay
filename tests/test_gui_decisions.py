"""Phase D — GUI decision endpoints (fail-closed loop via Flask test client)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sheet_solution.gui import main as gui_main

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture()
def client(tmp_path, monkeypatch):
    spool = tmp_path / "gui-spool"
    spool.mkdir()
    monkeypatch.setattr(gui_main, "SPOOL", spool)
    app = gui_main.build_app()
    app.config["TESTING"] = True
    return app.test_client()


TERMS = ("tag_row", "flag_for_human")


def _upload(client, path: Path) -> str:
    with path.open("rb") as fh:
        r = client.post("/api/upload",
                        data={"file": (fh, path.name)},
                        content_type="multipart/form-data")
    assert r.json["ok"] is True, r.json
    return r.json["id"]


def _policy(tmp_path: Path, actions=TERMS) -> Path:
    p = tmp_path / "gui-policy.json"
    p.write_text(json.dumps({
        "version": 1,
        "defaults": {"on_unresolved": "propose", "confirm_required": True},
        "checks": [{
            "id": "CH-002", "column": "qa_score", "rule": "not_blank",
            "params": {}, "severity": "high",
            "on_fail": {"actions": list(actions), "confirm_required": True},
        }],
    }), encoding="utf-8")
    return p


def _board(client, tmp_path):
    """Run checks + upload policy + plan; return (out, decisions)."""
    sheet = _upload(client, REPO / "examples" / "example-sheet.xlsx")
    tmpl = _upload(client, REPO / "examples" / "check-template.example.txt")
    r = client.post("/api/checks", json={"sheet": sheet, "template": tmpl})
    assert r.json["ok"] is True
    out = r.json["out"]
    policy = _upload(client, _policy(tmp_path))
    r = client.post("/api/decisions/plan", json={"out": out, "policy": policy})
    assert r.json["ok"] is True, r.json
    return out, r.json["decisions"]


def test_plan_produces_proposals_with_declared_options(client, tmp_path):
    out, decisions = _board(client, tmp_path)
    assert len(decisions) == 1
    d = decisions[0]
    assert d["state"] == "PROPOSED"
    assert d["options"] == list(TERMS)
    assert d["finding"]["check_id"] == "CH-002"
    assert "actor" not in d and "note" not in d  # runtime evidence excluded


def test_list_returns_states_and_ledger_evidence(client, tmp_path):
    out, _ = _board(client, tmp_path)
    r = client.get("/api/decisions", query_string={"out": out})
    assert r.json["ok"] is True
    assert r.json["decisions"][0]["state"] == "PROPOSED"
    assert any(e["type"] == "decision.proposed" for e in r.json["events"])


def test_decide_requires_a_named_actor(client, tmp_path):
    out, decisions = _board(client, tmp_path)
    fid = decisions[0]["decision_id"]
    r = client.post("/api/decisions/decide", json={
        "out": out, "findingId": fid, "action": "approve", "actor": ""})
    assert r.status_code == 400
    assert "actor" in r.json["error"].lower() or "actor" in r.json["error"]


def test_apply_before_approval_is_refused(client, tmp_path):
    out, decisions = _board(client, tmp_path)
    fid = decisions[0]["decision_id"]
    r = client.post("/api/decisions/decide", json={
        "out": out, "findingId": fid, "action": "apply", "actor": "alice"})
    assert r.status_code == 400
    assert Path(out, "corrected-copy.jsonl").exists() is False


def test_deny_then_alternative_then_apply(client, tmp_path):
    out, decisions = _board(client, tmp_path)
    fid = decisions[0]["decision_id"]

    def decide(action, **kw):
        body = {"out": out, "findingId": fid, "action": action, "actor": "alice"}
        body.update(kw)
        r = client.post("/api/decisions/decide", json=body)
        assert r.json["ok"] is True, r.json
        return r.json

    # Deny: nothing applied, state DECLINED.
    r = decide("decline", reason="risky")
    assert r["decisions"][0]["state"] == "DECLINED"
    assert Path(out, "corrected-copy.jsonl").exists() is False

    # Re-propose the alternative -> still PROPOSED, still not applied.
    r = decide("re-propose", actionId="flag_for_human", actor="bob")
    assert r["decisions"][0]["proposed_action"] == "flag_for_human"
    assert r["decisions"][0]["state"] == "PROPOSED"

    # Approve -> APPROVED, still nothing applied.
    r = decide("approve", actor="carol")
    assert r["decisions"][0]["state"] == "APPROVED"
    assert Path(out, "corrected-copy.jsonl").exists() is False

    # Apply -> APPLIED, corrected copy written, ledger records it.
    r = decide("apply", actor="carol")
    assert r["decisions"][0]["state"] == "APPLIED"
    assert Path(out, "corrected-copy.jsonl").exists() is True
    types = [e["type"] for e in r["events"]]
    assert "decision.applied" in types
    assert any(e.get("actor") == "carol" and e["type"] == "decision.recorded"
               for e in r["events"])


def test_compare_returns_a_json_error_for_an_unloadable_sheet(client, tmp_path):
    good = _upload(client, REPO / "examples" / "compare-baseline.xlsx")
    bad = tmp_path / "notes.txt"
    bad.write_text("not a sheet", encoding="utf-8")
    bad_id = _upload(client, bad)
    r = client.post("/api/compare", json={"sheetA": good, "sheetB": bad_id,
                                          "key": "item_id", "fields": "amount"})
    assert r.status_code == 400
    assert r.json["ok"] is False
    assert "unsupported" in r.json["error"].lower()


def test_pack_export_includes_decision_artifacts(client, tmp_path):
    out, decisions = _board(client, tmp_path)
    r = client.get("/api/pack", query_string={"out": out, "name": "decisions.json"})
    assert r.status_code == 200
    assert b"decision_id" in r.data


def test_outside_spool_pack_is_refused(client):
    r = client.get("/api/decisions", query_string={"out": "/etc"})
    assert r.status_code == 400
    assert "spool" in r.json["error"].lower()


def test_plan_refuses_a_traversal_policy_id(client):
    sheet = _upload(client, REPO / "examples" / "example-sheet.xlsx")
    tmpl = _upload(client, REPO / "examples" / "check-template.example.txt")
    out = client.post("/api/checks", json={"sheet": sheet, "template": tmpl}).json["out"]
    r = client.post("/api/decisions/plan", json={"out": out, "policy": "../../etc"})
    assert r.status_code == 400


def test_spool_file_rejects_traversal(tmp_path, monkeypatch):
    spool = tmp_path / "s"
    spool.mkdir()
    monkeypatch.setattr(gui_main, "SPOOL", spool)
    (spool / "ok").mkdir()
    (spool / "ok" / "f.txt").write_text("x", encoding="utf-8")
    assert gui_main._spool_file("ok").name == "f.txt"
    for bad in ("../../etc", "a/b", "..", ".", ""):
        with pytest.raises((ValueError, FileNotFoundError)):
            gui_main._spool_file(bad)


def test_index_has_decide_tab_and_stays_offline(client):
    r = client.get("/")
    assert b'tab-decide' in r.data and b'pane-decide' in r.data
    assert b"https://" not in r.data
