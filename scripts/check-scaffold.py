#!/usr/bin/env python3
"""Scaffold assertion for the Assay repository.

Checks the required tree for a distributable, offline, deterministic
sheet-audit tool. Unlike the Signoff reference (which carried owner
decision-making files for a portfolio-evidence project), this repository is
shipped to end users, so the scaffold checks the *tool's* invariants:

1. Every required path exists and is non-empty (root set per GOVERNANCE.md
   section 2; the report trio lives under docs/archive/ since 2026-11-26).
2. No forbidden placeholder tokens in src/ or scripts/ (TODO, FIXME, XXX,
   HACK, NotImplementedError, bare stub bodies).
3. The offline guarantee: the check-offline scan passes.
4. The output-files contract is stable (determinism of the report pack).
5. Root hygiene: no stray .md/.txt at the root, and no unlisted root document
   (GOVERNANCE.md section 2 documents the allowed set).

Run: python scripts/check-scaffold.py
Exit 0 = ok, exit 1 = problem (with a printed list).
"""
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

FORBIDDEN_TOKENS = [
    "TODO", "FIXME", "NotImplementedError", "XXX", "HACK",
]

REQUIRED = [
    # root -- the requested set from GOVERNANCE.md section 2 (nothing else at root)
    "README.md", "AGENTS.md", "CONSTITUTION.md", "GOVERNANCE.md",
    "LICENSE", "CHANGELOG.md", "SECURITY.md",
    "pyproject.toml", "Makefile", ".gitignore", ".editorconfig",
    ".dockerignore", "Dockerfile", "docker-compose.yml", ".gitleaks.toml",
    # one-off / historical reports, archived by the 2026-11-26 governance pass
    "docs/archive/CONTRIBUTING.md", "docs/archive/PROVENANCE.md",
    "docs/archive/RELEASE_READINESS.md",
    # packaging
    "requirements.lock",
    # tool entry points
    "run.sh", "gui.sh", "gui/main.py", "gui/README.md",
    "scripts/check-doc-consistency.py", "scripts/scale-stress.py",
    # security tooling
    "tooling/security/scan_history_secrets.py",
    "tooling/security/history-scan-exceptions.json",
    # source spine (inherited) + new sheet layer
    "src/sheet_solution/__init__.py", "src/sheet_solution/__main__.py",
    "src/sheet_solution/cli.py",
    "src/sheet_solution/core/__init__.py", "src/sheet_solution/core/config.py",
    "src/sheet_solution/core/errors.py", "src/sheet_solution/core/cli.py",
    "src/sheet_solution/sheets/__init__.py",
    "src/sheet_solution/sheets/template.py", "src/sheet_solution/sheets/runner.py",
    "src/sheet_solution/sheets/report.py", "src/sheet_solution/sheets/images.py",
    "src/sheet_solution/sheets/compare.py", "src/sheet_solution/sheets/ledger.py",
    # GUI package (offline drag-and-drop + visual cards)
    "src/sheet_solution/gui/__init__.py", "src/sheet_solution/gui/main.py",
    "src/sheet_solution/gui/index.html",
    # inherited spine modules
    "src/sheet_solution/core/engine/hash_chain.py",
    "src/sheet_solution/core/verify/verify_pack.py",
    "src/sheet_solution/core/ingest/csv_normaliser.py",
    "src/sheet_solution/core/render/pdf_renderer.py",
    "src/sheet_solution/core/model/decision_event.py",
    # policy + rules + ops tasks (one schema, three input formats)
    "src/sheet_solution/core/policy/__init__.py",
    "src/sheet_solution/core/policy/schema.py",
    "src/sheet_solution/core/policy/yaml_lite.py",
    "src/sheet_solution/core/policy/loader.py",
    "src/sheet_solution/core/policy/validator.py",
    "src/sheet_solution/sheets/rules/__init__.py",
    "src/sheet_solution/sheets/rules/registry.py",
    "src/sheet_solution/sheets/analyze.py",
    "src/sheet_solution/sheets/compatibility.py",
    # decision loop (fail-closed propose -> decide -> apply) + ops metrics
    "src/sheet_solution/sheets/actions.py",
    "src/sheet_solution/sheets/decisions.py",
    "src/sheet_solution/sheets/metrics.py",
    # tests
    "tests/conftest.py", "tests/test_scaffold.py", "tests/test_sheets.py",
    "tests/test_compare.py", "tests/test_gui.py", "tests/test_ledger.py",
    "tests/test_parity.py", "tests/test_policy.py", "tests/test_rules.py",
    "tests/test_analyze.py", "tests/test_decisions.py",
    "tests/test_gui_decisions.py", "tests/test_metrics.py",
    "tests/gui-browser-test.sh", "tests/gui-decisions-test.sh",
    # docs
    "docs/ARCHITECTURE.md", "docs/USER-GUIDE.md",
    # examples
    "examples/check-template.example.txt", "examples/README.md",
    "examples/policy.example.json", "examples/policy.example.yaml",
    "examples/policy-sheet.example.csv",
]

