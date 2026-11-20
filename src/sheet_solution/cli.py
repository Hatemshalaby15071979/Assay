"""Sheet Solution — CLI.

One command surface, fully offline, deterministic:

    python -m sheet_solution load-sheet    --sheet PATH [--key-col NAME] [--json OUT]
    python -m sheet_solution parse-template --template PATH [--sheet PATH]
    python -m sheet_solution run          --sheet PATH --template PATH --out DIR [--as-of ISO]
    python -m sheet_solution decisions    plan --out DIR --policy PATH
    python -m sheet_solution decisions    decide --out DIR --finding-id ID \\
                                          --action approve|decline|re-propose|apply --actor NAME
    python -m sheet_solution metrics      --out DIR
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
from sheet_solution.core.engine.hash_chain import sha256_bytes
from sheet_solution.sheets import template, runner, report, images
from sheet_solution.sheets.ledger import Ledger, verify_ledger

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


def _detect_key_column(header: list[str]) -> str:
    """Pick the most likely 'row identifier' column for traceable reports.

    Prefers columns whose name suggests an id/name/key; falls back to the
    first column; returns 'row' only when there is no header at all.
    """
    lowered = [h.strip().lower() for h in header]
    for needle in ("id", "key", "name", "ref", "code", "number"):
        for i, h in enumerate(lowered):
            if needle in h and h:
                return header[i]
    return header[0] if header and header[0].strip() else "row"


DEFAULT_MAX_ROWS = 500_000


def _cap_error(path: Path, max_rows: int) -> SignoffError:
    return SignoffError(
        f"{path.name}: more than {max_rows} data rows (row cap). "
        "Split the sheet or raise --max-rows (0 disables the cap).")


def _load_sheet(path: Path, key_col: str | None = None,
                max_rows: int = DEFAULT_MAX_ROWS) -> tuple[list[dict], str, bool]:
    """Return (rows, key_col, is_xlsx). Fails closed on unreadable input.

    `key_col` lets the caller name the row-identifier column explicitly;
    otherwise it is auto-detected from the header (see _detect_key_column).
    Rows are streamed and the load aborts once more than ``max_rows`` data rows
    have been read, so a huge or adversarial sheet cannot exhaust memory
    (``max_rows=0`` disables the cap).
    """
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
        it = ws.iter_rows(values_only=True)
        first = next(it, None)
        if first is None:
            raise SignoffError(f"{path.name}: xlsx has no rows")
        header = [str(c) if c is not None else "" for c in first]
        rows: list[dict] = []
        for r in it:
            rows.append({header[i]: (r[i] if i < len(r) else "")
                         for i in range(len(header))})
            if max_rows and len(rows) > max_rows:
                raise _cap_error(path, max_rows)
        chosen = key_col or _detect_key_column(header)
        return rows, chosen, True
    if ext == ".csv":
        import csv
        with path.open(encoding="utf-8-sig") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if header is None:
                raise SignoffError(f"{path.name}: empty CSV")
            rows = []
            for r in reader:
                if not any(c.strip() for c in r):
                    continue
                rows.append({header[i]: (r[i] if i < len(r) else "")
                             for i in range(len(header))})
                if max_rows and len(rows) > max_rows:
                    raise _cap_error(path, max_rows)
        chosen = key_col or _detect_key_column(header)
        return rows, chosen, False
    raise SignoffError(f"{path.name}: unsupported sheet type (expected .xlsx or .csv)")


def cmd_load_sheet(args) -> int:
    rows, key, is_xlsx = _load_sheet(
        Path(args.sheet), max_rows=getattr(args, "max_rows", DEFAULT_MAX_ROWS))
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


def cmd_parse_policy(args) -> int:
    """Load a policy file/sheet into one validated schema and echo it back."""
    from sheet_solution.core.policy import load_policy, validate_policy

    path = Path(args.policy)
    raw = load_policy(path, sheet=getattr(args, "sheet_name", "") or "")
    policy = validate_policy(raw)
    print(policy.echo())
    print(f"\nvalidated: {path.name}")
    return 0


def cmd_run(args) -> int:
    out_dir = Path(args.out)
    ledger = Ledger(out_dir / ".audit" / "ledger.jsonl")
    intent = ledger.append_intent("run", "cli", {
        "sheet": Path(args.sheet).name,
        "template": Path(args.template).name,
    })
    try:
        config = template.parse_template(Path(args.template), args.sheet)
        rows, key, is_xlsx = _load_sheet(
            Path(args.sheet), getattr(args, "key", None),
            max_rows=getattr(args, "max_rows", DEFAULT_MAX_ROWS))
        results = runner.run(config, rows, key=key)

        artifacts: dict[str, bytes] = {}
        artifacts["check-results.csv"] = report.render_results_csv(results).encode("utf-8")

        # Audit log: structured, machine-readable, with full traceability.
        log_lines = [json.dumps({
            "sheet": args.sheet, "persona": config.persona,
            "row_key": key, "rows_loaded": len(rows), "results": [
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
        ledger.append_result(intent, "run.completed", "cli", {
            "persona": config.persona,
            "checks": len(results),
            "artifacts": {
                name: sha256_bytes(data) for name, data in sorted(artifacts.items())
            },
            "images": [Path(ex.out_path).name for ex in extracted],
        })
    except Exception as exc:
        ledger.append_result(intent, "run.failed", "cli", {"error": str(exc)})
        raise
    print(report.summary(results))
    print(f"report pack -> {args.out}")
    return 0


def cmd_compare(args) -> int:
    """Compare two sheets row-by-row on a key; emit a diff report pack."""
    from sheet_solution.sheets import compare as cmp_mod

    out_dir = Path(args.out)
    ledger = Ledger(out_dir / ".audit" / "ledger.jsonl")
    intent = ledger.append_intent("compare", "cli", {
        "sheet_a": Path(args.sheet_a).name,
        "sheet_b": Path(args.sheet_b).name,
        "key": args.key,
        "fields": args.fields,
        "tolerance": args.tolerance or "",
    })
    try:
        max_rows = getattr(args, "max_rows", DEFAULT_MAX_ROWS)
        a_rows, _, _ = _load_sheet(Path(args.sheet_a), max_rows=max_rows)
        b_rows, _, _ = _load_sheet(Path(args.sheet_b), max_rows=max_rows)
        fields = [f.strip() for f in args.fields.split(",") if f.strip()]
        if not fields:
            raise SignoffError("compare: at least one field to compare is required "
                               "(comma-separated, e.g. 'name,amount')")

        result = cmp_mod.compare(a_rows, b_rows, args.key, fields,
                                 tolerance=args.tolerance or "")

        out_dir.mkdir(parents=True, exist_ok=True)
        report_text = result.csv()
        log = {
            "kind": "compare",
            "sheet_a": args.sheet_a, "sheet_b": args.sheet_b,
            "key": args.key, "fields": fields, "tolerance": args.tolerance or "",
            "totals": {"a": result.total_a, "b": result.total_b,
                       "matched": result.matched, "changed": result.changed,
                       "only_a": result.only_a, "only_b": result.only_b},
        }
        log_text = json.dumps(log, sort_keys=True) + "\n"
        (out_dir / "compare-report.csv").write_text(report_text, encoding="utf-8")
        (out_dir / "compare-log.jsonl").write_text(log_text, encoding="utf-8")
        ledger.append_result(intent, "compare.completed", "cli", {
            "totals": log["totals"],
            "artifacts": {
                "compare-report.csv": sha256_bytes(report_text.encode("utf-8")),
                "compare-log.jsonl": sha256_bytes(log_text.encode("utf-8")),
            },
        })
    except Exception as exc:
        ledger.append_result(intent, "compare.failed", "cli", {"error": str(exc)})
        raise

    print(result.summary())
    print(f"compare report -> {args.out}/compare-report.csv")
    return 0


def cmd_analyze(args) -> int:
    """Profile one sheet into a deterministic analysis pack (CSV + JSON log)."""
    from sheet_solution.sheets import analyze as an_mod

    out_dir = Path(args.out)
    ledger = Ledger(out_dir / ".audit" / "ledger.jsonl")
    intent = ledger.append_intent("analyze", "cli", {"sheet": Path(args.sheet).name})
    try:
        rows, key, _ = _load_sheet(
            Path(args.sheet), max_rows=getattr(args, "max_rows", DEFAULT_MAX_ROWS))
        result = an_mod.analyze(rows)
        analysis_csv = result.csv().encode("utf-8")
        log_text = (json.dumps({
            "kind": "analyze", "sheet": args.sheet, "row_key": key,
            "row_count": result.row_count, "column_count": result.column_count,
            "columns": [c.__dict__ for c in result.columns],
        }, sort_keys=True) + "\n").encode("utf-8")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "analysis.csv").write_bytes(analysis_csv)
        (out_dir / "analysis-log.jsonl").write_bytes(log_text)
        ledger.append_result(intent, "analyze.completed", "cli", {
            "row_count": result.row_count, "column_count": result.column_count,
            "artifacts": {
                "analysis.csv": sha256_bytes(analysis_csv),
                "analysis-log.jsonl": sha256_bytes(log_text),
            },
        })
    except Exception as exc:
        ledger.append_result(intent, "analyze.failed", "cli", {"error": str(exc)})
        raise
    print(result.summary())
    print(f"analysis pack -> {args.out}")
    return 0


def cmd_compatibility(args) -> int:
    """Compare two sheets' schema + value domains against a policy."""
    from sheet_solution.sheets import compatibility as compat_mod
    from sheet_solution.core.policy import load_policy, validate_policy

    out_dir = Path(args.out)
    ledger = Ledger(out_dir / ".audit" / "ledger.jsonl")
    policy_name = Path(args.policy).name if args.policy else ""
    intent = ledger.append_intent("compatibility", "cli", {
        "sheet_a": Path(args.sheet_a).name,
        "sheet_b": Path(args.sheet_b).name,
        "policy": policy_name,
    })
    try:
        max_rows = getattr(args, "max_rows", DEFAULT_MAX_ROWS)
        a_rows, _, _ = _load_sheet(Path(args.sheet_a), max_rows=max_rows)
        b_rows, _, _ = _load_sheet(Path(args.sheet_b), max_rows=max_rows)
        required: tuple[str, ...] = ()
        allowed: dict = {}
        if args.policy:
            policy = validate_policy(
                load_policy(Path(args.policy), sheet=args.sheet_name or ""))
            required = policy.compatibility.required_columns
            allowed = dict(policy.compatibility.allowed_values)
        result = compat_mod.compatibility(a_rows, b_rows, required, allowed)
        report_text = result.csv().encode("utf-8")
        log_text = (json.dumps({
            "kind": "compatibility",
            "sheet_a": args.sheet_a, "sheet_b": args.sheet_b, "policy": policy_name,
            "verdict": result.verdict,
            "findings": [f.__dict__ for f in result.findings],
        }, sort_keys=True) + "\n").encode("utf-8")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "compatibility-report.csv").write_bytes(report_text)
        (out_dir / "compatibility-log.jsonl").write_bytes(log_text)
        ledger.append_result(intent, "compatibility.completed", "cli", {
            "verdict": result.verdict,
            "findings": len(result.findings),
            "artifacts": {
                "compatibility-report.csv": sha256_bytes(report_text),
                "compatibility-log.jsonl": sha256_bytes(log_text),
            },
        })
    except Exception as exc:
        ledger.append_result(intent, "compatibility.failed", "cli", {"error": str(exc)})
        raise
    print(result.summary())
    print(f"compatibility report -> {args.out}")
    return 0 if result.verdict == "COMPATIBLE" else 1


