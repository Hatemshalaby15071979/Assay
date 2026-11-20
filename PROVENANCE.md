# Sheet Solution — Provenance

Sheet Solution is a **new, independent, deployable** product. It is not a
fork-in-place of the Signoff repository and it does not modify it. This
document records exactly which parts were **reused** from the Signoff 0.1.0
spine and which parts are **new**, so the lineage is honest and auditable.

## Source of the reused spine

- **Reference repo:** `cloned_repos/signoff` (Signoff 0.1.0, MIT licence).
- **Reuse mode:** a *copy* of the deterministic spine, rebranded and
  re-homed under `src/sheet_solution/core/`. The copy is **read-only with
  respect to behaviour**: every inherited test in `tests/` (the
  signoff-derived suite) still passes against the copied engine unchanged,
  which is the proof the reuse was faithful.
- The `signoff/` repository is **never modified**. All Sheet Solution work
  lives in `sheet_solution/`.

## What was copied 1:1 (the "80% spine")

| Sheet Solution path | Signoff 0.1.0 origin | Change on copy |
|---|---|---|
| `src/sheet_solution/core/model/*` | `src/signoff/model/*` | imports rebranded only |
| `src/sheet_solution/core/util/*` | `src/signoff/util/*` | imports rebranded only |
| `src/sheet_solution/core/engine/*` | `src/signoff/engine/*` | imports rebranded; brand strings aligned |
| `src/sheet_solution/core/render/*` | `src/signoff/render/*` | imports rebranded only |
| `src/sheet_solution/core/verify/*` | `src/signoff/verify/*` | imports rebranded only |
| `src/sheet_solution/core/ingest/*` | `src/signoff/ingest/*` | imports rebranded only |
| `src/sheet_solution/core/mapping/*` | `src/signoff/mapping/*` | imports rebranded only |
| `src/sheet_solution/core/{config,errors}.py` | `src/signoff/{config,errors}.py` | imports rebranded only |
| `src/sheet_solution/core/cli.py` | `src/signoff/cli.py` | rebranded; `_fixtures_root` re-rooted |
| `scripts/check-offline.py` | `scripts/check-offline.py` | scan path re-rooted |
| `scripts/check-determinism.py` | `scripts/check-determinism.py` | module name re-rooted |
| `tests/test_*.py` (spine suite) | `tests/test_*.py` | rebranded to the new package |

**Inherited guarantees that survive the copy (verified by the inherited
test suite):** offline (zero network), deterministic (byte-identical output),
fail-closed on every input, hash-chained evidence packs, CSV formula-
injection neutralisation, atomic writes, non-root Docker.

## What is new (the product layer — "sheet_solution")

| New path | Purpose |
|---|---|
| `src/sheet_solution/sheets/template.py` | Plain-English check-template → validated config |
| `src/sheet_solution/sheets/runner.py` | Deterministic check runner (machine rules + human routing) |
| `src/sheet_solution/sheets/report.py` | check-results CSV + summary; formula-neutralised |
| `src/sheet_solution/sheets/images.py` | Embedded-image extraction (xlsx), local-only |
| `src/sheet_solution/sheets/ledger.py` | Durable intent/result audit ledger (new, offline) |
| `src/sheet_solution/cli.py` | Top-level CLI: sheet commands + re-exported spine commands |
| `tests/test_sheets.py` | New-engine tests (template / runner / report / images) |
| `tests/test_scaffold.py` | Rewritten for the shipped-tool tree |
| `gui/main.py` | Offline Flask wrapper around the CLI |
| `run.sh`, `examples/`, `docs/USER-GUIDE.md` | Distribution + end-user docs |

## Design decision that shaped this copy

Sheet Solution is **deterministic + human-in-the-loop, with no AI model in
the check path.** The signoff spine's philosophy — *the machine never
guesses* — is preserved: every machine check is a verifiable rule, and every
image/semantic check is flagged `PENDING-HUMAN` and recorded in the audit
log. This keeps PII local and the output auditable, on any hardware.

## Verification

- The inherited spine suite and the new sheet-layer tests are all green
  (`make test`).
- `scripts/check-offline.py`: scans the runtime tree, zero network
  imports/calls.
- `scripts/check-doc-consistency.py`: version, Python floor and status claims
  agree across live docs.
- `tooling/security/scan_history_secrets.py`: fail-closed scan over every
  reachable commit.
- `signoff/` repository untouched.
