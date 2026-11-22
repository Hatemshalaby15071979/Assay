# Assay — Architecture

## Overview

Assay is a **deterministic, offline, auditable** sheet-audit
platform. It answers one question: *"given this sheet and the things I was
told to look for, what passes, what fails, and what needs a human?"*

It produces a **report pack** you can re-verify later:

- `check-results.csv` — one row per check (PASS / FAIL / PENDING-HUMAN),
  with matched/failed/denominator counts and the failing row ids
- `audit-log.jsonl` — structured, machine-readable log of the whole run
- `media/` — embedded images extracted for any check that needed a human
- a hash chain over the pack so a later `verify` detects tampering

Two personas, inferred from how you write the checks:

- **auditor** — pass/fail against a standard, with notes.
- **verifier** — expected values must be present; report the misses.

## Naming

- **Product:** Assay (formerly Sheet Solution).
- **Distribution / CLI:** `assay` — the installed console script.
- **Import package:** `sheet_solution` — kept deliberately so
  `python -m sheet_solution …` and existing scripts keep working. `assay`
  and `python -m sheet_solution` are the same entry point.
- **Images / bundles:** Docker tags and release bundles use `assay`.

The doc-consistency gate checks that `README.md` names `Assay {version}`.

## Layers

| Layer | Path | Responsibility | New / reused |
|---|---|---|---|
| Sheet layer | `sheets/` | template parse, check runner, report, image extract, policy rules, decisions/actions | **new** |
| Policy | `core/policy/` | one validated schema from JSON / safe-YAML / policy sheet | new |
| CLI | `cli.py` | sheet commands + re-exported spine commands | new |
| GUI | `gui/` | offline web shell around the CLI | new |
| Spine | `core/` | model, util, engine (hash chain), render, verify, ingest, mapping | **reused** from Signoff 0.1.0 |

## The two-layer check model

```
LAYER 1 — deterministic engine (inherited spine + sheet runner)
   parse sheet -> extract rows/cells -> run machine rules ->
   PASS / FAIL with full row traceability. Runs on any hardware, offline.

LAYER 2 — human-in-the-loop (the non-deterministic part, logged)
   image/semantic checks -> extract the embedded image locally ->
   a named human confirms -> recorded in the audit log.
   The tool never decides the image; it records that a human did.
```

There is **no AI model in the check path.** This is the design decision that
keeps PII local and the output auditable on any hardware.

## Deterministic guarantees (inherited, verified by tests)

- **Offline:** `check-offline.py` AST-bans network imports/calls.
- **Determinism:** `check-determinism.py` — byte-identical across runs.
- **Never guesses:** uncheckable rules become `PENDING-HUMAN`, never a guess.
- **Fail closed:** bad template or unreadable sheet aborts, nothing partial.
- **Hash chain:** SHA-256 over canonical JSON; `verify` replays it.
- **CSV injection neutralised:** report fields starting with `=` are quoted.
- **Claims consistent:** `check-doc-consistency.py` checks version, Python
  floor and status claims against `pyproject.toml` and `README.md`.
- **Security scanned:** CI runs Bandit, `pip-audit` and a fail-closed
  full-history secret scan.

## Durable run ledger (new in 0.3.0)

`run` and `compare` write a hash-chained ledger under `<out>/.audit/`:

- an **intent** event before any work starts;
- a **result** event after the pack is written, linked by sequence and hash;
- a `pending` view for an intent whose result never arrived (an interrupted
  process), so a partial run is visible rather than silent;
- optional local **anchors** (chained receipt files) that detect truncation,
  rewrite or reorder.

The ledger is a runtime evidence log with wall-clock timestamps; the report
pack stays byte-identical. Anchoring is local-only — there is no network and
no external timestamp authority. This is separate from the inherited pack
hash chain: the pack chain covers the report artifacts, the ledger covers the
run lifecycle.

```bash
python -m sheet_solution ledger --out out/report verify
python -m sheet_solution ledger --out out/report pending
python -m sheet_solution ledger --out out/report anchor
```

## The decision loop (fail closed, no audit theater)

The point of the loop is that a finding always leads to something a person can
*do*, and a refusal never dead-ends. It is a pure state machine in
`sheets/decisions.py`:

