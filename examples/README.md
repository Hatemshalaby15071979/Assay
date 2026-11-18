# Examples

Everything here is **synthetic** — no real customer data, no PII.

- `example-sheet.xlsx` — a small daily sheet (applicant rows + an embedded
  passport-style photo). This is what the CI Docker run and `make run` use.
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
