# Changelog

All notable changes to Sheet Solution are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.2.0] — 2026-11-18

### Added
- **Two-sheet compare** (`compare` command + GUI tab): row-level diff
  (MATCHED / CHANGED / ONLY-IN-A / ONLY-IN-B) with field-level traceability
  and optional numeric tolerance.
- **Drag-and-drop GUI** with colour-coded visual cards (green PASS / red
  FAIL / amber PENDING-HUMAN; compare: green MATCHED / red CHANGED /
  blue only-in-A / orange only-in-B), downloadable report pack.
- **Column preview** after upload: detected columns + 3 sample rows so a
  non-technical user can verify the file and see exact column names.
- **File-picker fallback** (hidden `<input type="file">` + "choose a file"
  button) so the tool works without drag-and-drop.
- **"Check my template"** button + `/api/validate-template` endpoint.
- **"Download all (zip)"** single-archive download of the whole pack.
- **"Start over" reset** button per pane.
- **Spinner + disabled state** on Run/Compare while in-flight.
- **"Show matched rows"** toggle on compare cards.
- **Browser regression test** (`tests/gui-browser-test.sh`) driving the real
  GUI in Chromium via Playwright, added as a CI job.
- `--key` flag on `run` for real row identifiers in failed-row lists
  (auto-detected from the header when omitted).

### Changed
- Failed rows now identified by their actual key value (e.g. `APP-003`)
  instead of a 0-based `row-N` index.
- `example_that_passes` / `example_that_fails` are now optional in the
  check-template (the engine never used them; they were pure friction).
- Broken download links fixed: only links for artifacts that exist for that
  run are shown.

### Fixed
- Compare button stayed disabled after dropping two sheets (root cause:
  drop handler stored under `state.compare.sheetA/.sheetB` but `refresh()`
  read `state.compare.A/.B`).
- `run.sh` failed on a foreign (non-3.11) host Python due to hash-locked
  requirements; now installs the same versions unpinned on foreign hosts.
- Bundle GUI now ships flask + gui.sh so it works fully offline from a
  fresh extract.

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
