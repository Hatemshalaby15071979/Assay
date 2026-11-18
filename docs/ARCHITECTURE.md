# Sheet Solution — Architecture

## Overview

Sheet Solution is a **deterministic, offline, auditable** sheet-audit
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

## Layers

| Layer | Path | Responsibility | New / reused |
|---|---|---|---|
| Sheet layer | `sheets/` | template parse, check runner, report, image extract | **new** |
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

## Data flow

1. **Input:** sheet (.xlsx/.csv) + plain-English check-template.
2. **Validate template:** parse into a `CheckConfig`; fail closed on any
   missing/ambiguous field. Prove the config back to the user.
3. **Load sheet:** rows into records; detect xlsx for image extraction.
4. **Run checks:** machine rules -> PASS/FAIL; human checks -> PENDING-HUMAN.
5. **Extract images:** embedded images pulled to `out/report/media/`.
6. **Write pack:** `check-results.csv` + `audit-log.jsonl` + media, atomically.
7. **Verify:** replay the structure; `VERIFIED-STRUCTURE` on a clean pack.

## Versioning

- 0.1.0 — initial released version. Spine from Signoff 0.1.0 (MIT).

See [`PROVENANCE.md`](../PROVENANCE.md) for the exact reuse lineage.
