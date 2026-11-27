# AGENTS.md — Agent Charter & Ledger for Assay

> **Read order (mandatory, every landing):** `AGENTS.md` → `CONSTITUTION.md` →
> `GOVERNANCE.md` → `README.md`. Then **sign in** to the ledger below, do the work,
> **sign out**. No entry, no trust: an unlogged session's work is treated as unverified
> until someone checks it.

## 1. Who agents are here

An "agent" is any entity that reads or writes this repository — an AI model, an
automation script, or a human acting as operator. There is exactly **one supreme
authority**: the repository owner (**Hatem Shalaby**). An agent acts only on the
owner's instruction and records every landing.

## 2. The mandatory sign-in / sign-out rule

Every agent, on **every landing** (a landing = one session that ends with the agent
stopping, whether the task is finished or not), must:

1. **SIGN IN** before any write action — who, why, what will be touched, sensitive or
   network actions planned, and the **date and time from the system clock**.
2. **SIGN OUT** when the landing's work is complete or stopped — what changed, why,
   the files touched, evidence of verification, and **the current status when leaving**,
   written so the next agent can continue without re-discovery.

Fail closed: if a task cannot be completed, still sign out and state exactly what is
incomplete. Never claim verification that did not happen.

### Entry format

```
## [YYYY-MM-DD HH:MM TZ] — <agent name / model>
Task: <what was assigned>
Touched: <files created / modified / deleted / moved>
Why: <the reasoning, not just the diff>
Verification: <what was actually checked and the observed result>
Left undone: <what is incomplete, needs review, or is deferred — or "nothing">
Sensitive: <any remote writes, secrets, or destructive actions, or "none">
```

### Current status block (keep updated at the top of the ledger)

```
STATUS WHEN LAST LEFT: Working — Assay 0.4.0, a staged preview candidate (release
record 2026-11-22): offline by construction, CI green on aa43016 (2026-11-27),
deterministic core
reused from Signoff 0.1.0. Not independently audited for stable release use.
Docs restructured to the 2026-11-26 governance pass (AGENTS/CONSTITUTION/GOVERNANCE
at root, one-off reports in docs/archive/). Open items: none release-blocking in the
finding register at docs/archive/RELEASE_READINESS.md; close the remaining
verification gaps there against evidence before any stable release.
```

## 3. Environment facts

- **Repo:** Assay — an offline sheet-ops tool that checks Excel/CSV sheets against plain-English check templates and produces hash-chained, traceable report packs (audit, two-sheet compare, analyze, compatibility, policy-driven decisions).
- **Owner account:** https://github.com/Hatemshalaby15071979
- **Default branch:** master
- **Where it runs:** fully local — CLI on the user's machine, GUI on `127.0.0.1` (local browser), Docker under `--network none`; CI on GitHub Actions. No network in the check path.
- **Verification command:** `PYTHONPATH=src python -m pytest -q` (mirrors `.github/workflows/ci.yml`)

## 4. Rules this agent must follow

- Read and obey **CONSTITUTION.md** (philosophy + clean-code policy). On conflict, it
  wins over this file.
- Follow **GOVERNANCE.md** for the repo map, documentation policy, and archiving rules.
- Keep `README.md` the single source of truth; landing pages and dashboards mirror it.
- Keep local and remote in harmony: after a sanctioned change, commit and push so the
  GitHub copy matches the working copy.
- Sign in and sign out every landing, with the real clock time.

## 5. Ledger (sign-in / sign-out)

## [2026-11-26 20:39 EET] — CodeBuddy Code (Codex), governance subagent
Task: Uniform governance pass — add root AGENTS/CONSTITUTION/GOVERNANCE, house-style README, aggressive root-doc cleanup; push to master.
Touched: CONSTITUTION.md (new, byte-identical to the shared canonical text); AGENTS.md (new, this file, seeded); GOVERNANCE.md (new); README.md (rewritten to the house style); CONTRIBUTING.md, GITHUB_SHIPMENT_REPORT.md, PRESHIPMENT_REPORT.md, PROVENANCE.md, RELEASE_READINESS.md → docs/archive/; cross-reference fixes in docs/ARCHITECTURE.md, tooling/fuzz/README.md, CHANGELOG.md. Also: local remote `origin` re-pointed from the dead Sheet-Solution URL to https://github.com/Hatemshalaby15071979/Assay.git, and origin/master merged into local master (both sides had made the same README logo-line change; trivial merge).
Why: Owner's 2026-11-26 instruction to bring every public repo to one governance standard and one house style.
Verification: CONSTITUTION.md md5sum equal to the canonical file; `git ls-files` confirms the five reports now live under docs/archive/; all root cross-references updated to the new paths.
Left undone: None for this pass.
Sensitive: git push of governance docs to master, authorised by owner 2026-11-26.

## [2026-11-27 02:49 EET] — sami (OpenMausBot), owner-authorised CI repair

STATUS: SIGN-IN (work in progress)

Task: Repair the red CI on master — run 45877938218 at commit 4636225. `scripts/check-scaffold.py` reports 3 missing required root files; `scripts/check-doc-consistency.py` reports the README no longer declares itself the status source. All three Tests jobs fail at step "Scaffold + offline + doc-consistency" and the "Version and status consistency" job fails at step 4, which skips Docker, Package, Release gate and Prerelease image.

