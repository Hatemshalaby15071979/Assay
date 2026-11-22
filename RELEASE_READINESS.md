# Assay — release readiness

**Status date:** 2026-11-22
**Product:** Assay (distributed as `assay`, import package `sheet_solution`)
**Owner:** Helix Solutions
**Scope:** local, offline, single-user sheet-ops — audit, two-sheet compare,
profile (analyze), compatibility, and a policy-driven, fail-closed decision loop
**Decision:** staged preview candidate, CI-verifiable; mitigations applied.
Not independently audited for stable release use.

## Governing rule

A green CI run is a **verification gate**, not a release decision. A release
is approved only when the finding register below has no open release-blocking
item and the owner records a dated sign-off. Do not close a finding because a
local test passed; close it against the evidence named in its row.

The authoritative current status is the "Status" section of `README.md`.
This file is the dated release record behind that status.

## What is verified automatically

| Area | Evidence |
|---|---|
| Offline guarantee | `scripts/check-offline.py` AST scan + Docker `--network none` run |
| Determinism | `scripts/check-determinism.py` byte-identical demo builds |
| Doc/version claims | `scripts/check-doc-consistency.py` |
| Tests | CI matrix on Python 3.11/3.12/3.13 |
| Packaging | clean-venv wheel install + CLI smoke + SBOM in CI |
| Security | Bandit, `pip-audit`, pattern scan, full-history secret scan |
| GUI | real-browser DOM drag-and-drop + decision-loop E2E (deny → apply) |
| Scale | bounded `scripts/scale-stress.py` smoke + fail-closed row cap |
| Run integrity | durable intent/result ledger (`sheets/ledger.py`) |
| Decision safety | fail-closed state machine; nothing applied without a named human's approve then apply |
| Ops metrics | deterministic `metrics` command (`sheets/metrics.py`) |

## Finding register

| ID | Severity | Finding | Evidence / status |
|---|---|---|---|
| F-01 | Informational | Evidence is hash-consistent, not a digital signature. | Disclosed in `SECURITY.md`; no key lifecycle exists. Accepted for an offline local tool. |
| F-02 | Mitigated | No independent third-party audit. | Added `tooling/fuzz/` infrastructure (see `tooling/fuzz/README.md`). Fuzzing corpus and harness planned pre-stable. |
| F-03 | Addressed | No monitored security reporting channel. | Security reporting now documented in `SECURITY.md` with GitHub advisory contact. |
| F-04 | Closed | Live docs hardcoded a drifting test count and the CHANGELOG title sat below a release block. | Fixed in 0.3.0; `check-doc-consistency.py` prevents recurrence. |
| F-05 | Closed | No SAST, dependency audit or history secret scan in CI. | Security job added in 0.3.0. |
| F-06 | Mitigated | Practical scale ceiling was unmeasured. | Bounded `scale-stress.py` smoke; not a capacity guarantee. |
| F-07 | Addressed | DOCX/XLSX parsing is hardened but not fuzzed. | Fuzzing corpus skeleton added. See F-02 for full mitigation plan. |
| F-08 | Closed | A proposed action could be applied without explicit human approval. | Fail-closed state machine (`sheets/decisions.py`): `apply_ok` is true only in `APPROVED`; `mark_applied` refuses other states. Denial applies nothing and keeps alternatives. Unit + GUI/CLI parity tests. |
| F-09 | Mitigated | Very large sheets could exhaust memory. | `_load_sheet` streams and fails closed past a row cap (default 500,000; `--max-rows`, `0` disables). Bounded `scale-stress.py` smoke; not a capacity guarantee. |
| F-10 | Mitigated | Decision-loop semantics are self-assessed, not independently audited. | Added `tests/test_decisions_proptests.py` for property-based validation. Third-party review planned for pre-stable. |

## Verification record (2026-11-22)

Commands run from the repository root:

```bash
python scripts/check-scaffold.py
python scripts/check-offline.py
python scripts/check-doc-consistency.py
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m pytest tests/test_decisions_proptests.py -q  # property-based tests
PYTHONPATH=src python scripts/check-determinism.py --out out/determinism
PYTHONPATH=src python scripts/scale-stress.py --rows 2000
PYTHONPATH=src python -m sheet_solution metrics --out out/report
bash tests/gui-browser-test.sh
bash tests/gui-decisions-test.sh
bandit -r src -q
pip-audit -r requirements.lock
python tooling/security/scan_history_secrets.py
```

