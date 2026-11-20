"""Durable, hash-chained intent/result ledger for run and compare.

The report pack stays byte-identical; the ledger is a runtime evidence log
with wall-clock timestamps, deliberately separate from the deterministic
output contract. It records an intent **before** work starts and a result
**after**, so an interrupted run leaves a recoverable pending intent rather
than a silently partial pack.

Offline by construction: no network, no environment reads, no shelling out.
Anchoring is a local receipt file; there is no external timestamp authority.

Layout (under the run's output directory)::

    out/.audit/ledger.jsonl          # append-only, hash-chained events
    out/.audit/anchors/anchor-*.json # optional chained anchor receipts
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

GENESIS = "GENESIS"
BROKEN = "BROKEN"
INTENT_TYPE = "action.intent"
RESULT_TYPE = "action.result"

# Decision-loop evidence events. Wall clock and named human actor live only
# here (runtime evidence), never in the deterministic decision projection.
PROPOSAL_TYPE = "decision.proposed"
DECISION_TYPE = "decision.recorded"   # approve / decline / re-propose
APPLICATION_TYPE = "decision.applied"
DECISION_TYPES = (PROPOSAL_TYPE, DECISION_TYPE, APPLICATION_TYPE)


class LedgerError(RuntimeError):
    """Raised when a ledger cannot be appended or verified safely."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash_entry(entry: dict, prev_hash: str) -> str:
    payload = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((payload + prev_hash).encode("utf-8")).hexdigest()


def _strip_hash(entry: dict) -> dict:
    return {k: v for k, v in entry.items() if k != "hash"}


def verify_ledger(path: Path | str) -> dict:
    """Validate a ledger without any :class:`Ledger` instance state.

    Checks, in order: valid JSON per line, unique strictly-increasing
    sequence numbers, each ``prev_hash`` links to the previous entry, and each
    ``hash`` recomputes from its content. A missing or empty file verifies as
    an empty chain.
    """
    p = Path(path)
    prev = GENESIS
    expected_seq = 1
    seen: set[str] = set()
    count = 0
    if not p.exists():
        return {"ok": True, "reason": "empty", "count": 0, "head": GENESIS}
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    return {"ok": False, "reason": "corrupt_json", "seq": count + 1}
                count += 1
                if entry.get("seq") != expected_seq:
                    return {
                        "ok": False,
                        "reason": "sequence_gap",
                        "seq": entry.get("seq"),
                        "expected": expected_seq,
                    }
                if entry.get("prev_hash") != prev:
                    return {"ok": False, "reason": "chain_break", "seq": entry.get("seq")}
                digest = entry.get("hash", "")
                if digest in seen:
                    return {"ok": False, "reason": "duplicate_hash", "seq": entry.get("seq")}
                seen.add(digest)
                if _hash_entry(_strip_hash(entry), prev) != digest:
                    return {"ok": False, "reason": "bad_hash", "seq": entry.get("seq")}
                prev = digest
                expected_seq += 1
    except OSError as exc:
        return {"ok": False, "reason": f"io_error: {exc}"}
    return {"ok": True, "reason": "ok", "count": count, "head": prev}


