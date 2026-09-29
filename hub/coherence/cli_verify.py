# // spec: coh-ev-05
"""Consumer-side verification CLI helpers (S5) and the decision claim.

Kept out of hub/coherence/__main__.py so that module stays under the
500-line hard limit. The claim walks the verification ladder
REQUESTED->ATTEMPTED->EXECUTED->COMPLETED->TESTED->OBSERVED and
deliberately never reaches VERIFIED: reaching it requires an independent
check the producer does not own.
"""
import json
import sys
from pathlib import Path

from . import attest, canon, result, verification


def _emit_decision_claim(out_dir: str, res: dict, identities: dict,
                         ev_digest: str, ledger: list) -> None:
    """Emit decision.claim.json (+ .digest sidecar) beside the decision.

    The claim walks the verification ladder REQUESTED->ATTEMPTED->EXECUTED
    ->COMPLETED->TESTED->OBSERVED with per-stage reasons, binds every
    identity digest plus the decision payload digest, and deliberately
    never reaches VERIFIED: reaching it requires an independent check the
    producer does not own.
    """
    try:
        payload = result.to_canonical(res)
        claim = verification.new_claim(
            f"coherence-decision:{(identities.get('subject_digest')
                                   or 'unknown')[:23]}",
            f"spec-coherence decision for subject "
            f"{identities.get('subject_digest')}",
            subject_digest=identities.get("subject_digest"),
            actor="devgate-coherence")
        for role, digest in (
                ("subject", identities.get("subject_digest")),
                ("openspec", identities.get("openspec_digest")),
                ("policy", identities.get("policy_digest")),
                ("context", identities.get("context_digest")),
                ("evidence-manifest", ev_digest),
                ("decision", canon.digest_bytes("decision/v1", payload))):
            if digest:
                verification.bind(claim, role, digest)
        for state, reason in (
                (verification.ATTEMPTED,
                 "request accepted, identities computed"),
                (verification.EXECUTED, "assertions executed"),
                (verification.COMPLETED, "decision computed"),
                (verification.TESTED,
                 f"assertion ledger complete ({len(ledger)} entries)"),
                (verification.OBSERVED,
                 f"decision {res.get('decision')} sealed with evidence")):
            verification.transition(claim, state, reason=reason)
        verification.attach_evidence(claim, "evidence-manifest.json")
        claim_path = Path(out_dir) / "decision.claim.json"
        result.emit(str(claim_path), canon.canon(claim))
        result.emit(str(claim_path) + ".digest",
                    verification.digest_claim(claim).encode("utf-8"))
    except (verification.VerificationError, OSError) as e:
        print(f"warning: decision claim could not be written; the sealed "
              f"decision is unaffected ({e})", file=sys.stderr)


def _verify_outcome(args) -> int:
    """Offline attestation verification (S5): check a sealed output
    directory's attestation.json against its result.json and an approved
    signer set. Exit 0 verified; 1 rejected (with the stable reason);
    30 usage/missing-input error."""
    out_dir = Path(args.verify)
    result_fp = out_dir / "result.json"
    att_fp = out_dir / "attestation.json"
    missing = [str(p) for p in (result_fp, att_fp) if not p.is_file()]
    if missing:
        print(f"hub.coherence --verify: missing input(s): "
              f"{', '.join(missing)}", file=sys.stderr)
        return result.EXIT_INVALID_INPUT
    if not args.signers:
        print("hub.coherence --verify: --signers PATH (approved signer set) "
              "is required; verification without a signer set would be a "
              "rubber stamp", file=sys.stderr)
        return result.EXIT_INVALID_INPUT
    try:
        result_payload = result_fp.read_bytes()
        attestation = json.loads(att_fp.read_text())
        signer_set = json.loads(Path(args.signers).read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"hub.coherence --verify: cannot read inputs: {e}",
              file=sys.stderr)
        return result.EXIT_INVALID_INPUT

    # The decision's own claimed identities come from the result payload;
    # the attestation must bind exactly these (substitution detection).
    try:
        decided = json.loads(result_payload)
    except json.JSONDecodeError:
        print("hub.coherence --verify: result.json is not valid JSON",
              file=sys.stderr)
        return result.EXIT_INVALID_INPUT
    identities = {
        "subject_digest": decided.get("subject_digest"),
        "openspec_digest": decided.get("openspec_digest"),
        "policy_digest": decided.get("policy_digest"),
        "context_digest": decided.get("context_digest"),
        "evaluator_image_digest": decided.get("evaluator_image_digest"),
        "evidence_manifest_digest": decided.get("evidence_manifest_digest"),
    }
    ok, reason = attest.verify(attestation, result_payload, identities,
                               signer_set,
                               reference_time=args.reference_time)
    if ok:
        print(f"attestation OK — signer {attestation['signer']['identity']} "
              f"({attestation['signer']['key_id']}) binds decision "
              f"{attestation['statement_digest']}")
        return 0
    print(f"attestation REJECTED: {reason}")
    return 1