```
PROPOSED --approve(actor)--> APPROVED --apply(actor)--> APPLIED (terminal)
    |                          |
    | decline(actor)           | decline(actor)
    v                          v
DECLINED --re-propose(actor, alternative)--> PROPOSED
```

Fail-closed invariants:

- **No apply without approval.** `apply_ok()` is true only in `APPROVED`;
  `mark_applied()` refuses any other state. A proposal or a denial can never
  be applied.
- **A denial keeps options.** `decline()` applies nothing and `alternatives()`
  still returns the other declared options; if none remain it returns the
  `flag_for_human` safe fallback, so there is always a way to act.
- **A named human is mandatory.** Every transition requires a non-empty
  actor; illegal transitions raise `DecisionError`. Re-proposing selects a
  declared alternative (or the safe fallback) and still needs a fresh approval.
- **Policies name, never execute.** `sheets/actions.py` is a fixed registry of
  pure row transforms (`tag_row`, `flag_for_human`, `emit_corrected_copy`,
  `drop_row`, `escalate`); a policy can only name one, never carry code. The
  action ids are the exact vocabulary in `core/policy/schema.ACTION_NAMES`;
  the module refuses to load if the two ever disagree (as does the rules
  registry with `RULE_NAMES`).
- **Runtime evidence stays out of deterministic artifacts.** Actor and note go
  to the ledger (`decision.proposed` / `decision.recorded` / `decision.applied`);
  `decisions.json` is a deterministic projection (ids, finding, options, state)
  with no clock or human identity.

`build_findings()` maps failed rows from `check-results.csv` to proposals,
using the policy's `on_fail.actions` or the safe fallback when a check declares
none. The `decisions` CLI command (`plan` / `list` / `decide`) exposes the whole
loop; applying an approved action writes `corrected-copy.jsonl`.

The GUI's third "Decide" tab is a thin client over the same engine:
`/api/decisions/plan` (build proposals from a pack + uploaded policy),
`/api/decisions` (list states + ledger evidence) and `/api/decisions/decide`
(record a transition) call `cmd_decisions` directly, so CLI and GUI cannot
drift. Pack paths are confined to the local content-named spool. A browser E2E
(`tests/gui-decisions-test.sh`) drives deny → alternatives → approve → apply
through real DOM drops and asserts zero page errors, complementing the Flask
API tests in `test_gui_decisions.py`.

## Input parsing (fail closed)

Templates and policies are parsed by small in-repo parsers, not PyYAML.
The policy YAML subset supports block mappings/sequences, flow collections
(including ones that span several lines), quoted strings, numbers, booleans
and null; it refuses anchors, aliases, tags, merge keys, multi-document
streams and tabs. A syntactically valid YAML file that is not a policy (a
compose file, a CI workflow) is rejected with a "does not look like an Assay
policy" message rather than a low-level parse error.

## Data flow

1. **Input:** sheet (.xlsx/.csv) + plain-English check-template.
2. **Validate template:** parse into a `CheckConfig`; fail closed on any
   missing/ambiguous field. A `[CHECK]` block with every field blank is a
   placeholder and is skipped; a partially filled block is refused and the
   error names the block and the missing fields. Prove the config back to
   the user.
3. **Load sheet:** rows into records; detect xlsx for image extraction.
4. **Run checks:** machine rules -> PASS/FAIL; human checks -> PENDING-HUMAN.
5. **Extract images:** embedded images pulled to `out/report/media/`.
6. **Write pack:** `check-results.csv` + `audit-log.jsonl` + media, atomically.
7. **Verify:** replay the structure; `VERIFIED-STRUCTURE` on a clean pack.

## Versioning

- Unreleased — renamed to Assay (distribution `assay`; import package
  unchanged); multi-line YAML flow support; blank template placeholders are
  skipped and non-policy YAML is rejected with a clear message.
- 0.4.0 — sheet-ops release: versioned policy (one schema, three inputs),
  named rules registry, `analyze` / `compatibility`, fail-closed decision loop
  (CLI + GUI), ops `metrics`, and a bounded-memory row cap. Staged preview.
- 0.3.0 — doc-consistency gate, security CI, durable run ledger, scale smoke
  and CLI/GUI parity test.
- 0.1.0 — initial released version. Spine from Signoff 0.1.0 (MIT).

See [`PROVENANCE.md`](../PROVENANCE.md) for the exact reuse lineage.
