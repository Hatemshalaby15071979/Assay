# Sheet Solution — GUI

A tiny **offline** web UI that wraps the deterministic CLI so non-technical
users can run a check without touching the terminal.

- Binds `127.0.0.1` only. **No outbound network calls** — the checks run
  through the same code path as `run.sh` / the CLI; the GUI adds no logic.
- Requires the optional `gui` extra: `pip install "sheet-solution[gui]"`
  (installs Flask 3.0.3). Everything else (the audit engine) is stdlib +
  the pinned PDF library.

## Run it

```bash
pip install "sheet-solution[gui]"
python gui/main.py            # -> http://127.0.0.1:8477
```

Then open the URL, paste a sheet path and a filled check-template path, and
click **Run checks**. The report pack (CSV + audit log + extracted images)
is written to `out/web-report/` on the same machine.

## For a non-technical recipient

You do not need to install anything. The standalone release ships this GUI
inside the bundle; they double-click the launcher and it opens in the
browser on their own machine. Their data never leaves it.
