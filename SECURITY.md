# Sheet Solution — Security

## The security posture in one line

**Data never leaves the machine the user runs it on.** The tool makes zero
network calls, stores no credentials, calls no model, and sends nothing
anywhere. PII in the sheets (passport photos, personal data) stays local by
construction, not by policy.

## Threat model (summary)

| Threat | Mitigation |
|---|---|
| Exfiltration of PII | No network stack in the check path. `scripts/check-offline.py` AST-scans every module and fails the build on any `socket`/`urllib`/`requests`/model-SDK import or outbound call. Verified in CI on every commit. |
| Prompt / model injection | There is no model in the check path, so there is no prompt to inject. Deterministic rules only. |
| CSV formula injection | Report artifacts are written with the field-quoter that neutralises leading `=`/`+`/`-`/`@`/tab characters, so a cell containing `=CMD()` can't become a spreadsheet macro when the report is opened. |
| Partial / tampered report | Each report pack is hash-chained (SHA-256 over canonical JSON); `verify` replays the chain and flags any artifact whose digest no longer matches. |
| Supply chain | Runtime dependencies are pinned with SHA-256 hashes in `requirements.lock`; the Docker build installs them `--no-index` from a locally verified wheel set. Base image is digest-pinned. |
| Runaway / arbitrary code | No shell, no `eval`, no user-controlled code paths. The GUI binds `127.0.0.1` only and makes no outbound calls. |

## Non-goals (honest)

- This is a **deterministic checker**, not a cryptographic signer. A
  `VERIFIED` result means the report pack's digests and hash chain replay;
  it does **not** authenticate who produced the source sheet. No signing key
  exists in this repository and no signature is produced.
- Image/semantic checks are **human decisions**, logged as
  `PENDING-HUMAN` with the reviewer's note. The tool records *that a human
  reviewed it*, not *whether the image is valid*.
- It is not a compliance certification. It automates a manual inspection
  and produces an auditable log of that inspection.

## Reporting

There is no monitored security mailbox yet. If you have repository access,
open a private security advisory; otherwise do not send personal data in a
report. This is stated honestly rather than inventing a channel. The open
reporting item is tracked in [`RELEASE_READINESS.md`](RELEASE_READINESS.md).