def _decisions_path(out_dir: Path) -> Path:
    return out_dir / "decisions.json"


def _load_decisions(out_dir: Path) -> list:
    from sheet_solution.sheets import decisions as dec

    path = _decisions_path(out_dir)
    if not path.exists():
        raise SignoffError(f"no decisions.json in {out_dir}; run 'decisions plan' first")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [dec.decision_from_dict(d) for d in data]


def _save_decisions(out_dir: Path, decs: list) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _decisions_path(out_dir).write_text(
        json.dumps([d.to_dict() for d in decs], indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def cmd_decisions(args) -> int:
    """Fail-closed decision loop: plan findings, then record human decisions."""
    import csv

    from sheet_solution.sheets import actions as act, decisions as dec

    out_dir = Path(args.out)
    op = args.decision_action

    if op == "plan":
        from sheet_solution.core.policy import load_policy, validate_policy

        results_path = (Path(args.check_results) if args.check_results
                        else out_dir / "check-results.csv")
        if not results_path.exists():
            raise SignoffError(f"missing check results: {results_path}")
        with results_path.open(encoding="utf-8-sig", newline="") as fh:
            results = list(csv.DictReader(fh))
        checks = {}
        if args.policy:
            policy = validate_policy(
                load_policy(Path(args.policy), sheet=args.sheet_name or ""))
            checks = {c.id: c for c in policy.checks}
        found = dec.build_findings(results, checks)
        _save_decisions(out_dir, found)
        ledger = Ledger(out_dir / ".audit" / "ledger.jsonl")
        intent = ledger.append_intent("decisions.plan", "system", {
            "check_results": results_path.name, "policy": Path(args.policy).name if args.policy else "",
        })
        for d in found:
            ledger.append_proposal(d)
        ledger.append_result(intent, "decisions.plan.completed", "system",
                             {"proposals": len(found)})
        print(f"planned {len(found)} finding(s) -> {_decisions_path(out_dir)}")
        for d in found:
            print(f"  {d.decision_id} [{d.state}] proposed={d.proposed_action} "
                  f"options={list(d.options)}")
        return 0

    decs = _load_decisions(out_dir)
    ledger = Ledger(out_dir / ".audit" / "ledger.jsonl")

    if op == "list":
        if not decs:
            print("no decisions (run 'decisions plan' first)")
            return 0
        for d in decs:
            line = (f"{d.decision_id} [{d.state}] proposed={d.proposed_action} "
                    f"options={list(d.options)}")
            if d.applied_action:
                line += f" applied={d.applied_action}"
            print(line)
        return 0

    # op == "decide" — every transition requires a named human actor.
    if not args.actor.strip():
        raise SignoffError("a named --actor is required to record a decision")
    idx = next((i for i, d in enumerate(decs) if d.decision_id == args.finding_id), None)
    if idx is None:
        raise SignoffError(f"unknown finding id {args.finding_id!r}")
    current = decs[idx]
    actor = args.actor.strip()
    transition, updated = "", current
    applied_result = None

    if args.action == "approve":
        updated = dec.approve(current, actor)
        transition = "approve"
    elif args.action == "decline":
        updated = dec.decline(current, actor, args.reason or "")
        transition = "decline"
    elif args.action == "re-propose":
        if not args.action_id:
            raise SignoffError("re-propose requires --action-id")
        updated = dec.re_propose(current, actor, args.action_id)
        transition = "re_propose"
    elif args.action == "apply":
        if not dec.apply_ok(current):
            raise SignoffError(
                f"{current.decision_id} is {current.state}, not APPROVED; refusing to apply")
        row = {"row_id": current.finding.row_id,
               current.finding.column: current.finding.value}
        result = act.apply_action(current.proposed_action, row)
        updated = dec.mark_applied(current, actor)
        transition = "apply"
        applied_result = result
        with (out_dir / "corrected-copy.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "decision_id": updated.decision_id, "action": result.action,
                "row": result.row, "drop": result.drop, "note": result.note,
            }, sort_keys=True) + "\n")
    else:
        raise SignoffError("decide requires --action "
                           "[approve|decline|re-propose|apply]")

    decs[idx] = updated
    _save_decisions(out_dir, decs)
    ledger.append_decision(updated, actor, transition)
    if transition == "apply":
        ledger.append_application(updated, actor, applied_result)
        print(f"{updated.decision_id}: APPLIED {applied_result.action} by {actor} "
              f"-> {applied_result.note}")
    elif transition == "decline":
        print(f"{updated.decision_id}: DECLINED by {actor}; "
              f"alternatives={list(updated.alternatives())}")
    else:
        print(f"{updated.decision_id}: {updated.state} by {actor} "
              f"(proposed={updated.proposed_action})")
    return 0


