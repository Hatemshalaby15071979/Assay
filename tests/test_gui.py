"""Sheet Solution — GUI API tests (offline, no browser, no outbound calls).

Drives the Flask app's test client directly. No server socket is opened and
no request leaves the process — consistent with the offline guarantee.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sheet_solution.gui import main as gui_main


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Point the spool at a temp dir so tests don't pollute the real one.
    monkeypatch.setattr(gui_main, "SPOOL", Path(tempfile_spool(tmp_path)))
    app = gui_main.build_app()
    app.config["TESTING"] = True
    return app.test_client()


def tempfile_spool(tmp_path) -> Path:
    d = tmp_path / "gui-spool"
    d.mkdir()
    return d


REPO = Path(__file__).resolve().parent.parent


def test_health_reports_offline(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json["offline"] is True


def test_upload_stashes_file(client, tmp_path):
    p = REPO / "examples" / "example-sheet.xlsx"
    with p.open("rb") as fh:
        r = client.post("/api/upload",
                        data={"file": (fh, p.name)},
                        content_type="multipart/form-data")
    assert r.json["ok"] is True
    assert Path(r.json["path"]).exists()


def test_checks_flow_produces_cards(client):
    def up(name):
        p = REPO / "examples" / name
        with p.open("rb") as fh:
            r = client.post("/api/upload",
                            data={"file": (fh, name)},
                            content_type="multipart/form-data")
        return r.json["id"]
    sheet_id, tmpl_id = up("example-sheet.xlsx"), up("check-template.example.txt")
    r = client.post("/api/checks",
                    json={"sheet": sheet_id, "template": tmpl_id})
    assert r.json["ok"] is True
    cards = r.json["results"]
    assert len(cards) == 4
    outcomes = {c["outcome"] for c in cards}
    assert {"PASS", "FAIL", "PENDING-HUMAN"} <= outcomes


def test_compare_flow_produces_diff_cards(client):
    def up(name):
        p = REPO / "tests" / "fixtures" / name
        with p.open("rb") as fh:
            r = client.post("/api/upload",
                            data={"file": (fh, name)},
                            content_type="multipart/form-data")
        return r.json["id"]
    a, b = up("weekA.xlsx"), up("weekB.xlsx")
    r = client.post("/api/compare",
                    json={"sheetA": a, "sheetB": b,
                          "key": "applicant_id", "fields": "amount,status"})
    assert r.json["ok"] is True
    assert r.json["totals"]["changed"] == 1
    changed = [x for x in r.json["rows"] if x["status"] == "CHANGED"]
    assert changed and changed[0]["key"] == "A2"


def test_compare_requires_key_and_fields(client):
    r = client.post("/api/compare",
                    json={"sheetA": "x", "sheetB": "y", "key": "", "fields": ""})
    assert r.status_code == 400


def test_index_html_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Sheet Solution" in r.data
    # The SPA must not make any outbound calls (offline guarantee in the UI too).
    assert b"fetch('/api/" in r.data and b"https://" not in r.data
