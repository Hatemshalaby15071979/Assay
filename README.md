<div align="center">

# Assay

<img src="gui/logo.svg" alt="Helix Solutions logo" width="48" height="48" style="vertical-align:middle;margin-right:0.5rem">

![licence](https://img.shields.io/badge/licence-MIT-blue)
![offline](https://img.shields.io/badge/offline-by-construction-blue)

<p float="left">
  <strong>Assay 0.4.0</strong><br>
  <span style="font-size:0.9em;color:#93aaa0">by Helix Solutions</span>
</p>

**Proof, not guesses.**

**Offline by construction** — zero network calls, no cloud, no AI model in
the check path. Your data (including passport photos and PII) never leaves
the machine it runs on.

</div>

## Status

**Assay 0.4.0** — a pre-release candidate, offline by construction.
This README is the single source of truth for project status; the dated
release record, finding register and owner sign-off live in
[`RELEASE_READINESS.md`](RELEASE_READINESS.md).

## What is this?

Assay automates a manual daily task: **open a sheet, check what you were
told to look for, write up what passed and what didn't.**

You give it two things:

1. A sheet (Excel `.xlsx` or `.csv`) — often one that arrives by email,
   with structured values and sometimes embedded images (e.g. passport
   photos).
2. A check-template you fill in **plain English** — what to look for. No
   YAML, no JSON, no coding.

It produces a **report pack**: a CSV report (one row per check: passed /
failed / needs-a-human, with the exact failing rows), a structured audit
log, and any embedded images a check needed a person to confirm. Every
result is traceable to the source row, and the pack is hash-chained so you
can re-verify it later.

## The two people it's built for

- **The auditor** — checks the sheet against a compliance standard; passes
  or fails it and records notes.
- **The verifier** — has a template / list of expected values; checks each
  one is present with the right value and reports the misses.

You pick the persona by how you write the checks; the tool infers it.

## The thing that makes it not a toy

**The machine never guesses.** Every machine-checkable rule is a
deterministic, verifiable check. Anything that genuinely needs a human eye
(an image, a judgement call) is flagged `PENDING-HUMAN`, the image is
extracted locally, and a named human confirms it — the tool records *who*
and *when*, and logs that a human reviewed it. There is no third outcome and
no model hiding in the middle. That's why the output is trustworthy: it
tells you exactly what it checked, what it couldn't, and who closed the gap.

## Documentation

- [User guide](docs/USER-GUIDE.md) — plain English, no coding required.
- [Architecture](docs/ARCHITECTURE.md) — layers, guarantees, decision loop.
- [Release readiness](RELEASE_READINESS.md) — finding register and sign-off.
- [Provenance](PROVENANCE.md) — what was reused from Signoff 0.1.0.
- [Contributing](CONTRIBUTING.md) — golden rules and workflow.
- [Brand sheet](docs/brand/assay-logo.html) — wordmark and lockups (offline HTML).

## Run it

```bash
# 1. install (offline wheels or pinned set)
python3 -m venv .venv && . .venv/bin/activate
pip install "assay[xlsx]"                 # CSV needs nothing else; xlsx needs openpyxl

# 2. the one-click path (non-technical users)
./run.sh examples/example-sheet.xlsx examples/check-template.example.txt out/report

# 3. or the CLI
assay run --sheet examples/example-sheet.xlsx \
     --template examples/check-template.example.txt --out out/report
assay verify --out out/report            # -> VERIFIED-STRUCTURE
assay ledger --out out/report verify     # intent/result chain
```

Running from a source checkout without installing: prefix the same commands
with `python -m sheet_solution` instead of `assay` (the import package keeps
its original name).

Every run writes a durable intent before it starts and a result after it
finishes (`out/report/.audit/ledger.jsonl`). If the process is interrupted,
`ledger --out out/report pending` shows the unfinished intent instead of
silently leaving a partial report.

If a template or policy is refused, see
[common errors](docs/USER-GUIDE.md#if-the-tool-refuses-a-file). The tool fails
closed before touching your data, and the message names the block or file.

## Also: compare two sheets

When your task is *"these two sheets should match — what changed?"*, use the
`compare` command (or the **Compare two sheets** tab in the GUI). It labels
every row MATCHED / CHANGED / ONLY-IN-A / ONLY-IN-B with field-level
traceability and an optional numeric tolerance — a defensible count, never a
"looks the same".

```bash
assay compare \
  --sheet-a examples/compare-baseline.xlsx \
  --sheet-b examples/compare-new.xlsx \
  --key item_id --fields amount,status --out out/compare
```

## Beyond pass/fail: policies, analyze, compatibility

Day-to-day sheet work is more than pass/fail. Assay now handles the
operations tasks people actually repeat:

- **Decide with a policy, not a guess.** A plain policy file (JSON or a small
  YAML subset) — or a two-column policy sheet you drop in — declares the
  rules and what a failure may do (`tag_row`, `flag_for_human`, ...). Every
  input format normalises to one validated schema; anything unknown is
  refused. Declared actions are acted on only after a human confirms them.
  Validate and echo what the machine understood:
  ```
  assay parse-policy --policy examples/policy.example.yaml
  ```
- **Decide, fail closed.** Failed checks become proposals; nothing is applied
  unless a named human approves it. Denying an action applies nothing and keeps
  the other options (plus a `flag_for_human` fallback) available for a human to
  choose. From a completed `run` pack:
  ```
  assay decisions plan --out out/run --policy policy.json
  assay decisions decide --out out/run --finding-id F-... \
    --action approve --actor alice          # approve | decline | re-propose | apply
  assay decisions list --out out/run
  ```
  Approving is not applying: only `decide --action apply` executes the named
  action and writes `corrected-copy.jsonl`. Every transition is recorded in the
  hash-chained ledger with the human actor; the deterministic `decisions.json`
  never carries that runtime evidence. The same loop is in the GUI's **Decide**
  tab — drop a policy, plan proposals, then deny / choose an alternative /
  approve / apply on visual cards.
- **Measure it honestly.** `metrics` reports, from a run pack, how many checks
  the machine decided vs how many need a person, and how many findings are
  resolved vs outstanding — no "auto-resolve" claim.
  ```
  assay metrics --out out/run
  ```
  Large sheets are bounded: loading fails closed past `--max-rows`
  (default 500,000; `0` disables) instead of exhausting memory.
- **Analyze** a sheet: types, blanks, distinct counts, numeric/date ranges.
  ```
  assay analyze --sheet examples/example-sheet.xlsx --out out/analyze
  ```
- **Compatibility**: can two sheets be combined? Checks required columns,
  cross-sheet type agreement and allowed value domains from a policy — a
  defensible COMPATIBLE / INCOMPATIBLE (exit 1), not a "looks fine".
  ```
  assay compatibility \
    --sheet-a baseline.xlsx --sheet-b new.xlsx --policy policy.json --out out/compat
  ```

All of these are offline, deterministic and write the same durable
intent/result ledger as `run`/`compare`.

## Three ways to use it (all offline)

- **CLI** — `assay …` (fast, scriptable, cron-able), including `run` (audit)
  and `compare` (two sheets).
- **GUI** — `python -m sheet_solution.gui.main` opens a local browser UI on
  `127.0.0.1`: drag-and-drop files, click, read colour-coded result cards.
- **Docker** — the non-root image runs under `--network none`.

## Where the pieces come from

The deterministic spine (hash chain, renderers, verification, offline
guarantees, and the full test suite) is reused from **Signoff 0.1.0** — see
[`PROVENANCE.md`](PROVENANCE.md) for the exact lineage. The sheet-comparison
layer, CLI, GUI, and distribution are new to this repository.

Assay was previously named **Sheet Solution**; the Python import package is
still `sheet_solution` so existing scripts and the module entry point keep
working.

## Author

Built by Hatem Shalaby.

## Licence

MIT
