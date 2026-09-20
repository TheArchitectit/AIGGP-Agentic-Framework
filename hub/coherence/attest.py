# // spec: coh-ev-01, coh-ev-05, coh-pol-02
"""Detached attestation over canonical decisions (S5 core).

Implements the frozen contract in `schemas/attestation.schema.json`:

  - ACYCLIC SEALING ORDER (coh-ev-01): the attestation is produced AFTER
    the canonical decision and evidence are sealed, and binds their digests.
    The decision never contains attestation material. Re-signing the same
    decision leaves the decision bytes unchanged.
  - SIGNER-SET VERIFICATION (coh-ev-05): a signature is evidence only when
    the signer is in the approved signer set, unrevoked, inside its
    validity window, and the key matches the recorded key_id. Every failure
    is fail-closed with a stable reason.
  - SUBSTITUTION DETECTION: the attestation's statement digest must equal
    the digest of the decision payload actually presented, and every bound
    input digest must equal the decision's own identities — a decision
    swapped under a valid attestation is rejected.

HONEST SCOPE: signatures are HMAC-SHA256 under keys from
HUB_COHERENCE_SIGNER_KEYS (JSON: identity -> hex key) — the same stand-in
scope as issue.py's countersignatures until ADR-018 lands real key
management. key_id is derived as the first 16 hex chars of sha256(key), so
key rotation is always visible in the attestation. Verification requires
the signer set; an unconfigurable verifier fails closed, never "accepts".
"""
import hashlib
import hmac
import json
import os

from . import canon, schemacheck

SIGNER_KEYS_ENV = "HUB_COHERENCE_SIGNER_KEYS"
SIGNER_IDENTITY_ENV = "HUB_COHERENCE_SIGNER_IDENTITY"
SIGNATURE_PREFIX = "hmac-sha256:"
ATTESTATION_API = "devgate.spec-coherence.attestation/v1"


class AttestationError(ValueError):
    """Attestation produce/verify failure (exit-31 class)."""


def signer_identity(environ=None) -> str:
    """The identity this runner attests as (empty when unset)."""
    import os as _os
    env = _os.environ if environ is None else environ
    return env.get(SIGNER_IDENTITY_ENV, "").strip()


def _keys() -> dict:
    """identity -> key bytes, from the environment. Empty when unconfigured
    (a missing configuration is a HARD no on signing, never an unsigned
    guess)."""
    raw = os.environ.get(SIGNER_KEYS_ENV, "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise AttestationError(
            f"{SIGNER_KEYS_ENV} must be a JSON object of identity -> hex key"
        ) from None
    if not isinstance(parsed, dict):
        raise AttestationError(
            f"{SIGNER_KEYS_ENV} must be a JSON object of identity -> hex key")
    keys = {}
    for identity, hexkey in parsed.items():
        if not isinstance(identity, str) or not isinstance(hexkey, str):
            raise AttestationError(
                f"{SIGNER_KEYS_ENV} entries must be identity -> hex string")
        try:
            keys[identity] = bytes.fromhex(hexkey)
        except ValueError:
            raise AttestationError(
                f"{SIGNER_KEYS_ENV}[{identity!r}] is not a hex key") from None
    return keys


def key_id_for(key: bytes) -> str:
    """Rotation-visible key identifier: first 16 hex of sha256(key)."""
    return hashlib.sha256(key).hexdigest()[:16]


def _signed_statement(statement_digest: str, bound: dict, signer: dict,
                      issued_at) -> bytes:
    """Exactly the bytes the signature commits to. Everything except the
    signature itself is inside the statement — including the signer, so an
    attestation cannot be re-attributed by editing the signer block."""
    return canon.canon({
        "statement_digest": statement_digest,
        "bound": bound,
        "signer": signer,
        "issued_at": issued_at,
    })


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
            f"{SIGNER_KEYS_ENV} not configured; refusing to produce an "
            f"unsigned attestation")
    key = keys.get(identity)
    if key is None:
        raise AttestationError(f"no signing key for identity {identity!r}")
    if not bound.get("evaluator_image_digest"):
        # The frozen attestation schema requires every bound digest — and
        # semantically an attestation WITNESSES the evaluator that produced
        # the decision. Attesting an unattributed execution would be a
        # lie by omission: require the identity (DEVGATE_IMAGE_DIGEST
        # injection) before signing.
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
        # A produced attestation that violates its own frozen schema is an
        # implementation bug — fail loudly rather than emit it.
        raise AttestationError(
            "produced attestation violates schema: " + "; ".join(errors[:5]))
    return attestation


def verify(attestation, decision_payload: bytes, result_identities: dict,
           signer_set: list, reference_time: str = None) -> tuple:
    """Verify a detached attestation. Returns (ok, reason).

    Fail-closed order (first failure wins, each with a stable reason):
      malformed shape / schema violation → statement-substitution →
      unknown-signer → revoked-signer → signer-outside-validity-window →
      key-mismatch → signature-mismatch → bound-input-substitution.

    `result_identities` are the digests the DECISION claims; every bound
    entry must match them — an attestation over different inputs does not
    witness this decision. `reference_time` (a context's evaluation_time,
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
                a, b = reference_time, edge
                # ISO-8601 with Z; lexicographic works for same-format
                # timestamps but parse for correctness.
                try:
                    from datetime import datetime
                    pa = datetime.fromisoformat(a.replace("Z", "+00:00"))
                    pb = datetime.fromisoformat(b.replace("Z", "+00:00"))
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


def signer_set_digest(entries: list) -> str:
    """Digest of an approved-signer set — bindable as the context's
    signer_set_digest so the verifier can detect a swapped set (the same
    binding discipline as baseline/exception sets, coh-ctx-01)."""
    if not isinstance(entries, list):
        raise AttestationError("signer set must be a list")
    return canon.digest_obj("context/v1", {"kind": "signer-set",
                                           "entries": entries})


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
