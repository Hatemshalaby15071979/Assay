# Sheet Solution — release readiness

**Status date:** 2026-11-20
**Scope:** local, offline, single-user sheet audit and two-sheet compare
**Decision:** pre-release candidate; not a compliance determination and not
independently audited.

## Governing rule

A green CI run is a **verification gate**, not a release decision. A release
is approved only when the finding register below has no open release-blocking
item and the owner records a dated sign-off. Do not close a finding because a
local test passed; close it against the evidence named in its row.

The authoritative current status is the "Status" section of `README.md`.
This file is the dated release record behind that status.

## What is verified automatically

| Area | Evidence |
|---|---|
| Offline guarantee | `scripts/check-offline.py` AST scan + Docker `--network none` run |
| Determinism | `scripts/check-determinism.py` byte-identical demo builds |
| Doc/version claims | `scripts/check-doc-consistency.py` |
| Tests | CI matrix on Python 3.11/3.12/3.13 |
| Packaging | clean-venv wheel install + CLI smoke + SBOM in CI |
| Security | Bandit, `pip-audit`, pattern scan, full-history secret scan |
| GUI | real-browser DOM drag-and-drop regression |
| Scale | bounded `scripts/scale-stress.py` smoke |
| Run integrity | durable intent/result ledger (`sheets/ledger.py`) |

## Finding register

| ID | Severity | Finding | Evidence / status |
|---|---|---|---|
| F-01 | Informational | Evidence is hash-consistent, not a digital signature. | Disclosed in `SECURITY.md`; no key lifecycle exists. Accepted for an offline local tool. |
| F-02 | Open | No independent third-party audit. | CI and local checks are self-assessed. Owner decision required before any external claim. |
| F-03 | Open | No monitored security reporting channel. | `SECURITY.md` states this honestly; a private advisory channel is an owner action. |
| F-04 | Closed | Live docs hardcoded a drifting test count and the CHANGELOG title sat below a release block. | Fixed in 0.3.0; `check-doc-consistency.py` prevents recurrence. |
| F-05 | Closed | No SAST, dependency audit or history secret scan in CI. | Security job added in 0.3.0. |
| F-06 | Mitigated | Practical scale ceiling was unmeasured. | Bounded `scale-stress.py` smoke; not a capacity guarantee. |
| F-07 | Open | DOCX/XLSX parsing is hardened but not fuzzed. | `defusedxml` + size caps; a fuzz corpus remains an owner decision. |

## Verification record (2026-11-20)

Commands run from the repository root:

```bash
python scripts/check-scaffold.py
python scripts/check-offline.py
python scripts/check-doc-consistency.py
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python scripts/check-determinism.py --out out/determinism
PYTHONPATH=src python scripts/scale-stress.py --rows 2000
bandit -r src -q
pip-audit -r requirements.lock
python tooling/security/scan_history_secrets.py
```

The authoritative, per-run results are the CI logs and the uploaded
history-scan artifact. This table records what was run, not a claim that every
environment is identical.

## Release decision

**Pre-release candidate.** The offline, deterministic and packaging
guarantees are CI-backed. The tool is not a compliance certification, not a
digital signer, and not independently audited. Any statement beyond that
requires the owner sign-off below and closure of the open findings.

## Owner sign-off

- Owner: ____________________
- Date: ____________________
- Scope of approval: ____________________