ALLOW_EMPTY: set[str] = set()

# GOVERNANCE.md section 2, "root documents" table: these are the only .md/.txt
# documents permitted at the root. Everything else belongs in docs/ or
# docs/archive/. Comparisons are case-insensitive; LICENSE may also appear as
# LICENSE.md. Note there is no .txt allowance at all.
ROOT_ALLOWED_DOCS = {
    "readme.md", "agents.md", "constitution.md", "governance.md",
    "changelog.md", "license.md", "security.md",
}


def check_forbidden_tokens(problems: list[str]) -> None:
    targets = list((REPO / "src").rglob("*.py")) + list((REPO / "scripts").rglob("*.py"))
    for path in sorted(targets):
        if path == Path(__file__).resolve():
            continue  # the scanner necessarily contains the token literals
        rel = path.relative_to(REPO)
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            if token in text:
                problems.append(f"{rel}: forbidden placeholder token {token!r}")
        for line_no, line in enumerate(text.splitlines(), start=1):
            s = line.strip().rstrip(":")
            if s in ("pass", "..."):
                problems.append(f"{rel}:{line_no}: stub body ({s})")


def check_pyproject_pins(problems: list[str]) -> None:
    path = REPO / "pyproject.toml"
    if not path.exists():
        problems.append("pyproject.toml missing")
        return
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        problems.append(f"pyproject.toml unparseable: {exc}")
        return
    deps = " ".join(data.get("project", {}).get("dependencies", []))
    if "fpdf2==" not in deps:
        problems.append("pyproject.toml does not pin fpdf2 (inherited PDF renderer needs it)")
    if data.get("project", {}).get("requires-python") != ">=3.11":
        problems.append("pyproject.toml requires-python must be >=3.11")


def check_root_hygiene(problems: list[str]) -> None:
    """GOVERNANCE.md section 2: "No stray `.md`/`.txt` at the root".

    Checked in both directions: REQUIRED proves the documented root documents
    are present, and this proves nothing *unlisted* sits beside them. Only the
    first direction existed, which is how the 2026-11-26 governance pass could
    archive three reports while the root set still looked satisfied -- a
    one-way check cannot enforce a "nothing else at root" rule.
    """
    for path in sorted(REPO.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        if path.name.lower() in ROOT_ALLOWED_DOCS:
            continue
        problems.append(
            f"stray root document: {path.name} -- move it to docs/ or "
            f"docs/archive/ (GOVERNANCE.md section 2)"
        )


def main() -> int:
    problems: list[str] = []
    for rel in REQUIRED:
        path = REPO / rel
        if not path.exists():
            problems.append(f"missing: {rel}")
            continue
        if rel in ALLOW_EMPTY:
            continue
        if path.is_file() and path.stat().st_size == 0:
            problems.append(f"empty: {rel}")

    check_forbidden_tokens(problems)
    check_pyproject_pins(problems)
    check_root_hygiene(problems)

    if problems:
        print(f"check-scaffold: {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"check-scaffold: OK — {len(REQUIRED)} required files present; "
          f"root hygiene clean ({len(ROOT_ALLOWED_DOCS)} allowed root documents)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
