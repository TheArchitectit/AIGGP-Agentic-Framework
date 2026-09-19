# // spec: coh-pol-04, coh-pol-05, coh-pol-06, coh-eval-05
"""Adoption ladder: fingerprinted baseline ratchet, scoped exceptions.

Baselines are SETS of fingerprints, not counts (coh-pol-04). A violation whose
fingerprint is in the baseline is named debt (ADVISORY); one that is not is a
regression and blocks at Stage >= 2. Exceptions never rewrite an outcome — they
change enforcement only (coh-eval-05), and expiry is evaluated against the
context evaluation_time, never the host clock.
"""
from datetime import datetime

from . import policy


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def fingerprint(assertion_id: str, version: int, location: str, vclass: str) -> str:
    """Stable, content-derived fingerprint (no whole-subject digests, no time)."""
    return "|".join([str(assertion_id), f"v{version}", str(location), str(vclass)])


def _vclass(finding: dict) -> str:
    """Violation class for the fingerprint.

    Read from the explicit `violation_class` field; falls back to the last
    segment of the finding key for findings produced before that field existed.
    """
    vc = finding.get("violation_class")
    if vc:
        return vc
    parts = finding.get("finding_key", "").split("|")
    return parts[-1] if len(parts) >= 3 else "unknown"


def _shelter_ends(stage: int, evaluator_of: dict, aid: str,
                  core_classes: frozenset) -> bool:
    """Does the baseline still shelter this assertion at this stage?

    The modes are the stages (design.md round-14): the ratchet (stage 2)
    shelters all named debt; enforced-core (3) ends shelter for the core
    classes only; enforced-full (4) ends it for everything. Below stage 2
    the caller never reaches here (stage < 2 is advisory). This is the one
    place stage changes WHICH findings a baseline excuses — every other
    ladder rule (exceptions, expiry, regression) is stage-invariant.
    """
    if stage >= 4:
        return True
    if stage == 3:
        return evaluator_of.get(aid) in core_classes
    return False


def validate_exceptions(exceptions: list) -> None:
    """Wildcards across assertions or repositories are forbidden (coh-pol-06)."""
    for ex in exceptions:
        if ex.get("assertion_id") in (None, "*", ""):
            raise policy.PolicyError("wildcard exception rejected: no assertion scope")
        if ex.get("subject_ref") in (None, "*", ""):
            raise policy.PolicyError("wildcard exception rejected: no subject scope")


def evaluate(ledger: list, findings: list, planned: list, baseline: list,
             exceptions: list, stage: int, evaluation_time: str,
             core_classes: frozenset = None) -> dict:
    """Apply the ladder. Returns ledger, findings, and whether anything blocks.

    `core_classes` are the evaluator IDs whose baseline shelter ends at Stage 3
    (enforced-core); None means the bundle named no set, so the ladder falls
    back to policy.DEFAULT_ENFORCED_CORE. Callers resolve the set from the
    bundle rather than here, keeping this function a pure ladder.
    """
    validate_exceptions(exceptions)
    if core_classes is None:
        core_classes = policy.DEFAULT_ENFORCED_CORE

    versions = {a["id"]: a.get("version", 1) for a in planned}
    # Core membership is by evaluator ID (the identity an assertion already
    # carries) — a repository cannot rename its way out of the enforced core.
    evaluator_of = {a["id"]: (a.get("evaluator") or {}).get("id")
                    for a in planned}
    baseline_fps = {
        fingerprint(b["fingerprint"]["assertion_id"],
                    b["fingerprint"]["assertion_version"],
                    b["fingerprint"]["subject_location"],
                    b["fingerprint"]["violation_key"])
        for b in baseline if b.get("status", "open") == "open"
    }

    now = _parse(evaluation_time)
    active_exc, expired_exc = {}, set()
    for ex in exceptions:
        fp = fingerprint(ex["finding_fingerprint"]["assertion_id"],
                         ex["finding_fingerprint"]["assertion_version"],
                         ex["finding_fingerprint"]["subject_location"],
                         ex["finding_fingerprint"]["violation_key"])
        if _parse(ex["expires_at"]) <= now:
            expired_exc.add(fp)
        else:
            active_exc[fp] = ex

    blocked = False
    for f in findings:
        aid = f["assertion_id"]
        fp = fingerprint(aid, versions.get(aid, 1),
                         f["subject_locations"][0] if f["subject_locations"] else "?",
                         _vclass(f))
        f["fingerprint"] = fp
        if stage < 2:
            f["enforcement"] = "ADVISORY"          # Stage 0/1: never blocks
        elif fp in expired_exc:
            f["enforcement"] = "BLOCK"             # expired exception -> blocks
            blocked = True
        elif fp in active_exc:
            f["enforcement"] = "EXCEPTION-ADVISORY"
            f["exception_id"] = active_exc[fp]["exception_id"]
        elif fp in baseline_fps and not _shelter_ends(stage, evaluator_of, aid,
                                                     core_classes):
            f["enforcement"] = "ADVISORY"          # named inherited debt
        else:
            f["enforcement"] = "BLOCK"             # regression -> blocks
            blocked = True

    # Ledger enforcement mirrors findings; unresolved required assertions are
    # incomplete execution and block at enforced stages.
    # One ledger row per assertion, but the engine emits many findings per
    # assertion (design.md section 8) — the row mirrors the STRICTEST
    # enforcement among them (a BLOCK must never be displayed away behind an
    # ADVISORY sibling), and `reason` names the softer classes that collapsed
    # into it so the single row is honest about what it represents.
    # Enforcement order is fixed (never a set membership), so rendering is
    # independent of finding order.
    _ENFORCEMENT_ORDER = {"ADVISORY": 0, "EXCEPTION-ADVISORY": 1, "BLOCK": 2}
    by_aid = {}
    for f in findings:
        by_aid.setdefault(f["assertion_id"], []).append(f)
    for e in ledger:
        if e["outcome"] == "SATISFIED":
            e["enforcement"] = "ADVISORY"
        elif e["outcome"] == "VIOLATED":
            fs = by_aid.get(e["assertion_id"])
            if not fs:
                # coh-eval-03: VIOLATED with no finding detail is itself an
                # evidence defect for enforced assertions, and blocks.
                e["enforcement"] = "BLOCK"
                e["reason"] = "violation-without-finding-detail"
                blocked = True
            else:
                strictest = max(fs,
                                key=lambda f: _ENFORCEMENT_ORDER[f["enforcement"]])
                e["enforcement"] = strictest["enforcement"]
                counts = {}
                for f in fs:
                    counts[f["enforcement"]] = counts.get(f["enforcement"], 0) + 1
                softer = sorted(set(counts) - {e["enforcement"]},
                                key=lambda name: _ENFORCEMENT_ORDER[name])
                if softer:
                    e["reason"] = (
                        f"multi-finding:{len(fs)} mirrors:{e['enforcement']}"
                        + "".join(f" softer:{name}x{counts[name]}"
                                  for name in softer))
                if e["enforcement"] == "BLOCK":
                    blocked = True
        else:  # UNRESOLVED: incomplete execution (coh-eval-02)
            e["enforcement"] = "BLOCK" if stage >= 2 else "ADVISORY"
            if e["enforcement"] == "BLOCK":
                blocked = True

    return {"ledger": ledger, "findings": findings, "blocked": blocked}