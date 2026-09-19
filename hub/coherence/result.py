# // spec: coh-dec-01, coh-dec-03, coh-dec-04, coh-dec-05, coh-eval-03
"""Canonical result construction: ledger, finding sort/keys, canonical JSON,
decision/exit matrix. No timestamps, durations, host identity, or attestation
fields in the canonical payload.
"""
import os
import sys
import tempfile
from pathlib import Path

from . import canon

# Exit codes per the frozen matrix (decision-exit-matrix.md).
EXIT_PASS = 0
EXIT_ADVISORY = 10
EXIT_FAIL = 20
EXIT_INVALID_INPUT = 30
EXIT_POLICY = 31
EXIT_EXECUTION = 32
EXIT_EVIDENCE = 33
EXIT_PROTOCOL = 40

# Stage thresholds at which a VIOLATED enforced assertion blocks.
_BLOCK_STAGES = {2, 3, 4}


def _sort_findings(findings: list) -> list:
    return sorted(findings, key=lambda f: (
        f["assertion_id"], f["subject_locations"][0] if f["subject_locations"] else "",
        f["finding_key"]))


def _summary(ledger: list) -> dict:
    return {
        "planned": len(ledger),
        "satisfied": sum(1 for e in ledger if e["outcome"] == "SATISFIED"),
        "violated": sum(1 for e in ledger if e["outcome"] == "VIOLATED"),
        "unresolved": sum(1 for e in ledger if e["outcome"] == "UNRESOLVED"),
    }


def decide(ledger: list, stage: int, error_class: str = None,
           error_reason: str = None, blocked: bool = None) -> tuple:
    """Apply the decision/exit matrix. Returns (decision, exit_code).

    When `blocked` is supplied it is the adoption ladder's verdict (a BLOCK
    enforcement exists after ratification/exception logic). Otherwise the
    matrix falls back to stage-based blocking.
    """
    if error_class:
        exit_map = {
            "invalid-input": EXIT_INVALID_INPUT,
            "policy-resolution": EXIT_POLICY,
            "evaluator": EXIT_EXECUTION,
            "execution": EXIT_EXECUTION,
            "evidence": EXIT_EVIDENCE,
            "attestation": EXIT_EVIDENCE,
            "protocol": EXIT_PROTOCOL,
        }
        return ("ERROR", exit_map.get(error_class, EXIT_EXECUTION))

    violated = [e for e in ledger if e["outcome"] == "VIOLATED"]
    unresolved = [e for e in ledger if e["outcome"] == "UNRESOLVED"]

    if blocked is None:
        blocked = stage in _BLOCK_STAGES and bool(violated or unresolved)

    if blocked:
        return ("FAIL", EXIT_FAIL)
    if violated or unresolved:
        return ("ADVISORY", EXIT_ADVISORY)
    return ("PASS", EXIT_PASS)


def build(ledger: list, findings: list, identities: dict, stage: int,
          semantics: str, evidence_manifest_digest: str, blocked: bool = None) -> dict:
    """Build the canonical result payload (no attestation, no envelope)."""
    decision, _ = decide(ledger, stage, blocked=blocked)
    result = {
        "api_version": "devgate.spec-coherence.result/v1",
        "decision": decision,
        "semantics": semantics,
        "subject_digest": identities["subject_digest"],
        "openspec_digest": identities["openspec_digest"],
        "policy_digest": identities["policy_digest"],
        "context_digest": identities["context_digest"],
        "evaluator_image_digest": identities["evaluator_image_digest"],
        "platform": identities["platform"],
        "assertion_summary": _summary(ledger),
        "assertion_results": ledger,
        "findings": _sort_findings(findings),
        "evidence_manifest_digest": evidence_manifest_digest,
        "error": None,
    }
    return result


def error_envelope(error_class: str, reason: str, stage: str, identities: dict,
                   assertion_results: list = None) -> dict:
    """Structured error envelope; identities that could not be computed are null.

    assertion_results: the evaluation ledger, when an ERROR-execution run got
    far enough to produce one. The frozen matrix records ALL condition classes
    (tie-break 2), so a crash sharing the run with VIOLATED assertions still
    shows them — the dominant error class never erases the FAIL-class rows."""
    env = {
        "api_version": "devgate.spec-coherence.result/v1",
        "decision": "ERROR",
        "error": {"class": error_class, "reason": reason, "stage": stage},
        "identities": {
            "subject_digest": identities.get("subject_digest"),
            "openspec_digest": identities.get("openspec_digest"),
            "policy_digest": identities.get("policy_digest"),
            "context_digest": identities.get("context_digest"),
            "evaluator_image_digest": identities.get("evaluator_image_digest"),
        },
    }
    if assertion_results is not None:
        env["assertion_results"] = assertion_results
    return env


def to_canonical(obj: dict) -> bytes:
    """Serialize under the frozen canonical profile (coh-dec-03)."""
    return canon.canon(obj)


def emit(path: str, payload: bytes) -> None:
    """Atomic artifact write (coh-rt-07): the payload is fsynced to a
    dot-prefixed temp file in the SAME directory and only then renamed onto
    the canonical path. A process killed mid-write can leave a temp fragment
    behind, but a canonical path never holds partial bytes — consumers can
    treat presence as completeness."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.parent / f".{p.name}.tmp-{os.getpid()}"
    with open(tmp, "wb") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, p)
    dfd = os.open(p.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def emit_with_fallback(out_dir: str, payload: bytes) -> str:
    """Write the canonical payload, falling back to a temp location.

    The error paths must never depend on the same directory that just failed:
    if `out_dir` is unwritable (a regular file, read-only, or nested under a
    file) writing there raises and the process dies with a traceback instead of
    returning the documented exit code (audit round 2, B1 — this made exit 33
    unreachable).
    """
    try:
        emit(f"{out_dir}/result.json", payload)
        return out_dir
    except OSError:
        # The envelope must remain findable: announce the fallback location on
        # stderr so the operator holding exit 33 can locate the payload
        # (round-3 audit: an unfound envelope only half-meets the criterion).
        fallback = tempfile.mkdtemp(prefix="devgate-coherence-")
        emit(f"{fallback}/result.json", payload)
        print(f"result written to fallback location: {fallback}/result.json",
              file=sys.stderr)
        return fallback
