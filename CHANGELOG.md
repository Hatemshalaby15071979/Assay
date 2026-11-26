# Changelog

All notable changes to Assay (formerly Sheet Solution) are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Fixed
- A blank `[CHECK]` placeholder block (for example a trailing skeleton from a
  spreadsheet export) no longer aborts a template that has real checks. Fully
  blank blocks are skipped; a template with no filled blocks now says so
  clearly instead of listing empty required fields. The GUI template builder
  also skips blank spreadsheet rows.
- `yaml_lite` now parses flow collections that span multiple lines (e.g.
  `command: ["run",` continued on the next line). A syntactically valid YAML
  file that is not a policy — such as `docker-compose.yml` — is rejected with
  a clear "does not look like an Assay policy" message instead of an
  "unterminated flow value" parse error.

## [0.4.0] — 2026-11-20

The sheet-ops release: policies, a named rules registry, analyze and
compatibility tasks, a fail-closed decision loop in CLI and GUI, plus ops
metrics and a bounded-memory sheet loader. Staged preview; see
`docs/archive/RELEASE_READINESS.md`.

### Added
- **Versioned policy, one schema, three inputs** (`core/policy/`): a plain
  policy answers "what may the machine decide, and what must a person
  confirm?". JSON files, a restricted-YAML subset (no unpinned dependency),
  and a two-column key/value policy sheet (`.csv`/`.xlsx`) all normalise to
  one validated `Policy`. Unknown fields, rules, actions, duplicate ids and
  ambiguous YAML are refused (fail closed). New `parse-policy` command echoes
  what the machine understood. Examples: `examples/policy.example.*`.
- **Named rules registry** (`sheets/rules/`): deterministic rules with stable
  ids (`not_blank`, `is_blank`, `equals`, `numeric_range`, `one_of`, `regex`,
  `date_before`, `cross_column`, `lookup_in`, `unique`). The four legacy
  plain-English predicates now run through this registry, byte-identically.
  The registry and the policy schema share one rule-id vocabulary and refuse
  to load if they ever disagree.
- **`analyze` command**: profiles one sheet (per-column type inference, blank
  and distinct counts, numeric/date min-max) into a deterministic CSV + JSON
  pack with a ledger entry.
- **`compatibility` command**: a first-class ops task distinct from row-level
  compare — checks required columns, cross-sheet type agreement and policy
  value domains, returning a defensible COMPATIBLE / INCOMPATIBLE verdict.
  Exit status 1 means INCOMPATIBLE.
- **Fail-closed decision loop** (`sheets/decisions.py`, `sheets/actions.py`):
  findings become `PROPOSED` decisions and can only reach `APPLIED` through a
  recorded human confirmation (`approve`), never by a machine guess. A denial
  (`decline`) applies nothing and always leaves the remaining declared options
  plus a `flag_for_human` fallback; a human may `re-propose` an alternative,
  which still needs approval. `APPLIED` is terminal. Every transition requires
  a named actor. Named action executors are a fixed registry (no code from a
  policy is ever executed) and share one id vocabulary with the schema.
- **`decisions` command**: `plan` turns a run's `check-results.csv` + policy
  into deterministic `decisions.json` proposals; `decide` records
  approve/decline/re-propose/apply with the whole lifecycle written to the
  hash-chained ledger; `list` shows current states. Applying an approved action
  emits a `corrected-copy.jsonl`. Actor and note stay in the ledger, never in
  the deterministic projection.
- **GUI decision console**: a third "Decide" tab runs the whole loop in the
  browser — drop a policy, plan proposals, then act on colour-coded decision
  cards (deny, choose an alternative, approve, apply). Offline endpoints
  `/api/decisions` (list + ledger evidence), `/api/decisions/plan` and
  `/api/decisions/decide` reuse the CLI engine, so GUI and CLI are identical.
  A browser E2E drives deny → alternatives → approve → apply with zero page
  errors; pack export now includes `decisions.json` and the corrected copy.
- **Ops `metrics` command** (`sheets/metrics.py`): an honest, deterministic
  summary of a run pack — checks the machine decided vs checks needing a person,
  and findings resolved vs outstanding. There is no "auto-resolve" claim:
  every failed check still waits for a named human. Writes `metrics.json` and a
  ledger entry.

### Changed
- **Bounded-memory sheet loading**: `_load_sheet` now streams rows and fails
  closed past a row cap (default 500,000; `--max-rows N`, `0` disables) so a
  huge or adversarial sheet cannot exhaust memory. Applied to `run`,
  `compare`, `analyze`, `compatibility` and `load-sheet`, and the GUI loader.

## [0.3.0] — 2026-11-20

### Added
- **Doc-consistency gate** (`scripts/check-doc-consistency.py`): version,
  Python floor and status claims are checked against `pyproject.toml` and
  `README.md`; live docs may not hardcode a drifting test count or claim a
  digital signature.
- **Security CI job**: Bandit, `pip-audit`, a pattern secret scan and a
  fail-closed full-history secret scanner (`tooling/security/`).
- **Durable run/compare ledger** (`sheets/ledger.py`): an intent is written
  before work starts and a result after, so an interrupted run leaves a
  recoverable pending intent; the ledger is hash-chained and locally
  anchorable. New `ledger` CLI command (`verify`, `pending`, `tail`,
  `anchor`, `check-anchor`).
- **Release readiness record** (`docs/archive/RELEASE_READINESS.md`) separating the CI
  verification gate from the release decision.
- **Scale smoke** (`scripts/scale-stress.py`) and **CLI/GUI parity test**
  (`tests/test_parity.py`).
- CI: Python 3.11/3.12/3.13 matrix, clean-venv wheel install + CLI smoke,
  SBOM, and an aggregated release-gate job.

### Fixed
- `CHANGELOG.md` now starts with its `# Changelog` title (the 0.2.1 block
  had been inserted above it).
- Removed hardcoded test-count claims from live docs; the count had drifted
  from the actual suite.

## [0.2.1] — 2026-11-18

### Fixed
- **GUI drag-and-drop was completely broken**: a missing `for` loop header in
  the drop-zone wiring made the entire JS invalid (`SyntaxError: Unexpected
  token '}'`), so no file was ever uploaded and every button stayed
  inactive — the GUI was effectively a static design. Restored the loop;
  verified by a real-browser DOM-drag-and-drop regression test (now in CI).

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
  ingest / mapping) under `src/sheet_solution/core/` — the inherited tests
  pass unchanged against the copied engine (see `docs/archive/PROVENANCE.md`).
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
