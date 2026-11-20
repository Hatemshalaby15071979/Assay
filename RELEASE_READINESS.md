# Sheet Solution — release readiness

**Status date:** 2026-11-20
**Scope:** local, offline, single-user sheet-ops — audit, two-sheet compare,
profile (analyze), compatibility, and a policy-driven, fail-closed decision loop
**Decision:** staged preview candidate; not a compliance determination and not
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
| GUI | real-browser DOM drag-and-drop + decision-loop E2E (deny → apply) |
| Scale | bounded `scripts/scale-stress.py` smoke + fail-closed row cap |
| Run integrity | durable intent/result ledger (`sheets/ledger.py`) |
| Decision safety | fail-closed state machine; nothing applied without a named human's approve then apply |
| Ops metrics | deterministic `metrics` command (`sheets/metrics.py`) |

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
| F-08 | Closed | A proposed action could be applied without explicit human approval. | Fail-closed state machine (`sheets/decisions.py`): `apply_ok` is true only in `APPROVED`; `mark_applied` refuses other states. Denial applies nothing and keeps alternatives. Unit + GUI/CLI parity tests. |
| F-09 | Mitigated | Very large sheets could exhaust memory. | `_load_sheet` streams and fails closed past a row cap (default 500,000; `--max-rows`, `0` disables). Bounded `scale-stress.py` smoke; not a capacity guarantee. |
| F-10 | Open | Decision-loop semantics are self-assessed, not independently audited. | Behaviour is covered by deterministic tests and a browser E2E; third-party review remains an owner decision before any external safety claim. |

## Verification record (2026-11-20)

Commands run from the repository root:

```bash
python scripts/check-scaffold.py
python scripts/check-offline.py
python scripts/check-doc-consistency.py
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python scripts/check-determinism.py --out out/determinism
PYTHONPATH=src python scripts/scale-stress.py --rows 2000
PYTHONPATH=src python -m sheet_solution metrics --out out/report
bash tests/gui-browser-test.sh
bash tests/gui-decisions-test.sh
bandit -r src -q
pip-audit -r requirements.lock
python tooling/security/scan_history_secrets.py
```

The authoritative, per-run results are the CI logs and the uploaded
history-scan artifact. This table records what was run, not a claim that every
environment is identical.

## Staged preview rollout

0.4.0 is a **staged preview**: local, single-user, opt-in. The rollout is
deliberately narrow so a decision-loop bug cannot silently change a user's
data at scale.

1. **Preview (now).** Ship 0.4.0 to the owner and a small set of local users.
   The default is fail-closed: every failed check waits for a named human, and
   nothing is applied without an explicit approve then apply.
2. **Watch.** Review the `metrics` output on real packs (share of checks the
   machine decided vs items needing a person, findings resolved vs
   outstanding) and any `declined` decisions that reveal unclear policy.
3. **Promote.** Only after the open findings above are closed by an owner
   sign-off, tag a stable release. Until then, do not present 0.4.0 as a
   compliance tool, a digital signer, or an independently audited system.

## Release decision

**Staged preview candidate.** The offline, deterministic and packaging
guarantees are CI-backed. The tool is not a compliance certification, not a
digital signer, and not independently audited. Any statement beyond that
requires the owner sign-off below and closure of the open findings.

## Owner sign-off

- Owner: ____________________
- Date: ____________________
- Scope of approval: ____________________