Touched: Will touch `scripts/check-scaffold.py`, `scripts/check-doc-consistency.py`, `README.md`, and this ledger. No file moved, renamed or deleted.

Why: The 2026-11-26 governance pass moved CONTRIBUTING.md, PROVENANCE.md and RELEASE_READINESS.md into `docs/archive/` and rewrote the README to the house style, but neither evidence script was updated with it. Both now assert paths and a phrase that the governance pass deliberately removed, so the root cause is stale checks, not a broken product.

Verification: Planned — run `python scripts/check-scaffold.py`, `python scripts/check-offline.py` and `python scripts/check-doc-consistency.py` locally, then `PYTHONPATH=src python -m pytest -q`; then confirm the GitHub Actions run on the repair commit is green on every job, including the previously skipped Docker, Package, Release gate and Prerelease image jobs.

Left undone: Nothing at sign-in.

Sensitive: git push to master, authorised by the owner's instruction in chat on 2026-11-27.

## [2026-11-27 02:57 EET] — sami (OpenMausBot), owner-authorised CI repair

STATUS: SIGN-OUT (landing complete)

Task: Repair the red CI on master (run 45877938218 at 4636225). Done.

Touched: `scripts/check-scaffold.py` (required-path set now follows GOVERNANCE.md section 2: root is README/AGENTS/CONSTITUTION/GOVERNANCE/LICENSE/CHANGELOG/SECURITY, and the three reports are checked at `docs/archive/`); `scripts/check-doc-consistency.py` (live-doc scan pointed at the archived paths instead of the dead root paths, which it had been silently skipping); `tests/test_scaffold.py` (reads `docs/archive/PROVENANCE.md`); `README.md` (the "Current status" section now declares itself the single source of truth for project status, per AGENTS.md section 4, and the opening line states the offline guarantee up front as the scaffold test requires); `scripts/make-release.sh` (copied `PROVENANCE.md` from root — would have aborted the bundle); pointer comments in `.github/workflows/ci.yml`, `Dockerfile`, `pyproject.toml`, `src/sheet_solution/__init__.py`. No file moved or deleted.

Why: The 2026-11-26 governance pass was correct and deliberate; the checks that assert it were not updated with it. `check-scaffold.py` demanded three files at root that had just been archived and did not assert the new root set at all, and `check-doc-consistency.py` required a README phrase the house-style rewrite dropped. Because the scaffold step runs first, CI never reached the test suite — which was also stale, so two further failures in `tests/test_scaffold.py` had been invisible. Root cause was stale assertions, not a broken product.

Verification: Locally — `check-scaffold: OK — 83 required files present`, `check-offline: OK` (66 files, zero network imports/SDKs/outbound calls/env reads), `Documentation consistency checks passed`, GUI import OK, GUI smoke PASS, `326 passed`, determinism byte-identical across runs, 2000-row scale smoke ok. Each check was then re-run against a deliberately broken copy (removed `docs/archive/PROVENANCE.md`; removed the status declaration; removed `AGENTS.md`) and each failed as it should — the new root assertions catch a missing `AGENTS.md`, which the old check could not. On GitHub — run 45919490534 on `aa43016`: all 11 jobs success, including Docker (offline proof) and Package, which had been skipped; Prerelease image skipped by design (tag/dispatch only). Docker log shows `LEDGER-VERIFIED: 2 event(s)` and the example audit's 4 checks; Package built `assay-0.4.0`; Tests jobs show 85% coverage over 3609 statements.

Left undone: Nothing failing. Two things worth the owner's eye: (1) `docs/archive/` is scanned as live docs by `check-doc-consistency.py` — a deliberate choice, because the README still presents the release record and provenance as current claims, and all three are clean today; (2) the scaffold check asserts the root files but does not yet assert GOVERNANCE.md's "no stray .md/.txt at root" rule, which is the rule this whole breakage came from — left for the owner to call.

Sensitive: git push to master (two commits: 12c5d54 sign-in, aa43016 repair), authorised by the owner's instruction in chat on 2026-11-27.

## [2026-11-27 04:00 EET] — sami (OpenMausBot), owner-authorised root-hygiene assertion

STATUS: SIGN-IN (work in progress)

Task: Close the open item from the 02:57 sign-out. The owner answered "yes" in chat on 2026-11-27: make `scripts/check-scaffold.py` assert GOVERNANCE.md's root rule — "No stray `.md`/`.txt` at the root" — so the exact rule the 2026-11-26 breakage came from can no longer be violated silently.

Touched: Will touch `scripts/check-scaffold.py` (new root-hygiene assertion, driven by the GOVERNANCE.md section 2 document table), `tests/test_scaffold.py` (a test proving the assertion fails on a planted stray root doc), and this ledger. No file moved, renamed or deleted.

Why: The scaffold check asserts that required root files exist, but nothing asserted that *unlisted* root docs do not. That asymmetry is what let the governance pass archive three reports while the root set looked satisfied; a one-way check cannot protect a "nothing else at root" rule.

Verification: Planned — `python scripts/check-scaffold.py`, `python scripts/check-offline.py`, `python scripts/check-doc-consistency.py`, then `PYTHONPATH=src python -m pytest -q`; then a planted-stray negative run to prove the new assertion actually fails; then the GitHub Actions run on the new commit.

Left undone: Nothing at sign-in.

Sensitive: git push to master, authorised by the owner's instruction in chat on 2026-11-27.

