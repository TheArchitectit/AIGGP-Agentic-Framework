# // spec: coh-dec-01, coh-dec-03, coh-dec-04, coh-dec-05, coh-eval-03
"""Canonical result construction: ledger, finding sort/keys, canonical JSON,
decision/exit matrix. No timestamps, durations, host identity, or attestation
fields in the canonical payload.
"""
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


def decide(ledger: list, stage: int, error_class: str = None, error_reason: str = None) -> tuple:
    """Apply the decision/exit matrix. Returns (decision, exit_code)."""
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

    # Enforced stages: any violated or unresolved required assertion blocks.
    if stage in _BLOCK_STAGES:
        if violated or unresolved:
            return ("FAIL", EXIT_FAIL)
        return ("PASS", EXIT_PASS)

    # Advisory/inventory stages: violations visible but non-blocking.
    if violated or unresolved:
        return ("ADVISORY", EXIT_ADVISORY)
    return ("PASS", EXIT_PASS)


def build(ledger: list, findings: list, identities: dict, stage: int,
          semantics: str, evidence_manifest_digest: str) -> dict:
    """Build the canonical result payload (no attestation, no envelope)."""
    decision, _ = decide(ledger, stage)
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


def error_envelope(error_class: str, reason: str, stage: str, identities: dict) -> dict:
    """Structured error envelope; identities that could not be computed are null."""
    return {
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


def to_canonical(obj: dict) -> bytes:
    """Serialize under the frozen canonical profile (coh-dec-03)."""
    return canon.canon(obj)
