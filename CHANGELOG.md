# Changelog

All notable changes to Sheet Solution are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] — 2026-11-18

### Added
- Deterministic, offline sheet-audit platform. Feed it a sheet + a
  plain-English check-template; it runs the checks and writes a report pack
  (CSV + audit log + extracted images) with a hash chain you can re-verify.
- Reused spine from Signoff 0.1.0 (model / util / engine / render / verify /
  ingest / mapping) under `src/sheet_solution/core/` — 151 inherited tests
  pass unchanged against the copied engine (see `PROVENANCE.md`).
- New sheet layer (`src/sheet_solution/sheets/`): template parser,
  deterministic check runner, report renderer, embedded-image extraction.
- Two personas: **auditor** (pass/fail against a standard) and **verifier**
  (expected values must be present).
- CLI (`load-sheet`, `parse-template`, `run`, `verify`, **`compare`**) + the
  inherited spine commands (`demo`, `build`, `verify-pack`, …).
- **Two-sheet compare**: `compare --sheet-a … --sheet-b … --key … --fields …
  [--tolerance …]` classifies every row as MATCHED / CHANGED / ONLY-IN-A /
  ONLY-IN-B with full field-level traceability (deterministic, logged).
- Offline Flask GUI (`gui/`): drag-and-drop file input + **colour-coded
  visual cards** (green PASS / red FAIL / amber PENDING-HUMAN; for compare:
  green MATCHED / red CHANGED / blue only-in-A / orange only-in-B) with
  downloadable report pack. Local-only, no cloud.
- One-click `run.sh` + `install.sh` for non-technical recipients.
- Distribution: pip wheel, non-root offline Docker image, standalone bundle.
- Security posture: zero network, PII local, CSV formula-injection
  neutralised, hash-pinned dependencies, digest-pinned base image.

### Design note
- **No AI model in the check path.** Every machine check is a verifiable
  rule; every image/semantic check is logged as `PENDING-HUMAN`. This is the
  "the machine never guesses" guarantee.
