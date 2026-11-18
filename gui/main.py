"""Sheet Solution — offline GUI (no network).

A minimal local web UI that wraps the deterministic CLI. It is designed to be
bundled into the standalone release so non-technical users can:
  1. drop in a sheet + a filled check-template,
  2. click "Run checks",
  3. download the report pack (CSV + audit log + extracted images).

It binds 127.0.0.1 only and makes no outbound calls. The checks themselves
run through the same CLI the operator would run — the GUI adds zero logic.

Launch:  python gui/main.py   (or `make gui`)
Then open http://127.0.0.1:8477
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def build_app():  # pragma: no cover - thin web shell; the logic is in the CLI
    from flask import Flask, request, jsonify, send_file
    from sheet_solution.cli import cmd_run
    from sheet_solution.core.errors import SignoffError

    app = Flask(__name__)

    @app.post("/api/run")
    def run():
        out = Path(request.form.get("out", "out/web-report")).resolve()
        args = argparse.Namespace(
            sheet=request.form["sheet"],
            template=request.form["template"],
            out=str(out))
        try:
            rc = cmd_run(args)
        except SignoffError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        if rc != 0:
            return jsonify({"ok": False, "error": f"run exited {rc}"}), 400
        return jsonify({
            "ok": True,
            "results": (out / "check-results.csv").read_text(encoding="utf-8"),
            "log": (out / "audit-log.jsonl").read_text(encoding="utf-8"),
            "media": sorted(p.name for p in (out / "media").glob("*"))
            if (out / "media").exists() else []})

    @app.get("/")
    def index():  # noqa: ANN201
        return """
<!doctype html><meta charset=utf-8>
<title>Sheet Solution — offline checks</title>
<style>body{font:16px/1.5 system-ui;margin:2rem;max-width:44rem}
input,button{font:inherit;padding:.4rem}.out{white-space:pre-wrap;
font-family:ui-monospace,monospace;background:#f4f4f4;padding:1rem}</style>
<h1>Sheet Solution</h1>
<p>Paste your sheet path and template path, then run. Everything stays on
this machine — no upload, no cloud.</p>
<form method=post action=/api/run target=_blank>
  <label>Sheet <input name=sheet required placeholder=sheet.xlsx></label><br>
  <label>Template <input name=template required placeholder=checks.txt></label><br>
  <button type=submit>Run checks</button>
</form>
<p>(Open the report pack via the CLI or <code>run.sh</code> for the files.)</p>
"""

    return app


def main() -> int:  # pragma: no cover - entry point
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8477)
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind host (default localhost only; do not expose)")
    args = parser.parse_args()
    app = build_app()
    print(f"Sheet Solution offline GUI on http://{args.host}:{args.port} "
          f"(local only)")
    app.run(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
