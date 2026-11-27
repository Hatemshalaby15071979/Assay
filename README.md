<div align="center">

<img src="https://raw.githubusercontent.com/Hatemshalaby15071979/Helix-Solutions/main/assets/helix-solutions-logo.png"
     alt="Helix Solutions" width="72" height="72">

# Assay

Assay checks a spreadsheet (Excel or CSV) against checks you write in plain English,
and hands back a report you can stand behind — what passed, what failed, and exactly
which rows are the proof. It runs entirely offline, on your own machine. Built for
auditors and verifiers on operational floors.

*by Helix Solutions*

</div>

## What this is and why it's here

Every day on a contact-centre floor, someone has to open a sheet, check what they were
told to look for, and write up what passed and what didn't. That work is slow, and the
write-up is only as good as the person's attention on that day.

Assay does that checking for you — offline, on your own machine, with no cloud and no
AI model in the check path. Your data (including the passport photos a sheet may carry)
never leaves the machine it runs on.

The important part is what the tool *won't* do: it never guesses. Anything that is
machine-checkable is checked deterministically. Anything that genuinely needs a human
eye (an image, a judgement call) is flagged `PENDING-HUMAN`, the image is pulled out
locally, and a named person confirms it — the tool records *who* and *when*. Every
result in the pack is traceable to the source row, and the pack is hash-chained so you
can re-verify it later.

Assay was previously named **Sheet Solution**; the Python import package keeps that
name (`sheet_solution`) so existing scripts still work. The deterministic spine —
hash chain, report renderers, verification, offline guarantees, and the full test
suite — is reused from **Signoff 0.1.0** (lineage recorded in
`docs/archive/PROVENANCE.md`); the sheet-compare layer, CLI, GUI, and distribution are
new to this repository.

## What you get

- **An audit you can defend.** A CSV report — one row per check, with the exact
  failing rows — plus a structured audit log, reproducible from the pack itself.
- **A compare tool.** Ask "these two sheets should match — what changed?" and get every
  row labelled MATCHED / CHANGED / ONLY-IN-A / ONLY-IN-B with field-level traceability.
- **Plain-English checks.** The check template is plain text — no YAML, no JSON, no
  coding. You write what to look for; the tool does the rest.
- **A decision loop with a human in charge.** Failed checks become proposals; nothing
  is applied unless a named person approves it, and every step is recorded.
- **Three ways to run it, all offline:** a fast CLI, a click-and-drag GUI on your own
  machine, or a Docker image that runs with the network switched off.

## How to use it

1. **Install, then run the one-click path** — downloads nothing at run time; CSV
   needs no extra packages, Excel needs `openpyxl`:

   ```bash
   python3 -m venv .venv && . .venv/bin/activate
   pip install "assay[xlsx]"
   ./run.sh examples/example-sheet.xlsx examples/check-template.example.txt out/report
   ```

   What it does for you: checks the example sheet and writes a report pack you can open.

2. **Re-verify any pack later** — proves the report you received is intact:

   ```bash
   assay verify --out out/report        # -> VERIFIED-STRUCTURE
   ```

   What it does for you: a later auditor (or you, in a month) can prove nothing was
   quietly changed.

3. **Open the GUI** — drag-and-drop files, click, and read colour-coded result cards:

   ```bash
   python -m sheet_solution.gui.main
   ```

   What it does for you: the same guarantees without touching a terminal.

Running from a source checkout without installing: prefix the same commands with
`python -m sheet_solution` instead of `assay`. If the tool refuses a file, the message
names the block or file — it fails closed *before* touching your data; see
`docs/USER-GUIDE.md` (§ "If the tool refuses a file").

## The rules we build by

Assay obeys `CONSTITUTION.md`: **fail closed** (a missing input or authority is a
refusal, never a guess), **evidence before claims** (every published number is
reproducible from this repo), **local-first** (no network in the check path, ever), and
**a human is always in charge** (nothing is applied without a named person's approval).

## Current status

This section is the **single source of truth for project status**; every landing
page, dashboard or report mirrors it and none of them overrides it.

**As of 2026-11-22:** Assay 0.4.0 is a *staged preview candidate* — CI-verified on
Python 3.11–3.13 and offline by construction — **not** an independently audited stable
release; the dated release record and finding register live in
`docs/archive/RELEASE_READINESS.md`.

## Where things live

- `docs/USER-GUIDE.md` — plain-English guide, no coding required.
- `docs/ARCHITECTURE.md` — layers, guarantees, the decision loop.
- `docs/archive/RELEASE_READINESS.md` — the dated release record (finding register, sign-off).
- `docs/archive/PROVENANCE.md` — exactly what was reused from Signoff 0.1.0.
- `examples/` — ready-made sheets, check templates, and policies.
- `tests/` — the offline, deterministic test suite (verification: `PYTHONPATH=src python -m pytest -q`).

## Licence & contact

MIT. Built by Hatem Shalaby — Contact Centre Operations & AI Implementation Lead |
WFM & CX Transformation.

- **GitHub:** [github.com/Hatemshalaby15071979](https://github.com/Hatemshalaby15071979)
- **LinkedIn:** [linkedin.com/in/hatem-shalaby-202902127](https://www.linkedin.com/in/hatem-shalaby-202902127/)
