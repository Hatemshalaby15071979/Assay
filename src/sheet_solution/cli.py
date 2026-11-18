"""Sheet Solution — CLI.

One command surface, fully offline, deterministic:

    python -m sheet_solution load-sheet    --sheet PATH [--key-col NAME] [--json OUT]
    python -m sheet_solution parse-template --template PATH [--sheet PATH]
    python -m sheet_solution run          --sheet PATH --template PATH --out DIR [--as-of ISO]
    python -m sheet_solution verify        --out DIR

`run` is the headline command: load the daily sheet, apply the user's
plain-English checks, and emit an auditable, hash-chained report pack plus
a structured audit log. Image checks that need a human are flagged,
extracted, and logged — never guessed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sheet_solution import __version__
from sheet_solution.core.errors import SignoffError
from sheet_solution.sheets import template, runner, report, images

# Re-export the inherited spine CLI surface so the signoff test suite
# (tests/conftest.py) resolves cli._render_artifacts / cli._write_atomic /
# cli.cmd_* against the copied engine unchanged.
from sheet_solution.core import cli as _core_cli
from sheet_solution.core.cli import (
    _render_artifacts, _write_atomic, csv_field,
    cmd_build, cmd_demo, cmd_parse_questionnaire, cmd_validate_mapping,
    cmd_verify_pack, _as_of, _fixtures_root,
)  # noqa: F401  (re-exported for the inherited test suite)
# Attributes the inherited test suite reaches through the top-level CLI object
# (monkeypatch targets + cfg lookups). They belong to the core CLI.
from sheet_solution.core import config as cfg  # noqa: F401
import tempfile  # noqa: F401  (core CLI's atomic-write staging; re-exposed)


def _load_sheet(path: Path) -> tuple[list[dict], str, bool]:
    """Return (rows, key_col, is_xlsx). Fails closed on unreadable input."""
    ext = path.suffix.lower()
    if ext == ".xlsx":
        try:
            import openpyxl  # type: ignore[import-untyped]
        except ImportError as exc:
            raise SignoffError(
                f"{path.name}: .xlsx needs the 'xlsx' extra — "
                "pip install 'sheet_solution[xlsx]'") from exc
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        grid = [list(r) for r in ws.iter_rows(values_only=True)]
        if not grid:
            raise SignoffError(f"{path.name}: xlsx has no rows")
        header = [str(c) if c is not None else "" for c in grid[0]]
        rows = [{header[i]: (r[i] if i < len(r) else "")
                 for i in range(len(header))}
                for r in grid[1:]]
        return rows, "row", True
    if ext == ".csv":
        import csv
        with path.open(encoding="utf-8-sig") as fh:
            reader = list(csv.reader(fh))
        if not reader:
            raise SignoffError(f"{path.name}: empty CSV")
        header = reader[0]
        rows = [{header[i]: (r[i] if i < len(r) else "")
                 for i in range(len(header))}
                for r in reader[1:] if any(c.strip() for c in r)]
        return rows, "row", False
    raise SignoffError(f"{path.name}: unsupported sheet type (expected .xlsx or .csv)")


def cmd_load_sheet(args) -> int:
    rows, key, is_xlsx = _load_sheet(Path(args.sheet))
    out = Path(args.json_out) if args.json_out else None
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(
            {"key_col": key, "is_xlsx": is_xlsx, "rows": rows}, indent=1),
            encoding="utf-8")
    print(f"loaded {len(rows)} row(s) from {args.sheet} (key column: {key})")
    return 0


def cmd_parse_template(args) -> int:
    config = template.parse_template(Path(args.template), args.sheet or "")
    print(template.config_echo(config))
    print(f"\npersona: {config.persona}, {len(config.checks)} check(s)")
    for c in config.checks:
        mode = "machine" if c.machine_can_check else "HUMAN REVIEW"
        print(f"  {c.check_id} [{mode}] {c.what_is_this_check_for}")
    return 0


def cmd_run(args) -> int:
    config = template.parse_template(Path(args.template), args.sheet)
    rows, key, is_xlsx = _load_sheet(Path(args.sheet))
    results = runner.run(config, rows, key=key)

    out_dir = Path(args.out)
    artifacts: dict[str, bytes] = {}
    artifacts["check-results.csv"] = report.render_results_csv(results).encode("utf-8")

    # Audit log: structured, machine-readable, with full traceability.
    log_lines = [json.dumps({
        "sheet": args.sheet, "persona": config.persona,
        "rows_loaded": len(rows), "results": [
            {"check_id": r.check_id, "outcome": r.outcome,
             "matched": r.matched_rows, "failed": r.failed_rows,
             "denominator": r.denominator, "detail": r.detail}
            for r in results]})]
    artifacts["audit-log.jsonl"] = ("\n".join(log_lines) + "\n").encode("utf-8")

    # Extract embedded images for any human-review checks (xlsx only).
    extracted = []
    if is_xlsx:
        extracted = images.extract_images(Path(args.sheet), out_dir)
        for ex in extracted:
            print(f"extracted image {ex.out_path} ({ex.bytes} bytes)")

    _write_atomic(out_dir, artifacts)
    print(report.summary(results))
    print(f"report pack -> {args.out}")
    return 0


def cmd_verify(args) -> int:
    out_dir = Path(args.out)
    results_csv = out_dir / "check-results.csv"
    log = out_dir / "audit-log.jsonl"
    if not results_csv.exists() or not log.exists():
        print("NOT-FOUND: missing check-results.csv or audit-log.jsonl", file=sys.stderr)
        return 1
    data = json.loads(log.read_text(encoding="utf-8"))
    print(f"VERIFIED-STRUCTURE: {len(data['results'])} result record(s), "
          f"persona={data['persona']}, rows={data['rows_loaded']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sheet_solution",
        description="Offline, deterministic, auditable sheet-audit platform "
                    "(no network, no model in the check path).")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True,
                                parser_class=argparse.ArgumentParser)

    p = sub.add_parser("load-sheet", help="load a sheet into row records")
    p.add_argument("--sheet", required=True)
    p.add_argument("--json-out", default=None, help="write rows to JSON")
    p.set_defaults(func=cmd_load_sheet)

    p = sub.add_parser("parse-template", help="validate + echo the check template")
    p.add_argument("--template", required=True)
    p.add_argument("--sheet", default="", help="sheet path recorded in the config")
    p.set_defaults(func=cmd_parse_template)

    p = sub.add_parser("run", help="run the checks and emit the report pack + audit log")
    p.add_argument("--sheet", required=True)
    p.add_argument("--template", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("verify", help="re-check a produced report pack structure")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_verify)

    # --- inherited spine subcommands (reused engine: mapping, questionnaire,
    #     build, demo, verify-pack). These are the signoff-derived commands
    #     the 140-test regression suite guards; they run the copied engine.
    p = sub.add_parser("validate-mapping", help="validate a mapping table "
                                                 "without building a pack")
    p.add_argument("--mapping", required=True)
    p.add_argument("--allow-unverified", action="store_true")
    p.set_defaults(func=cmd_validate_mapping)

    p = sub.add_parser("parse-questionnaire", help="extract questions only")
    p.add_argument("--input", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_parse_questionnaire)

    p = sub.add_parser("build", help="build a hash-consistent evidence pack "
                                     "(reused spine engine)")
    p.add_argument("--questionnaire", required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--mapping", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--as-of", default=None, metavar="ISO")
    p.add_argument("--redact", action="store_true")
    p.add_argument("--allow-unverified", action="store_true")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("demo", help="build a full pack from synthetic fixtures")
    p.add_argument("--out", required=True)
    p.add_argument("--as-of", default=None, metavar="ISO")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("verify-pack", help="verify a built pack (hash chain)")
    p.add_argument("--pack", required=True)
    p.set_defaults(func=cmd_verify_pack)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SignoffError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"[IO_ERROR] {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001 — last-resort honesty
        print(f"[INTERNAL] unexpected failure: {exc}", file=sys.stderr)
        return 4
