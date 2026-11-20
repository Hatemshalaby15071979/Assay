"""CLI/GUI parity: the same inputs must produce the same report bytes.

The GUI is a thin shell around the deterministic engine, so this test drives
both paths and asserts the report artifacts are byte-identical. It is the
regression that keeps the GUI from drifting into its own logic.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from tests.conftest import REPO

from sheet_solution.cli import cmd_compare, cmd_run
from sheet_solution.gui import main as gui_main


@pytest.fixture()
def client(tmp_path, monkeypatch):
    spool = tmp_path / "gui-spool"
    spool.mkdir()
    monkeypatch.setattr(gui_main, "SPOOL", spool)
    app = gui_main.build_app()
    app.config["TESTING"] = True
    return app.test_client()


def _upload(client, path: Path) -> str:
    with path.open("rb") as fh:
        response = client.post(
            "/api/upload",
            data={"file": (fh, path.name)},
            content_type="multipart/form-data",
        )
    assert response.json["ok"] is True
    return response.json["id"]


def test_compare_report_is_byte_identical_between_cli_and_gui(client, tmp_path):
    sheet_a = REPO / "tests" / "fixtures" / "weekA.xlsx"
    sheet_b = REPO / "tests" / "fixtures" / "weekB.xlsx"
    fields = "amount,status"
    key = "applicant_id"

    cli_out = tmp_path / "cli-compare"
    cli_args = argparse.Namespace(
        sheet_a=str(sheet_a), sheet_b=str(sheet_b), key=key,
        fields=fields, tolerance="", out=str(cli_out),
    )
    assert cmd_compare(cli_args) == 0

    gui_out = client.post(
        "/api/compare",
        json={
            "sheetA": _upload(client, sheet_a),
            "sheetB": _upload(client, sheet_b),
            "key": key,
            "fields": fields,
        },
    ).json
    assert gui_out["ok"] is True

    cli_csv = (cli_out / "compare-report.csv").read_bytes()
    gui_csv = (Path(gui_out["out"]) / "compare-report.csv").read_bytes()
    assert cli_csv == gui_csv
    assert gui_out["totals"]["changed"] == 1


def test_check_results_are_byte_identical_between_cli_and_gui(client, tmp_path):
    sheet = REPO / "examples" / "example-sheet.xlsx"
    template = REPO / "examples" / "check-template.example.txt"

    cli_out = tmp_path / "cli-run"
    cli_args = argparse.Namespace(
        sheet=str(sheet), template=str(template), out=str(cli_out), key=None,
    )
    assert cmd_run(cli_args) == 0

    gui_out = client.post(
        "/api/checks",
        json={
            "sheet": _upload(client, sheet),
            "template": _upload(client, template),
        },
    ).json
    assert gui_out["ok"] is True

    cli_csv = (cli_out / "check-results.csv").read_bytes()
    gui_csv = (Path(gui_out["out"]) / "check-results.csv").read_bytes()
    assert cli_csv == gui_csv
    assert len(gui_out["results"]) == 4
