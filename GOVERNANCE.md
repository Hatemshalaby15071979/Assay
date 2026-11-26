# GOVERNANCE.md — Operating Policy & Repo Map for Assay

> Companion to `CONSTITUTION.md` (the *why* — philosophy and clean-code policy, which
> this file enforces operationally) and `AGENTS.md` (the agent charter + ledger).
> Read all three before acting. This file may be updated by any agent **as a logged
> governance change** to keep the map and policy truthful; the CONSTITUTION itself is
> owner-only.

## 1. Repository map

Authoritative directory map for **Assay**. Any file you add, move, rename, or
delete gets reflected here in the same landing.

| Path | Purpose (one line) |
|---|---|
| `src/` | The Assay application (import package `sheet_solution`) — check engine, CLI, report packs. |
| `gui/` | Local-browser GUI (runs on `127.0.0.1`). |
| `tests/` | The full test suite (offline, deterministic). |
| `examples/` | Ready-made sheets, check templates, and policies to run in seconds. |
| `scripts/` | Evidence scripts: offline check, determinism check, doc-consistency check, SBOM. |
| `tooling/` | Extra tooling, e.g. the fuzz corpus under `tooling/fuzz/`. |
| `docs/` | Standing docs: `ARCHITECTURE.md`, `USER-GUIDE.md`, `brand/` (offline brand sheet). |
| `docs/archive/` | One-off / historical reports (release readiness, shipment + pre-shipment reports, provenance, contributing notes). |
| `assets/` | Brand assets (logos). |
| `.github/` | CI workflows (test matrix, packaging, security scans). |
| `Makefile`, `run.sh`, `install.sh`, `gui.sh` | One-command entry points. |
| `Dockerfile`, `docker-compose.yml`, `docker-entrypoint.sh`, `.dockerignore` | Offline container run (`--network none`). |
| `pyproject.toml`, `requirements.lock` | Packaging and the pinned dependency lock. |
| `SECURITY.md` | Threat model and vulnerability reporting. |
| `CHANGELOG.md` | Dated user-visible changes. |
| `LICENSE` | MIT. |
| `.gitleaks.toml`, `.editorconfig`, `.gitignore` | Secret-scan config, formatting rules, ignore list. |
| `helix_codex_inevitable_engraving.pdf` (+ `.backup`) | Engraving art file kept with the brand assets. |

(Working directories `build/`, `dist/`, `out/`, `.venv/`, `.pytest_cache/` are
local only and not part of the repository map.)

## 2. Documentation policy (what belongs where)

**Root holds only the requested set** — nothing else:

| File | State | Purpose |
|---|---|---|
| `README.md` | required | The single source of truth: what this is, why it's here, how to use it — in simple English for a professional reader. Carries the Helix Solutions logo. |
| `AGENTS.md` | required | Agent charter + sign-in/out ledger. |
| `CONSTITUTION.md` | required | The owner's engineering philosophy and clean-code policy (unified across every repo). |
| `GOVERNANCE.md` | required | This file: repo map, documentation policy, sync policy, archiving rules. |
| `CHANGELOG.md` | standard | Dated user-visible changes. |
| `LICENSE` / `LICENSE.md` | standard | MIT, unless the repo states otherwise. |
| `SECURITY.md` | standard | Threat model, vulnerability reporting, secret handling. |

**Everything else lives in `docs/`** — reports, audit logs, execution plans, research
notes, ADRs, runbooks, anything dated or one-off. No stray `.md`/`.txt` at the root.
If a document at the root is not in the table above, move it to `docs/` (or
`docs/archive/` if it is historical) and record the move in the `AGENTS.md` ledger.

## 3. Synchronization & harmony policy

The owner's rule: **the repository's actual status must match its README at all times,
locally and remotely.**

1. `README.md` is the canonical account. Landing pages (`index.html`) and dashboards
   mirror it; they never fork it.
2. When reality changes, update `README.md` **first**, then mirror it to the pages.
3. Every sanctioned change is committed **and pushed** to the default branch, so the
   GitHub copy, the local working copy, and any local platform that reads the repo
   all show the same truth.
4. A number published anywhere (README, page, badge) must be reproducible from this
   repository. A stale figure is removed, not left to rot.
5. The workspace tool `readme-sync/` (in `Repos_Readmes`) verifies that every public
   repo's README matches its local clone. Keep this repo's README in a state it reports
   as matching.

## 4. Archiving rule

- Archive (move to `docs/archive/`), never delete: historical reports, superseded plans,
  dated audits, and one-off execution logs.
- Delete outright only regenerable artifacts: caches, build output, coverage files.
- Record every move in the `AGENTS.md` ledger with date and time.

## 5. Engineering philosophy & clean-code policy (operational summary)

The full text is `CONSTITUTION.md`. The operational reminders, enforced here:

- **Fail closed.** Missing input or missing authority is a refusal, never a default.
- **Evidence before claims.** Published numbers carry a command, a date, and an artifact.
- **No duplicates, no temp files, one file one job, every file explains itself.**
- **Secrets never enter the tree.**
- **Simple English** in code, docs, and UI, so a non-technical professional reader
  (recruiter, partner) can follow.
- **One brand mark:** the Helix Solutions logo, everywhere.

## 6. Definition of done

It works; it has a test or a documented manual check; the `AGENTS.md` ledger has an
entry; the docs reflect the new reality; no temporary file was left behind; and every
published number can be re-run to reproduce itself.
