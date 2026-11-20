"""Sheet Solution — offline GUI: drag-and-drop + visual result cards.

A single-page local app. The user drags in:
  - one sheet + one check-template  ->  "Run checks"  (the audit persona), or
  - two sheets + a key + fields     ->  "Compare"     (the two-sheet case), or
  - a run pack + a policy           ->  "Decide"      (the fail-closed loop).

Results render as **visual cards**: one card per check (or per diff row),
color-coded — green PASS / red FAIL / amber PENDING-HUMAN, and for compare,
green MATCHED / red CHANGED / blue only-in-A / orange only-in-B. Each card
shows the exact details + the failing row ids, and the pack (CSV + JSON log +
extracted images) is downloadable. Everything is on 127.0.0.1; no outbound
calls; the engine is the same deterministic code the CLI runs.

Launch:  python gui/main.py            # -> http://127.0.0.1:8477
Requires the optional `gui` extra:  pip install "sheet-solution[gui]"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

# Repo root: src/sheet_solution/gui/main.py -> parents[3] = repo root.
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

# Files the GUI is allowed to read/upload (kept in a local spool, never the
# whole filesystem).
SPOOL = Path(tempfile.gettempdir()) / "sheet_solution_gui"


def _new_spool_for(content: bytes) -> Path:
    """Deterministic spool dir: named by the SHA-256 of the uploaded bytes.

    No random ids (the platform bans uuid4/random — determinism invariant).
    Identical uploads land in the same spool dir; the id is content-derived,
    matching the spine's content-derived-ids philosophy.
    """
    digest = hashlib.sha256(content).hexdigest()
    d = SPOOL / digest
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_rows(path: Path) -> list[dict]:
    from sheet_solution.cli import _load_sheet
    rows, _, _ = _load_sheet(path)
    return rows


# ---------------------------------------------------------------------------
# API handlers
# ---------------------------------------------------------------------------
def build_app():  # pragma: no cover - thin web shell; logic is in the engine
    from flask import Flask, request, jsonify, send_file, Response

    from sheet_solution.cli import cmd_run, cmd_compare, _load_sheet
    from sheet_solution.sheets import compare as cmp_mod, template
    from sheet_solution.core.errors import SignoffError
    from sheet_solution import __version__

    app = Flask(__name__)

    @app.get("/")
    def index():
        return (Path(__file__).parent / "index.html").read_text(encoding="utf-8")

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "version": __version__,
                        "offline": True, "spool": str(SPOOL)})

    @app.post("/api/upload")
    def upload():
        """Stash a dropped file (sheet / template) into a content-named spool."""
        f = request.files.get("file")
        if f is None or not f.filename:
            return jsonify({"ok": False, "error": "no file"}), 400
        data = f.read()
        spool = _new_spool_for(data)
        dest = spool / Path(f.filename).name
        dest.write_bytes(data)
        # Column preview so a non-technical user can verify the upload and
        # see the exact column names (no more guessing 'passport_photo').
        columns: list[str] = []
        preview: list[list[str]] = []
        rows: list[dict] = []
        try:
            rows, _, _ = _load_sheet(dest)
            if rows:
                columns = list(rows[0].keys())
                preview = [[str(r.get(c, "")) for c in columns]
                           for r in rows[:3]]
        except Exception:  # noqa: BLE001 - preview is best-effort, never blocks upload
            columns, preview = [], []
        return jsonify({"ok": True, "id": spool.name, "name": dest.name,
                        "path": str(dest), "columns": columns,
                        "preview": preview, "row_count": len(rows) if rows else 0})

    @app.post("/api/validate-template")
    def validate_template():
        body = request.get_json(force=True)
        tmpl_id = body.get("template") or ""
        try:
            p = _spool_file(tmpl_id)
            config = template.parse_template(p, "")
        except Exception as exc:  # noqa: BLE001
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "persona": config.persona,
                        "checks": [{"id": c.check_id, "label": c.what_is_this_check_for,
                                    "machine": c.machine_can_check,
                                    "needs_human": c.needs_human}
                                   for c in config.checks]})

    @app.post("/api/checks")
    def run_checks():
        """Run the audit checks: one template + one sheet -> result cards."""
        body = request.get_json(force=True)
        sheet_id = body.get("sheet") or ""
        tmpl_id = body.get("template") or ""
        out = SPOOL / sheet_id / "out"
        args = type("A", (), {})()
        args.sheet = str(_spool_file(sheet_id))
        args.template = str(_spool_file(tmpl_id))
        args.out = str(out)
        try:
            rc = cmd_run(args)
        except SignoffError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        if rc != 0:
            return jsonify({"ok": False, "error": f"run exited {rc}"}), 400
        results = _read_results_csv(out / "check-results.csv")
        log = _read_jsonl(out / "audit-log.jsonl")
        media = sorted(p.name for p in (out / "media").glob("*")) \
            if (out / "media").exists() else []
        return jsonify({"ok": True, "persona": log[0].get("persona") if log else "auditor",
                        "results": results, "log": log, "media": media,
                        "out": str(out)})

    @app.post("/api/compare")
    def do_compare():
        """Two-sheet compare: two uploads + key + fields -> diff cards."""
        body = request.get_json(force=True)
        a_id, b_id = body.get("sheetA") or "", body.get("sheetB") or ""
        key = body.get("key") or ""
        fields = [f.strip() for f in (body.get("fields") or "").split(",") if f.strip()]
        tolerance = body.get("tolerance") or ""
        if not key or not fields:
            return jsonify({"ok": False, "error": "key and fields are required"}), 400
        a_path = _spool_file(a_id)
        b_path = _spool_file(b_id)
        # Distinct output dir per compare, named by the inputs + parameters so
        # two different compares never collide (still deterministic, no random).
        seed = (a_path.name + b_path.name + key + ",".join(fields)
                + tolerance).encode("utf-8")
        spool = _new_spool_for(seed)
        out = spool / "out"; out.mkdir(parents=True, exist_ok=True)
        from sheet_solution.sheets.ledger import Ledger
        from sheet_solution.core.engine.hash_chain import sha256_bytes
        ledger = Ledger(out / ".audit" / "ledger.jsonl")
        intent = ledger.append_intent("compare", "gui", {
            "sheet_a": a_path.name, "sheet_b": b_path.name,
            "key": key, "fields": fields, "tolerance": tolerance,
        })
        try:
            a_rows = _load_rows(a_path)
            b_rows = _load_rows(b_path)
            result = cmp_mod.compare(a_rows, b_rows, key, fields, tolerance)
            report_text = result.csv()
            logrec = {"kind": "compare", "key": key, "fields": fields,
                      "tolerance": tolerance,
                      "totals": {"a": result.total_a, "b": result.total_b,
                                 "matched": result.matched, "changed": result.changed,
                                 "only_a": result.only_a, "only_b": result.only_b}}
            log_text = json.dumps(logrec, sort_keys=True) + "\n"
            (out / "compare-report.csv").write_text(report_text, encoding="utf-8")
            (out / "compare-log.jsonl").write_text(log_text, encoding="utf-8")
            ledger.append_result(intent, "compare.completed", "gui", {
                "totals": logrec["totals"],
                "artifacts": {
                    "compare-report.csv": sha256_bytes(report_text.encode("utf-8")),
                    "compare-log.jsonl": sha256_bytes(log_text.encode("utf-8")),
                },
            })
        except Exception as exc:
            ledger.append_result(intent, "compare.failed", "gui", {"error": str(exc)})
            raise
        return jsonify({"ok": True, "summary": result.summary(),
                        "totals": logrec["totals"], "rows": [
                            {"key": r.key, "status": r.status,
                             "changed_fields": r.changed_fields,
                             "a_value": r.a_value, "b_value": r.b_value}
                            for r in result.rows], "out": str(out)})

    # --- decision loop (fail closed; reuses the CLI engine) --------------
    @app.post("/api/decisions/plan")
    def decisions_plan():
        """Turn a run pack's failures into proposals, using an uploaded policy."""
        from sheet_solution.cli import cmd_decisions

        body = request.get_json(force=True)
        try:
            out = _spool_pack(body.get("out", ""))
            policy_path = _spool_file(body.get("policy") or "")
        except (ValueError, FileNotFoundError, OSError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        args = type("A", (), {})()
        args.decision_action = "plan"
        args.out = str(out)
        args.policy = str(policy_path)
        args.sheet_name = ""; args.check_results = ""; args.finding_id = ""
        args.action = ""; args.action_id = ""; args.actor = ""; args.reason = ""
        try:
            cmd_decisions(args)
        except Exception as exc:  # noqa: BLE001 - surface any fail-closed abort
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "out": str(out),
                        "decisions": _read_decisions(out)})

    @app.get("/api/decisions")
    def decisions_list():
        """Current decision states + their ledger evidence for a pack."""
        from sheet_solution.sheets.ledger import Ledger

        try:
            out = _spool_pack(request.args.get("out", ""))
        except (ValueError, OSError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        ledger = Ledger(out / ".audit" / "ledger.jsonl")
        return jsonify({"ok": True, "out": str(out),
                        "decisions": _read_decisions(out),
                        "events": ledger.decision_events()})

    @app.post("/api/decisions/decide")
    def decisions_decide():
        """Record approve/decline/re-propose/apply with a named human actor."""
        from sheet_solution.cli import cmd_decisions
        from sheet_solution.sheets.ledger import Ledger

        body = request.get_json(force=True)
        try:
            out = _spool_pack(body.get("out", ""))
        except (ValueError, OSError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        args = type("A", (), {})()
        args.decision_action = "decide"
        args.out = str(out)
        args.policy = ""; args.sheet_name = ""; args.check_results = ""
        args.finding_id = body.get("findingId") or ""
        args.action = body.get("action") or ""
        args.action_id = body.get("actionId") or ""
        args.actor = body.get("actor") or ""
        args.reason = body.get("reason") or ""
        try:
            cmd_decisions(args)
        except Exception as exc:  # noqa: BLE001 - fail-closed abort -> 400
            return jsonify({"ok": False, "error": str(exc)}), 400
        ledger = Ledger(out / ".audit" / "ledger.jsonl")
        return jsonify({"ok": True, "out": str(out),
                        "decisions": _read_decisions(out),
                        "events": ledger.decision_events()})

    @app.get("/api/pack")
    def download_pack():
        out = Path(request.args.get("out", "")).resolve()
        files = {"csv": out / "check-results.csv",
                 "ccsv": out / "compare-report.csv",
                 "log": out / "audit-log.jsonl",
                 "clog": out / "compare-log.jsonl",
                 "dec": out / "decisions.json",
                 "corr": out / "corrected-copy.jsonl"}
        name = request.args.get("name", "")
        target = next((p for k, p in files.items() if p.name == name), None)
        if target is None:
            target = next((p for p in files.values() if p.exists()), None)
        if target and target.exists():
            return send_file(str(target), as_attachment=True,
                            download_name=target.name)
        return jsonify({"ok": False, "error": "no pack"}), 404

    @app.get("/api/zip")
    def download_zip():
        import zipfile, io
        out = Path(request.args.get("out", "")).resolve()
        if not out.exists() or not out.is_dir():
            return jsonify({"ok": False, "error": "no pack"}), 404
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(out.rglob("*")):
                if p.is_file():
                    zf.write(p, p.relative_to(out))
        buf.seek(0)
        return send_file(buf, as_attachment=True,
                        download_name=f"{out.name}.zip",
                        mimetype="application/zip")

    return app


def _spool_file(upload_id: str) -> Path:
    """Each upload spool dir holds exactly one file; return its full path.

    The id must be a single spool directory name (uploads are named by their
    SHA-256 hex digest). Anything with a separator, a traversal component or a
    symlink escaping the spool is refused, so a crafted id cannot read files
    outside the local spool.
    """
    if not isinstance(upload_id, str) or not upload_id:
        raise ValueError("invalid upload id")
    if upload_id in (".", "..") or Path(upload_id).name != upload_id:
        raise ValueError("invalid upload id")
    d = SPOOL / upload_id
    if not d.is_dir():
        raise FileNotFoundError(f"spool {upload_id} has no file")
    if d.resolve().parent != SPOOL.resolve():
        raise ValueError("invalid upload id")
    for p in sorted(d.iterdir()):
        if p.is_file():
            return p
    raise FileNotFoundError(f"spool {upload_id} has no file")


def _spool_pack(out: str) -> Path:
    """Resolve a run pack path, refusing anything outside the local spool."""
    p = Path(out).resolve()
    spool = SPOOL.resolve()
    if spool not in p.parents and p != spool:
        raise ValueError("pack must be a local GUI spool path")
    return p


def _read_decisions(out: Path) -> list[dict]:
    path = out / "decisions.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _read_results_csv(path: Path) -> list[dict]:
    import csv
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def main() -> int:  # pragma: no cover
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8477)
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind host (default localhost only; do not expose)")
    args = parser.parse_args()
    SPOOL.mkdir(parents=True, exist_ok=True)
    app = build_app()
    print(f"Sheet Solution offline GUI on http://{args.host}:{args.port} "
          f"(local only — no cloud)")
    app.run(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
