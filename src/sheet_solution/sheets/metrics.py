"""Deterministic ops metrics: what the machine decided vs what a human must.

Reads a run pack's ``check-results.csv`` and ``decisions.json`` and produces an
honest, deterministic summary. There is deliberately **no "auto-resolve"
claim**: every failed check becomes a finding that waits for a named human, so
the metric separates *checks the deterministic engine decided* from *items that
still need a person*, and *findings a human resolved* from *outstanding ones*.

No clock, no randomness, no network, no filesystem here: same inputs -> the
same byte-identical dict. The CLI writes that dict as ``metrics.json``.
"""
from __future__ import annotations

from dataclasses import dataclass

_PENDING = "PENDING-HUMAN"


@dataclass(frozen=True)
class Metrics:
    checks_total: int
    checks_pass: int
    checks_fail: int
    checks_pending_human: int
    findings_total: int
    findings_proposed: int
    findings_declined: int
    findings_approved: int
    findings_applied: int

    # -- derived, single definition each -----------------------------------
    @property
    def checks_machine_decided(self) -> int:
        """Checks the deterministic engine settled without a person."""
        return self.checks_pass + self.checks_fail

    @property
    def findings_resolved(self) -> int:
        return self.findings_applied

    @property
    def findings_outstanding(self) -> int:
        return (self.findings_proposed + self.findings_declined
                + self.findings_approved)

    @staticmethod
    def _pct(part: int, whole: int) -> float:
        return round(100.0 * part / whole, 1) if whole else 0.0

    def to_dict(self) -> dict:
        return {
            "checks": {
                "total": self.checks_total,
                "pass": self.checks_pass,
                "fail": self.checks_fail,
                "pending_human": self.checks_pending_human,
                "machine_decided": self.checks_machine_decided,
                "machine_decided_pct": self._pct(
                    self.checks_machine_decided, self.checks_total),
                "needs_human_pct": self._pct(
                    self.checks_pending_human, self.checks_total),
            },
            "findings": {
                "total": self.findings_total,
                "proposed": self.findings_proposed,
                "declined": self.findings_declined,
                "approved": self.findings_approved,
                "applied": self.findings_applied,
                "resolved": self.findings_resolved,
                "resolved_pct": self._pct(
                    self.findings_resolved, self.findings_total),
                "outstanding_pct": self._pct(
                    self.findings_outstanding, self.findings_total),
            },
        }

    def summary(self) -> str:
        d = self.to_dict()
        c, f = d["checks"], d["findings"]
        return "\n".join([
            "Sheet Solution — metrics",
            f"checks evaluated: {c['total']}",
            f"  pass: {c['pass']}  fail: {c['fail']}  human-review: {c['pending_human']}",
            f"  machine-decided: {c['machine_decided']}/{c['total']} "
            f"({c['machine_decided_pct']}%)  ·  needs a person: "
            f"{c['pending_human']}/{c['total']} ({c['needs_human_pct']}%)",
            f"findings: {f['total']}",
            f"  proposed: {f['proposed']}  declined: {f['declined']}  "
            f"approved: {f['approved']}  applied: {f['applied']}",
            f"  resolved: {f['resolved']}/{f['total']} ({f['resolved_pct']}%)  ·  "
            f"outstanding: {f['total'] - f['resolved']}/{f['total']} "
            f"({f['outstanding_pct']}%)",
        ])


def build_metrics(results: list[dict], decisions: list[dict]) -> Metrics:
    """Compute :class:`Metrics` from check-result rows and decision records."""
    passed = failed = human = 0
    for row in results:
        outcome = str(row.get("outcome", "")).upper()
        if outcome == "PASS":
            passed += 1
        elif outcome == "FAIL":
            failed += 1
        elif outcome == _PENDING:
            human += 1

    states: dict[str, int] = {}
    for d in decisions:
        state = str(d.get("state", "")).upper()
        states[state] = states.get(state, 0) + 1

    return Metrics(
        checks_total=len(results),
        checks_pass=passed, checks_fail=failed, checks_pending_human=human,
        findings_total=len(decisions),
        findings_proposed=states.get("PROPOSED", 0),
        findings_declined=states.get("DECLINED", 0),
        findings_approved=states.get("APPROVED", 0),
        findings_applied=states.get("APPLIED", 0),
    )
