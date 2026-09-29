# // spec: coh-ev-01, coh-ev-05, coh-pol-02
"""Detached attestation over canonical decisions (S5 core).

Implements the frozen contract in `schemas/attestation.schema.json`:

  - ACYCLIC SEALING ORDER (coh-ev-01): the attestation is produced AFTER
    the canonical decision and evidence are sealed, and binds their digests.
  - SIGNER-SET VERIFICATION (coh-ev-05): a signature is evidence only when
    the signer is in the approved signer set, unrevoked, inside its
    validity window, and the key matches the recorded key_id.
  - SUBSTITUTION DETECTION: the statement digest must equal the digest of
    the decision payload actually presented, and every bound input digest
    must equal the decision's own identities.
  - ANTI-ROLLBACK (coh-pol-02): a bundle below the control-plane epoch
    floor is rejected.

Signature bytes are `_signed_statement(...)` (see attest_base): an
attestation produced by this chain or by the run-sealing chain verifies
under either verifier.
"""
import hashlib
import hmac

from . import canon, schemacheck
from .attest_base import (
    ATTESTATION_API,
    SIGNATURE_PREFIX,
    AttestationError,
    _keys,
    _signed_statement,
    key_id_for,
    signer_set_digest,
)


def attest(decision_payload: bytes, bound: dict, identity: str,
           issued_at=None) -> dict:
    """Produce a detached attestation over a canonical decision.

    `decision_payload` is the exact canonical bytes emitted as result.json —
    signing bytes (not a re-serialization) is what makes substitution
    detectable. Raises AttestationError when no signing key is configured
    for `identity`: an unconfigured signer produces NO attestation, never an
    unsigned one.
    """
    keys = _keys()
    if not keys:
        raise AttestationError(
            f"HUB_COHERENCE_SIGNER_KEYS not configured; refusing to produce "
            f"an unsigned attestation")
    key = keys.get(identity)
    if key is None:
        raise AttestationError(f"no signing key for identity {identity!r}")
    if not bound.get("evaluator_image_digest"):
        raise AttestationError(
            "cannot attest a decision with an unknown evaluator image "
            "identity; the execution must be attributed first")
    statement_digest = canon.digest_bytes("decision/v1", decision_payload)
    signer = {"key_id": key_id_for(key), "identity": identity}
    statement = _signed_statement(statement_digest, bound, signer, issued_at)
    signature = SIGNATURE_PREFIX + hmac.new(
        key, statement, hashlib.sha256).hexdigest()
    attestation = {
        "api_version": ATTESTATION_API,
        "statement_digest": statement_digest,
        "bound": bound,
        "signer": signer,
        "signature": signature,
    }
    if issued_at is not None:
        attestation["issued_at"] = issued_at
    errors = schemacheck.validate(attestation,
                                  schemacheck.load("attestation.schema.json"))
    if errors:
        raise AttestationError(
            "produced attestation violates schema: " + "; ".join(errors[:5]))
    return attestation


def verify(attestation, decision_payload: bytes, result_identities: dict,
           signer_set: list, reference_time: str = None) -> tuple:
    """Verify a detached attestation. Returns (ok, reason).

    Fail-closed order (first failure wins, each with a stable reason):
      malformed shape / schema violation -> statement-substitution ->
      unknown-signer -> revoked-signer -> signer-outside-validity-window ->
      key-mismatch -> signature-mismatch -> bound-input-substitution.

    `result_identities` are the digests the DECISION claims; every bound
    entry must match them. `reference_time` (a context's evaluation_time,
    never the host clock) governs signer validity windows.
    """
    if not isinstance(attestation, dict):
        return False, "attestation-malformed"
    errors = schemacheck.validate(attestation,
                                  schemacheck.load("attestation.schema.json"))
    if errors:
        return False, "attestation-schema:" + "; ".join(errors[:3])

    statement_digest = canon.digest_bytes("decision/v1", decision_payload)
    if attestation["statement_digest"] != statement_digest:
        return False, "statement-substitution"

    keys = _keys()
    signer = attestation["signer"]
    identity = signer["identity"]
    approved = None
    for entry in signer_set or []:
        if isinstance(entry, dict) and entry.get("identity") == identity:
            approved = entry
            break
    if approved is None:
        return False, f"unknown-signer:{identity}"
    if approved.get("revoked"):
        return False, f"revoked-signer:{identity}"
    if reference_time is not None:
        for field, comparison in (("valid_from", "min"), ("valid_until", "max")):
            edge = approved.get(field)
            if edge:
                try:
                    from datetime import datetime
                    pa = datetime.fromisoformat(
                        reference_time.replace("Z", "+00:00"))
                    pb = datetime.fromisoformat(edge.replace("Z", "+00:00"))
                    within = pa >= pb if comparison == "min" else pa <= pb
                except ValueError:
                    return False, f"signer-window-unparseable:{field}"
                if not within:
                    return False, f"signer-outside-validity-window:{field}"

    key = keys.get(identity)
    if key is None:
        return False, "verifier-has-no-key-for-signer"
    if key_id_for(key) != signer["key_id"]:
        return False, "key-mismatch"

    statement = _signed_statement(attestation["statement_digest"],
                                  attestation["bound"], signer,
                                  attestation.get("issued_at"))
    expected = SIGNATURE_PREFIX + hmac.new(
        key, statement, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, attestation["signature"]):
        return False, "signature-mismatch"

    for role, digest in attestation["bound"].items():
        if result_identities.get(role) != digest:
            return False, f"bound-input-substitution:{role}"
    return True, None


def check_anti_rollback(min_bundle_epoch, policy_epoch_floor) -> None:
    """Anti-rollback gate (coh-pol-02): a bundle whose epoch floor is below
    the control-plane floor is a rolled-back (trusted-but-obsolete) bundle
    and is rejected. Absence of a control-plane floor disables enforcement
    (grandfathered/older contexts), absence of the bundle field means the
    bundle predates epochs and is rejected whenever a floor exists."""
    if policy_epoch_floor is None:
        return
    if not isinstance(policy_epoch_floor, int) or policy_epoch_floor < 0:
        raise AttestationError(
            f"context policy_epoch_floor invalid: {policy_epoch_floor!r}")
    if min_bundle_epoch is None:
        raise AttestationError(
            f"policy rollback: bundle carries no epoch while the "
            f"control-plane floor is {policy_epoch_floor} (coh-pol-02)")
    if min_bundle_epoch < policy_epoch_floor:
        raise AttestationError(
            f"policy rollback: bundle epoch floor {min_bundle_epoch} is "
            f"below the control-plane floor {policy_epoch_floor} "
            f"(coh-pol-02)")


__all__ = [
    "AttestationError", "attest", "check_anti_rollback", "signer_set_digest",
    "verify",
]