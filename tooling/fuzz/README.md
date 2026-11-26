# Assay — Fuzzing Infrastructure

This directory contains the fuzzing corpus and harness for the DOCX/XLSX parsing
stack. Fuzzing is planned for pre-stable release validation.

## Directory Structure

```
tooling/fuzz/
├── README.md              # This file
├── corpus/                # Seed corpus (git-ignored)
│   ├── docx/
│   │   ├── minimal.docx
│   │   └── template.docx
│   └── xlsx/
│       ├── minimal.xlsx
│       └── sheet.xlsx
└── harness.py           # Fuzzing entry point (to be implemented)
```

## Current Status

**Staged Preview (0.4.0):** Fuzzing harness not yet implemented. The parser stack uses:
- `defusedxml` for hardened XML parsing
- Size caps on sheet dimensions (`--max-rows` default 500,000)
- Streaming load to fail closed on memory exhaustion

## Planned Pre-Stable Implementation

1. Create corpus with samples from `examples/`
2. Implement `harness.py` using `python-afl` or `libflame`
3. Add CI job to run fuzzing against corpus nightly
4. Integrate with GitHub Actions on pull requests

## Fuzz Targets

- `src/sheet_solution/sheets/reader.py` - XLSX/CVS loading
- `src/sheet_solution/core/questionnaire_parsers.py` - DOCX parsing
- `src/sheet_solution/core/policy/yaml_lite.py` - Policy YAML parsing

See [RELEASE_READINESS.md](../../docs/archive/RELEASE_READINESS.md#closure-of-open-findings) for status.