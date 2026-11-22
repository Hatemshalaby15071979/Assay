#!/usr/bin/env python3
"""Check that version, Python floor and status claims agree across the repo.

Single sources of truth:

* version      -> ``pyproject.toml`` ``[project].version``
* Python floor -> ``pyproject.toml`` ``requires-python``
* status       -> ``README.md`` "Status" section (declares itself the source)

Live docs must not hardcode a test count (it drifts) and must not claim a
digital signature (evidence is hash-consistent only). ``CHANGELOG.md`` is a
historical record: it is excluded from those two scans, but its first heading
must be ``# Changelog`` so a new release cannot be inserted above the title.

Exit 0 = all claims agree; exit 1 = a listed inconsistency.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LIVE_DOCS = (
    "README.md",
    "SECURITY.md",
    "ARCHITECTURE.md",
    "docs/ARCHITECTURE.md",
    "docs/USER-GUIDE.md",
    "PROVENANCE.md",
    "CONTRIBUTING.md",
    "RELEASE_READINESS.md",
)

FORBIDDEN_SIGNATURE_CLAIMS = re.compile(
    r"(?i)\b(digitally signed|cryptographically signed|signed evidence pack|signature-verified)\b"
)
HARDCODED_TEST_COUNT = re.compile(
    r"(?i)\b\d{2,4}(?:-|\s+)(?:automated\s+)?tests?\b"
)
STATUS_SOURCE_DECLARATION = "single source of truth for project status"


def _python_versions(ci_text: str) -> list[str]:
    """Extract declared Python versions from a GitHub Actions workflow."""
    versions: list[str] = []
    for match in re.finditer(
        r"python-version:\s*(\[[^\]]*\]|\"[^\"]+\"|'[^']+')", ci_text
    ):
        value = match.group(1).strip()
        if value.startswith("["):
            versions.extend(re.findall(r"[\"']([0-9]+\.[0-9]+)[\"']", value))
        elif "${{" not in value:
            versions.append(value.strip("\"'"))
    return versions


def check_repo(root: Path) -> list[str]:
    problems: list[str] = []
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    version = project["version"]
    requires = project["requires-python"]
    floor_match = re.search(r">=\s*([0-9]+\.[0-9]+)", requires)
    if not floor_match:
        return [f"requires-python must use a >=X.Y floor, found {requires!r}"]
    python_floor = floor_match.group(1)

    for rel in ("src/sheet_solution/__init__.py", "src/sheet_solution/core/__init__.py"):
        text = (root / rel).read_text(encoding="utf-8")
        declared = re.search(r'__version__\s*=\s*"([^"]+)"', text)
        if not declared or declared.group(1) != version:
            problems.append(
                f"{rel} __version__ "
                f"{declared.group(1) if declared else 'missing'} != pyproject {version}"
            )

    readme = (root / "README.md").read_text(encoding="utf-8")
    if f"Assay {version}" not in readme:
        problems.append(
            f"README.md does not name version {version} as 'Assay {version}'"
        )
    if STATUS_SOURCE_DECLARATION not in readme:
        problems.append(f"README.md must declare itself the {STATUS_SOURCE_DECLARATION!r}")

    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    base = re.search(r"^FROM\s+python:([0-9]+\.[0-9]+)", dockerfile, re.MULTILINE)
    if not base:
        problems.append("Dockerfile has no python:X.Y base image")
    elif base.group(1) != python_floor:
        problems.append(
            f"Dockerfile python {base.group(1)} != requires-python {python_floor}"
        )

    ci_text = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    ci_versions = _python_versions(ci_text)
    if not ci_versions:
        problems.append("CI workflow declares no python-version")
    else:
        lowest = min(ci_versions, key=lambda v: tuple(map(int, v.split("."))))
        if lowest != python_floor:
            problems.append(
                f"CI minimum python {lowest} != requires-python {python_floor}"
            )

    lock = (root / "requirements.lock").read_text(encoding="utf-8")
    runtime = re.search(r'"(fpdf2==[^"]+)"', " ".join(project.get("dependencies", [])))
    if runtime and runtime.group(1) not in lock:
        problems.append(f"requirements.lock does not pin {runtime.group(1)}")

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    first_line = next((ln.strip() for ln in changelog.splitlines() if ln.strip()), "")
    if first_line != "# Changelog":
        problems.append("CHANGELOG.md must start with the '# Changelog' heading")

    floor_minor = int(python_floor.split(".")[1])
    for rel in LIVE_DOCS:
        path = root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"Python\s+3\.(\d+)", text):
            if int(match.group(1)) < floor_minor:
                problems.append(
                    f"{rel} claims Python 3.{match.group(1)} below the {python_floor} floor"
                )
        if FORBIDDEN_SIGNATURE_CLAIMS.search(text):
            problems.append(
                f"{rel} contains a signature claim; evidence is hash-consistent only"
            )
        if HARDCODED_TEST_COUNT.search(text):
            problems.append(
                f"{rel} hardcodes a test count that will drift; let CI report it"
            )
    return problems


def main() -> int:
    problems = check_repo(ROOT)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1
    print("Documentation consistency checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