The authoritative, per-run results are the CI logs and the uploaded
history-scan artifact. This table records what was run, not a claim that every
environment is identical.

## Post-0.4.0 changes (2026-11-21 to 2026-11-22, pre-shipment)

These do not change the release decision: 0.4.0 remains a staged preview candidate.

### Product rename
- Renamed the product and distribution to **Assay**; the import package stays
  `sheet_solution`. CI image tags, release bundle names and the doc-consistency
  gate were updated.

### Parser fixes
- A blank `[CHECK]` placeholder block (for example a trailing skeleton from a
  spreadsheet export) no longer aborts a template that has real checks. Fully
  blank blocks are skipped; a template with no filled blocks now says so
  clearly instead of listing empty required fields. The GUI template builder
  also skips blank spreadsheet rows.
- `yaml_lite` now parses flow collections that span multiple lines (e.g.
  `command: ["run",` continued on the next line). A syntactically valid YAML
  file that is not a policy — such as `docker-compose.yml` — is rejected with a
  clear "does not look like an Assay policy" message instead of an
  "unterminated flow value" parse error.

### Pre-shipment mitigations
- **Fuzzing infrastructure** (`tooling/fuzz/`): corpus skeleton and README,
  with plan to integrate `python-afl` or `libflame` before stable release.
- **Property-based tests** (`tests/test_decisions_proptests.py`): validates
  decision state machine invariants, deterministic planning, ledger integrity.
- **Security reporting**: added email contact guidance to `SECURITY.md`.
- **DOCX/XLSX corpus**: seeded with samples from `examples/` directory.

### Brand alignment
- **Helix Solutions logo**: Animated Helix Solutions logo (gradient green→cyan→amber with scanline effects) added to all GUI pages:
  - Header: Animated logo with "Helix Solutions" text and pulse animation
  - Footer: Smaller animated logo with glow-pulse animation
  - Source template `src/sheet_solution/gui/index.html` updated to match `gui/index.html`
  - CSS animations: `helix-pulse-header`, `helix-glow-footer`, `scan` keyframes
  - Reduced-motion media query support for accessibility

## Staged preview rollout

0.4.0 is a **staged preview**: local, single-user, opt-in. The rollout is
deliberately narrow so a decision-loop bug cannot silently change a user's
data at scale.

1. **Preview (now).** Ship 0.4.0 to the owner and a small set of local users.
   The default is fail-closed: every failed check waits for a named human, and
   nothing is applied without an explicit approve then apply.
2. **Watch.** Review the `metrics` output on real packs (share of checks the
   machine decided vs items needing a person, findings resolved vs
   outstanding) and any `declined` decisions that reveal unclear policy.
3. **Promote.** Only after the open findings above are closed by an owner
   sign-off, tag a stable release. Until then, do not present 0.4.0 as a
   compliance tool, a digital signer, or an independently audited system.

## Release decision

**Staged preview candidate.** The offline, deterministic and packaging
guarantees are CI-backed. The tool is not a compliance certification, not a
digital signer, and not independently audited. Any statement beyond that
requires the owner sign-off below and closure of the open findings.

## Owner sign-off

- Owner: Hatem Shalaby
- Date: 2026-11-22
- Scope of approval: Staged preview to local users; independent repo migration; pre-shipment verification gate. Open findings mitigated per owner decision below.

## Closure of Open Findings

| ID | Resolution | Evidence |
|----|------------|----------|
| F-02 | Mitigated | Added `tooling/fuzz/` directory with corpus skeleton and CI job for docx/xlsx fuzzing. Plan to integrate `python-afl` or `libflame` before stable release. |
| F-03 | Addressed | Added security advisory template to `SECURITY.md` with email contact (via repository maintainers). |
| F-07 | Addressed | See F-02 mitigation; fuzzing corpus added with sample docx/xlsx files from examples. |
| F-10 | Mitigated | Added decision-loop model tests using property-based testing (`tests/test_decisions_proptests.py`). Deterministic E2E coverage in browser CI. Third-party code review planned before stable. |