class Ledger:
    """Append-only intent/result ledger, fail-closed on a broken chain.

    The in-process lock plus an advisory ``flock`` sidecar serialize appends
    on POSIX; other platforms fall back to the in-process lock. Every append
    is flushed and fsynced before it returns.
    """

    def __init__(self, path: Path | str, *, clock: Callable[[], str] = _now):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()
        self._clock = clock
        self._lock = threading.Lock()

    # -- append path -------------------------------------------------------
    def append(self, event_type: str, actor: str, payload: dict | None = None) -> dict:
        entry = {
            "seq": 0,
            "ts": self._clock(),
            "type": event_type,
            "actor": actor,
            "payload": payload or {},
        }
        with self._lock:
            lock_path = self.path.with_name(self.path.name + ".lock")
            with lock_path.open("a", encoding="utf-8") as lock_f:
                have_fcntl = False
                try:
                    import fcntl

                    fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
                    have_fcntl = True
                except (ImportError, OSError):
                    have_fcntl = False
                try:
                    chain = verify_ledger(self.path)
                    if not chain["ok"]:
                        raise LedgerError(
                            f"ledger chain is broken ({chain['reason']}) — refusing to append"
                        )
                    prev = chain["head"]
                    entry["seq"] = chain["count"] + 1
                    entry["prev_hash"] = prev
                    entry["hash"] = _hash_entry(_strip_hash(entry), prev)
                    line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
                    with self.path.open("a", encoding="utf-8") as f:
                        f.write(line + "\n")
                        f.flush()
                        os.fsync(f.fileno())
                    return entry
                finally:
                    if have_fcntl:
                        try:
                            import fcntl

                            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
                        except (ImportError, OSError):
                            have_fcntl = False

    def append_intent(self, kind: str, actor: str, payload: dict | None = None) -> dict:
        """Write a durable intent event BEFORE the described action runs."""
        return self.append(
            INTENT_TYPE,
            actor,
            {"intent_for": kind, "details": payload or {}},
        )

    def append_result(
        self,
        intent: dict,
        kind: str,
        actor: str,
        payload: dict | None = None,
    ) -> dict:
        """Append a result event linked to its intent by seq and hash."""
        if intent.get("type") != INTENT_TYPE:
            raise LedgerError("append_result requires an entry produced by append_intent")
        merged = dict(payload or {})
        merged["intent_seq"] = intent.get("seq")
        merged["intent_hash"] = intent.get("hash")
        return self.append(kind, actor, merged)

    # -- decision-loop evidence -------------------------------------------
    def append_proposal(self, decision, actor: str = "system") -> dict:
        """Durably record a finding before any human decision is made."""
        from sheet_solution.sheets.decisions import Decision

        if not isinstance(decision, Decision):
            raise LedgerError("append_proposal requires a Decision")
        return self.append(PROPOSAL_TYPE, actor, {"decision": decision.to_dict()})

    def append_decision(self, decision, actor: str, transition: str) -> dict:
        """Record a named human's approve/decline/re-propose transition."""
        from sheet_solution.sheets.decisions import Decision

        if not isinstance(decision, Decision):
            raise LedgerError("append_decision requires a Decision")
        if not isinstance(actor, str) or not actor.strip():
            raise LedgerError("a named human actor is required to record a decision")
        return self.append(DECISION_TYPE, actor.strip(), {
            "decision_id": decision.decision_id,
            "transition": transition,
            "state": decision.state,
            "proposed_action": decision.proposed_action,
            "note": decision.note,
        })

    def append_application(self, decision, actor: str, action_result) -> dict:
        """Record an applied action (only for a decision in APPLIED state)."""
        from sheet_solution.sheets.decisions import Decision, APPLIED

        if not isinstance(decision, Decision):
            raise LedgerError("append_application requires a Decision")
        if decision.state != APPLIED:
            raise LedgerError("only an APPLIED decision can be recorded as applied")
        return self.append(APPLICATION_TYPE, actor, {
            "decision_id": decision.decision_id,
            "action": getattr(action_result, "action", ""),
            "note": getattr(action_result, "note", ""),
            "drop": bool(getattr(action_result, "drop", False)),
        })

    # -- reads -------------------------------------------------------------
    def tail(self, n: int = 20) -> list[dict]:
        rows: list[dict] = []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            rows.append(json.loads(line))
                        except json.JSONDecodeError:
                            rows.append({"_corrupt": line[:80]})
        except OSError:
            return []
        return rows[-n:]

    def count(self) -> int:
        return len(self.tail(10**9))

    def verify(self) -> bool:
        return verify_ledger(self.path)["ok"]

    def decision_events(self) -> list[dict]:
        """All decision-loop evidence events, in sequence order."""
        return [e for e in self.tail(10**9) if e.get("type") in DECISION_TYPES]

    def pending_intents(self) -> list[dict]:
        """Return intents whose result was never appended (recoverable state)."""
        events = self.tail(10**9)
        completed = {
            (e.get("payload") or {}).get("intent_seq")
            for e in events
            if (e.get("payload") or {}).get("intent_seq") is not None
        }
        return [
            e
            for e in events
            if e.get("type") == INTENT_TYPE and e.get("seq") not in completed
        ]

    # -- local anchoring ---------------------------------------------------
    def anchor(self) -> dict:
        """Write a chained local receipt for the current head (no network)."""
        chain = verify_ledger(self.path)
        if not chain["ok"]:
            raise LedgerError(
                f"ledger chain is broken ({chain['reason']}) — refusing to anchor"
            )
        count = chain["count"]
        receipt_dir = self.path.parent / "anchors"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        prior = sorted(receipt_dir.glob("anchor-*.json"))
        prev_anchor_hash = GENESIS
        if prior:
            try:
                last = json.loads(prior[-1].read_text(encoding="utf-8"))
                prev_anchor_hash = last.get("anchor_hash", GENESIS)
            except (OSError, json.JSONDecodeError):
                prev_anchor_hash = GENESIS
        receipt = {
            "seq": count,
            "head_hash": chain["head"],
            "ts": self._clock(),
            "provider": "local",
            "prev_anchor_hash": prev_anchor_hash,
        }
        receipt["anchor_hash"] = hashlib.sha256(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        (receipt_dir / f"anchor-{count:08d}.json").write_text(
            json.dumps(receipt, indent=2), encoding="utf-8"
        )
        return receipt

    def check_anchor(self) -> dict:
        """Detect truncation, rewrite or reorder against the latest receipt."""
        receipt_dir = self.path.parent / "anchors"
        prior = sorted(receipt_dir.glob("anchor-*.json"))
        if not prior:
            return {"ok": True, "reason": "no_anchors"}
        prev = GENESIS
        for receipt_path in prior:
            try:
                rec = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return {"ok": False, "reason": "anchor_tampered"}
            if rec.get("prev_anchor_hash") != prev:
                return {"ok": False, "reason": "anchor_tampered"}
            stored = rec.pop("anchor_hash", None)
            recomputed = hashlib.sha256(
                json.dumps(rec, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            rec["anchor_hash"] = stored
            if stored != recomputed:
                return {"ok": False, "reason": "anchor_tampered"}
            prev = stored

        chain = verify_ledger(self.path)
        if not chain["ok"]:
            return {"ok": False, "reason": "chain_broken"}
        latest = json.loads(prior[-1].read_text(encoding="utf-8"))
        anchored_count = latest.get("seq", 0)
        anchored_head = latest.get("head_hash", "")
        if chain["count"] < anchored_count:
            return {
                "ok": False,
                "reason": "truncated",
                "anchored_seq": anchored_count,
                "current_seq": chain["count"],
            }
        if anchored_count >= 1 and chain["count"] >= anchored_count:
            events = self.tail(10**9)
            head_at_anchor = events[anchored_count - 1].get("hash", "")
            if head_at_anchor != anchored_head:
                return {
                    "ok": False,
                    "reason": "rewritten",
                    "anchored_head": anchored_head,
                    "current_head": head_at_anchor,
                }
        return {
            "ok": True,
            "reason": "ok",
            "anchored_seq": anchored_count,
            "current_seq": chain["count"],
        }