def cmd_metrics(args) -> int:
    """Deterministic ops metrics from a run pack's results + decisions."""
    import csv

    from sheet_solution.sheets import metrics as met

    out_dir = Path(args.out)
    results_path = out_dir / "check-results.csv"
    if not results_path.exists():
        raise SignoffError(f"missing {results_path}; run 'run' first")
    with results_path.open(encoding="utf-8-sig", newline="") as fh:
        results = list(csv.DictReader(fh))
    decisions_path = out_dir / "decisions.json"
    decisions = (json.loads(decisions_path.read_text(encoding="utf-8"))
                 if decisions_path.exists() else [])

    ledger = Ledger(out_dir / ".audit" / "ledger.jsonl")
    intent = ledger.append_intent("metrics", "cli", {"pack": out_dir.name})
    metrics = met.build_metrics(results, decisions)
    data = (json.dumps(metrics.to_dict(), indent=2, sort_keys=True) + "\n").encode("utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_bytes(data)
    ledger.append_result(intent, "metrics.completed", "cli", {
        "artifacts": {"metrics.json": sha256_bytes(data)},
    })
    print(metrics.summary())
    print(f"metrics -> {out_dir / 'metrics.json'}")
    return 0


def cmd_verify(args) -> int:
    out_dir = Path(args.out)
    results_csv = out_dir / "check-results.csv"
    log = out_dir / "audit-log.jsonl"
    if not results_csv.exists() or not log.exists():
        print("NOT-FOUND: missing check-results.csv or audit-log.jsonl", file=sys.stderr)
        return 1
    ledger_path = out_dir / ".audit" / "ledger.jsonl"
    if ledger_path.exists():
        chain = verify_ledger(ledger_path)
        if not chain["ok"]:
            print(f"LEDGER-BROKEN: {chain.get('reason')} at seq {chain.get('seq', '?')}",
                  file=sys.stderr)
            return 1
        print(f"LEDGER-VERIFIED: {chain.get('count', 0)} event(s)")
    data = json.loads(log.read_text(encoding="utf-8"))
    print(f"VERIFIED-STRUCTURE: {len(data['results'])} result record(s), "
          f"persona={data['persona']}, rows={data['rows_loaded']}")
    return 0


def cmd_ledger(args) -> int:
    """Inspect or verify the durable intent/result ledger for a run."""
    path = Path(args.out) / ".audit" / "ledger.jsonl"
    if args.action == "verify":
        chain = verify_ledger(path)
        if chain["ok"]:
            print(f"LEDGER-VERIFIED: {chain.get('count', 0)} event(s), "
                  f"head {str(chain.get('head', 'GENESIS'))[:12]}")
            return 0
        print(f"LEDGER-BROKEN: {chain.get('reason')} at seq {chain.get('seq', '?')}",
              file=sys.stderr)
        return 1
    ledger = Ledger(path)
    if args.action == "pending":
        pending = ledger.pending_intents()
        if not pending:
            print("no pending intents")
        for event in pending:
            print(json.dumps(event, sort_keys=True))
        return 0
    if args.action == "tail":
        for event in ledger.tail(args.n):
            print(json.dumps(event, sort_keys=True))
        return 0
    if args.action == "anchor":
        print(json.dumps(ledger.anchor(), sort_keys=True))
        return 0
    if args.action == "check-anchor":
        result = ledger.check_anchor()
        print(json.dumps(result, sort_keys=True))
        return 0 if result["ok"] else 1
    return 1


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
    p.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS,
                   help="fail closed past this many data rows (0 = no cap)")
    p.set_defaults(func=cmd_load_sheet)

    p = sub.add_parser("parse-template", help="validate + echo the check template")
    p.add_argument("--template", required=True)
    p.add_argument("--sheet", default="", help="sheet path recorded in the config")
    p.set_defaults(func=cmd_parse_template)

    p = sub.add_parser("parse-policy", help="validate + echo a policy (file first, sheet second)")
    p.add_argument("--policy", required=True,
                   help="policy .json/.yaml/.yml file or .csv/.xlsx policy sheet")
    p.add_argument("--sheet-name", default="", help="worksheet name for an .xlsx policy sheet")
    p.set_defaults(func=cmd_parse_policy)

    p = sub.add_parser("run", help="run the checks and emit the report pack + audit log")
    p.add_argument("--sheet", required=True)
    p.add_argument("--template", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--key", default=None,
                   help="column that identifies each row (auto-detected if omitted)")
    p.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS,
                   help="fail closed past this many data rows (0 = no cap)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("compare", help="compare two sheets row-by-row on a key")
    p.add_argument("--sheet-a", required=True, help="baseline sheet")
    p.add_argument("--sheet-b", required=True, help="new / other sheet")
    p.add_argument("--key", required=True, help="row-key column (identifies the same thing)")
    p.add_argument("--fields", required=True,
                   help="comma-separated columns to compare, e.g. 'name,amount'")
    p.add_argument("--tolerance", default="",
                   help="numeric tolerance for compared fields (blank = exact)")
    p.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS,
                   help="fail closed past this many data rows (0 = no cap)")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("analyze", help="profile one sheet (types, blanks, ranges)")
    p.add_argument("--sheet", required=True)
    p.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS,
                   help="fail closed past this many data rows (0 = no cap)")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("compatibility", help="check two sheets' schema + value domains")
    p.add_argument("--sheet-a", required=True)
    p.add_argument("--sheet-b", required=True)
    p.add_argument("--policy", default="",
                   help="optional policy file/sheet declaring required columns + domains")
    p.add_argument("--sheet-name", default="", help="worksheet name for an .xlsx policy sheet")
    p.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS,
                   help="fail closed past this many data rows (0 = no cap)")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_compatibility)

    p = sub.add_parser("decisions", help="fail-closed decision loop over proposed findings")
    p.add_argument("decision_action", choices=["plan", "list", "decide"],
                   help="plan: build findings; list: show states; decide: record a human decision")
    p.add_argument("--out", required=True,
                   help="run pack directory (holds check-results.csv / decisions.json)")
    p.add_argument("--policy", default="",
                   help="policy file/sheet for plan (declares on_fail actions)")
    p.add_argument("--sheet-name", default="", help="worksheet name for an .xlsx policy sheet")
    p.add_argument("--check-results", default="",
                   help="override path to check-results.csv for plan")
    p.add_argument("--finding-id", default="", help="decision to act on (for decide)")
    p.add_argument("--action", default="", choices=["approve", "decline", "re-propose", "apply"],
                   help="human decision to record (for decide)")
    p.add_argument("--action-id", default="", help="alternative action id for re-propose")
    p.add_argument("--actor", default="", help="named human actor (required for decide)")
    p.add_argument("--reason", default="", help="optional reason for a decline")
    p.set_defaults(func=cmd_decisions)

    p = sub.add_parser("metrics", help="ops metrics: machine-decided vs human-needed")
    p.add_argument("--out", required=True, help="run pack directory")
    p.set_defaults(func=cmd_metrics)

    p = sub.add_parser("verify", help="re-check a produced report pack structure")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("ledger", help="inspect the durable run/compare ledger")
    p.add_argument("--out", required=True)
    p.add_argument("action",
                   choices=["verify", "pending", "tail", "anchor", "check-anchor"])
    p.add_argument("--n", type=int, default=20, help="events to show for 'tail'")
    p.set_defaults(func=cmd_ledger)

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
