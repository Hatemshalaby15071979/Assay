"""Scaffold + offline-guarantee invariants for the Assay repo.

Runs the repo's own checkers as subprocesses — the tests assert the same
exit codes an operator sees. This repository is a *shipped tool*, so the
scaffold checks the tool's invariants (tree, offline guarantee, output
contract), not the owner-decision scaffolding the Signoff reference carried.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from tests.conftest import REPO


def run_script(script: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script)], cwd=str(REPO),
                          capture_output=True, text=True)


def test_check_scaffold_exit_zero():
    result = run_script(REPO / "scripts" / "check-scaffold.py")
    assert result.returncode == 0, result.stdout + result.stderr


def test_check_offline_scan_exit_zero():
    result = run_script(REPO / "scripts" / "check-offline.py")
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_placeholder_tokens_in_sources():
    bad_tokens = ("TODO", "FIXME", "XXX", "HACK", "NotImplementedError")
    exempt = {"check-scaffold.py", "check-offline.py"}
    hits: list[str] = []
    for root in ("src", "scripts"):
        for path in (REPO / root).rglob("*.py"):
            if path.name in exempt:
                continue
            text = path.read_text(encoding="utf-8")
            for token in bad_tokens:
                if token in text:
                    hits.append(f"{path}: {token}")
    assert hits == [], "placeholder tokens must never ship recursively"


def test_output_files_contract_is_stable():
    from sheet_solution import config as cfg
    # The inherited spine's output contract must be unchanged.
    assert set(cfg.OUTPUT_FILES) == {
        "dossier_html", "dossier_pdf", "pack_json", "answers_csv",
        "gaps_csv", "events_csv", "statement_txt",
    }


def test_coverage_window_is_90_days():
    from sheet_solution import config as cfg
    assert cfg.COVERAGE_WINDOW_DAYS == 90


def test_ci_workflow_contains_network_none_demo():
    workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "--network none" in workflow


def test_readme_states_offline_guarantee_up_front():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    head = "\n".join(readme.splitlines()[:20]).lower()
    assert "offline" in head


def test_provenance_records_reuse():
    provenance = (REPO / "docs" / "archive" / "PROVENANCE.md").read_text(encoding="utf-8")
    assert "signoff" in provenance.lower()
    assert "0.1.0" in provenance


def _load_check_scaffold():
    spec = importlib.util.spec_from_file_location(
        "check_scaffold_under_test", REPO / "scripts" / "check-scaffold.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_root_hygiene_flags_unlisted_root_documents(tmp_path):
    """GOVERNANCE.md section 2: only its table's documents may sit at the root.

    Drives the check against a temporary tree so the assertion is proven to
    fail closed, without writing into the real repository root.
    """
    module = _load_check_scaffold()
    (tmp_path / "README.md").write_text("# allowed\n", encoding="utf-8")
    (tmp_path / "STRAY-NOTE.md").write_text("# stray\n", encoding="utf-8")
    (tmp_path / "NOTES.txt").write_text("stray\n", encoding="utf-8")
    (tmp_path / "unrelated.toml").write_text("x = 1\n", encoding="utf-8")

    problems: list[str] = []
    real_repo = module.REPO
    module.REPO = tmp_path
    try:
        module.check_root_hygiene(problems)
    finally:
        module.REPO = real_repo

    flagged = " ".join(problems)
    assert "STRAY-NOTE.md" in flagged, problems
    assert "NOTES.txt" in flagged, problems
    assert "README.md" not in flagged, problems
    assert "unrelated.toml" not in flagged, problems


def test_root_hygiene_accepts_the_real_root():
    problems: list[str] = []
    _load_check_scaffold().check_root_hygiene(problems)
    assert problems == [], problems
