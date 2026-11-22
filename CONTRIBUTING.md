# Contributing

Assay is a deterministic, offline tool. Keep it that way.

## Golden rules

1. **No network in the check path.** `scripts/check-offline.py` AST-scans
   every module and fails on any `socket`/`urllib`/`requests`/model-SDK
   import or outbound call. Do not add one.
2. **The machine never guesses.** A check either passes, fails, or is
   `PENDING-HUMAN`. There is no third "maybe" and no model in between.
3. **Determinism.** Identical inputs must produce byte-identical outputs.
   No wall clock, no random. `scripts/check-determinism.py` proves it.
4. **PII stays local.** Nothing leaves the user's machine. Embedded images
   are extracted on-device, never uploaded.
5. **No silent partial runs.** `run` and `compare` write an intent before
   work and a result after (`sheets/ledger.py`). Do not bypass the ledger or
   make a failure look like a completion.

## Naming

The distribution and console script are `assay`; the import package is
`sheet_solution`. Keep that split unless you are doing a full migration —
`python -m sheet_solution` and `assay` must stay the same entry point.

## Workflow

```bash
make all          # scaffold + offline + doc consistency + tests + spine demo
make check-docs   # version / Python floor / status claims agree
make test-cov     # tests with coverage
make scale        # bounded compare smoke (not a capacity claim)
make security     # fail-closed full-history secret scan
./run.sh examples/example-sheet.xlsx examples/check-template.example.txt out/report
```

When you add a machine-checkable rule to `sheets/runner.py`, add a test in
`tests/test_sheets.py` that proves it (a passing row, a failing row, and the
human-routing case). When you add a new output artifact, extend
`report.py` and the `check-results` contract, and add a
formula-injection test (a cell whose value starts with `=`).

## What to keep out of this repo

- Real customer / client data. Use the synthetic fixtures.
- Any AI model or LLM dependency.
- Cloud endpoints.
