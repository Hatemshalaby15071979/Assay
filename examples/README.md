# Examples

Everything here is **synthetic** — no real customer data, no PII.

- `example-sheet.xlsx` — a small daily sheet (applicant rows + an embedded
  passport-style photo). This is what the CI Docker run and `make run` use.
- `compare-baseline.xlsx` + `compare-new.xlsx` — a two-sheet pair for the
  `compare` command.
- `policy.example.json`, `policy.example.yaml`, `policy-sheet.example.csv` —
  the same policy in three formats (JSON, restricted YAML, key/value sheet).
  All normalise to one schema. `parse-policy` echoes what was understood:
  ```
  python -m sheet_solution parse-policy --policy examples/policy.example.yaml
  ```
- `check-template.example.txt` — a filled-in check template covering all
  three check kinds:
  - `no blank` (machine) — a value must be present
  - `>= 60` (machine, numeric threshold)
  - `machine_can_check = no` (human review) — the tool extracts the image and
    a human confirms it; the decision is logged, never guessed

## Try it in 3 commands

```bash
pip install "sheet-solution[xlsx]"
python -m sheet_solution run \
  --sheet examples/example-sheet.xlsx \
  --template examples/check-template.example.txt \
  --out out/report
python -m sheet_solution verify --out out/report
```

You get:

- `out/report/check-results.csv` — the report (one row per check, with
  matched/failed/denominator and the failing row ids)
- `out/report/audit-log.jsonl` — the structured, machine-readable log
- `out/report/media/` — any embedded images a check needed a human to review

## Compare two sheets

When your task is "these two sheets should agree — what changed?" use the
`compare` command (also available as the **Compare two sheets** tab in the
GUI). Give it a row-key column, the columns to compare, and an optional
numeric tolerance:

```bash
python -m sheet_solution compare \
  --sheet-a examples/compare-baseline.xlsx \
  --sheet-b examples/compare-new.xlsx \
  --key item_id --fields amount,status \
  --out out/compare
```

You get:

- `out/compare/compare-report.csv` — one row per item, each labelled
  `MATCHED` / `CHANGED` / `ONLY-IN-A` / `ONLY-IN-B`, with the exact fields
  that changed and the values on both sides (full traceability)
- `out/compare/compare-log.jsonl` — the structured log (totals + inputs)

A `CHANGED` row names the differing columns; `ONLY-IN-A`/`ONLY-IN-B` are
rows present on one side only. The result is a deterministic count, never a
soft "looks the same".
