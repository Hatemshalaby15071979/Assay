<div align="center">

# Sheet Solution

![licence](https://img.shields.io/badge/licence-MIT-blue)
![offline](https://img.shields.io/badge/offline-by-construction-blue)

**Offline by construction** — zero network calls, no cloud, no AI model in
the check path. Your data (including passport photos and PII) never leaves
the machine it runs on.

</div>

## What is this?

Sheet Solution automates a manual daily task: **open a sheet, check what you
were told to look for, write up what passed and what didn't.**

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

## Run it

```bash
# 1. install (offline wheels or pinned set)
python3 -m venv .venv && . .venv/bin/activate
pip install "sheet-solution[xlsx]"        # CSV needs nothing else; xlsx needs openpyxl

# 2. the one-click path (non-technical users)
./run.sh examples/example-sheet.xlsx examples/check-template.example.txt out/report

# 3. or the CLI
python -m sheet_solution run --sheet examples/example-sheet.xlsx \
     --template examples/check-template.example.txt --out out/report
python -m sheet_solution verify --out out/report     # -> VERIFIED-STRUCTURE
```

## Three ways to use it (all offline)

- **CLI** — `python -m sheet_solution …` (fast, scriptable, cron-able).
- **GUI** — `python gui/main.py` opens a local browser UI on `127.0.0.1`.
- **Docker** — the non-root image runs under `--network none`.

## Where the pieces come from

The deterministic spine (hash chain, renderers, verification, offline
guarantees, 151 passing tests) is reused from **Signoff 0.1.0** — see
[`PROVENANCE.md`](PROVENANCE.md) for the exact lineage. The sheet-comparison
layer, CLI, GUI, and distribution are new to this repository.

## Author

Built by Hatem Shalaby.

## Licence

MIT
