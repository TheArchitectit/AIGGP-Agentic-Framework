# // spec: coh-oap-01, coh-oap-07
"""Detached Ed25519 signing/verification for the OAP evidence envelope.

Implements the signing half of the peer-side method in
`openspec/changes/add-oap-evidence-consumer/secure-method.md`:

  - CANONICAL BYTES: the signed bytes are the canonical JSON of the envelope's
    frozen field list — sorted keys, UTF-8, no duplicate keys — reusing
    `hub.coherence.canon`, the same frozen profile the rest of the service uses.
  - DETACHED ED25519: the signature covers every frozen field EXCEPT
    `signature` itself, via `hub.coherence.ed25519` (stdlib-only, RFC 8032).

The flat envelope field list below is the secure-method "Envelope (both
directions)" list. It is a transport/metadata shape that sits OUTSIDE the
canonical DevGate decision bytes; the nested `oap-evidence-envelope.schema.json`
fields map onto it (`producer.key_id` -> `producer_key_id`,
`devgate.identities.*` -> `*_digest`). This module changes none of the existing
canonical schemas.

HONEST SCOPE — bounded slice:
  - No live service, network API, OAP authority, or policy mutation is added.
  - No transport authentication (secure-method stage 2) and no consumer
    authorization (stage 4): those belong to the consumer, not to a library.
  - Verification is against an independently provisioned `TrustStore`
    (`hub.coherence.trust_store`, loaded from a provisioned trust file —
    never a caller-supplied keyring) AND a caller-supplied reference time,
    never the host clock — a producer timestamp is never proof of
    pre-revocation issuance, so freshness is the consumer's decision.

GATE 0 QUARANTINE (openspec/changes/harden-oap-evidence-verification):
every envelope verified through this path is NON-AUTHORIZING. A True
return from `verify_envelope` means the detached signature and local key
window checks passed; it is not authenticity, not authorization, and MUST
NOT satisfy a mandatory, promotion, release, or OAP-effect check until that
change's Gates 1-3 pass and an independent security reviewer plus the OAP
owner approve. See NON_AUTHORIZING and inventory-s-e0.md.
"""
import hashlib
from datetime import datetime

from . import canon, ed25519, strict_parse
from .trust_store import TrustStore, digest_of

CONTRACT_VERSION = "devgate.oap-evidence/v1"
# Gate 0 quarantine marker. True while outputs of this path remain
# non-authorizing (see module docstring and inventory-s-e0.md).
NON_AUTHORIZING = True
SUPPORTED_DIRECTIONS = frozenset({
    "devgate-to-oap", "oap-to-devgate", "guardrails-to-peer", "peer-to-guardrails",
})

# Frozen field list — secure-method.md "Envelope (both directions)".
ENVELOPE_FIELDS = (
    "contract_version", "direction", "producer_id", "producer_key_id",
    "consumer_audience", "tenant_or_project_id", "subject_kind",
    "subject_digest", "policy_digest", "context_digest", "evaluator_digest",
    "request_id", "evaluation_id", "idempotency_key", "nonce", "issued_at",
    "expires_at", "native_status", "native_reason", "payload_digest",
    "evidence_refs", "signature",
)
# Everything the signature commits to; the signature itself is detached.
SIGNED_FIELDS = tuple(f for f in ENVELOPE_FIELDS if f != "signature")

SIGNATURE_PREFIX = "ed25519:"
KEY_ID_PREFIX = "ed25519:"
# Domain separation for the key id: a versioned tag plus the public key bytes,
# so a key id cannot be conflated with any other digest in the profile.
KEY_ID_TAG = "devgate.oap-evidence.key-id/v1"


class EvidenceSignatureError(ValueError):
    """Raised when a signature cannot be produced.

    An inconsistent or unconfigured signer produces NO signature, never a
    wrong or unsigned one.
    """


def key_id_for(public_key: bytes) -> str:
    """Version-tagged, domain-separated key id (public metadata, not a secret)."""
    if len(public_key) != ed25519.PUBLIC_KEY_SIZE:
        raise EvidenceSignatureError("public key must be 32 bytes")
    h = hashlib.sha256()
    h.update(KEY_ID_TAG.encode("utf-8"))
    h.update(b"\x00")
    h.update(public_key)
    return KEY_ID_PREFIX + h.hexdigest()[:32]


def canonical_envelope_bytes(envelope: dict) -> bytes:
    """Exactly the bytes the signature commits to.

    Refuses an envelope missing any signed field: a missing binding must not be
    smoothed into a signable document.
    """
    if not isinstance(envelope, dict):
        raise EvidenceSignatureError("envelope must be an object")
    unsigned = {}
    for field in SIGNED_FIELDS:
        if field not in envelope:
            raise EvidenceSignatureError(
                f"missing binding field for signing: {field!r}")
        unsigned[field] = envelope[field]
    return canon.canon(unsigned)


def sign_envelope(envelope: dict, seed: bytes) -> str:
    """Detached Ed25519 signature over the envelope's canonical bytes.

    Raises when `producer_key_id` does not match the seed's public key: the
    envelope may not be signed by a key other than the one it names.
    """
    try:
        public = ed25519.public_key(seed)
    except ed25519.Ed25519Error as exc:
        raise EvidenceSignatureError(str(exc)) from None
    derived = key_id_for(public)
    declared = envelope.get("producer_key_id")
    if declared is not None and declared != derived:
        raise EvidenceSignatureError(
            f"envelope producer_key_id {declared!r} does not match the "
            f"signing key {derived!r}")
    return SIGNATURE_PREFIX + ed25519.sign(
        seed, canonical_envelope_bytes(envelope)).hex()


def _signature_bytes(signature):
    if isinstance(signature, bytes):
        return signature if len(signature) == ed25519.SIGNATURE_SIZE else None
    if isinstance(signature, str) and signature.startswith(SIGNATURE_PREFIX):
        try:
            raw = bytes.fromhex(signature[len(SIGNATURE_PREFIX):])
        except ValueError:
            return None
        return raw if len(raw) == ed25519.SIGNATURE_SIZE else None
    return None


def _public_bytes(entry):
    raw = entry.get("public_key")
    if isinstance(raw, bytes):
        return raw if len(raw) == ed25519.PUBLIC_KEY_SIZE else None
    if isinstance(raw, str):
        try:
            raw = bytes.fromhex(raw)
        except ValueError:
            return None
        return raw if len(raw) == ed25519.PUBLIC_KEY_SIZE else None
    return None


# Evidence purposes the receiver knows how to fetch bytes for, mapped to the
# `verify_envelope` keyword that carries those bytes (Gate 2.3).
PURPOSE_TO_PARAM = {
    "canonical-result": "result",
    "evidence-manifest": "evidence_manifest",
    "detached-attestation": "attestation",
}


def _parse_time(value):
    """Parse an ISO-8601 timestamp, or None when unparseable."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _bind_digest(declared, supplied, name):
    """Recompute one declared digest from the supplied bytes. Fail closed.

    Missing bytes for a declared digest are non-PASS; so are bytes that do
    not hash to the declared value.
    """
    if supplied is None:
        return False, f"missing-evidence-bytes:{name}"
    if declared != digest_of(supplied):
        return False, f"{name}-digest-mismatch"
    return True, None


def _bind_v1_evidence(envelope, payload, result, evidence_manifest,
                      attestation):
    """Recompute every declared v1 digest from supplied bytes."""
    ok, reason = _bind_digest(envelope.get("payload_digest"), payload,
                              "payload")
    if not ok:
        return False, reason
    refs = envelope.get("evidence_refs")
    if not isinstance(refs, list):
        return False, "invalid-evidence-ref"
    for ref in refs:
        if not isinstance(ref, dict) or \
                not all(isinstance(ref.get(k), str)
                        for k in ("name", "digest", "purpose")):
            return False, "invalid-evidence-ref"
        purpose = ref["purpose"]
        supplied = {
            "result": result,
            "evidence_manifest": evidence_manifest,
            "attestation": attestation,
        }.get(PURPOSE_TO_PARAM.get(purpose))
        ok, reason = _bind_digest(ref["digest"], supplied, purpose)
        if not ok:
            return False, reason
    return True, None


def verify_envelope(envelope, signature, trust_store, *, reference_time=None,
                    payload=None, audience=None, result=None,
                    evidence_manifest=None, attestation=None) -> tuple:
    """Verify a detached envelope signature. Returns (ok, reason).

    Fail-closed, first failure wins, each with a distinct reason code so no
    stage's failure can be smoothed into a later stage's success:

      trust:   caller-supplied-keyring-rejected -> reference-time-unparseable
               -> unknown-key -> revoked-key -> key-producer-mismatch ->
               key-direction-mismatch -> key-audience-mismatch ->
               key-not-yet-valid -> key-expired ->
               key-entry-missing-public-key -> key-id-mismatch
      context: audience-mismatch
      binding: missing-evidence-bytes:* -> *-digest-mismatch
      crypto:  signature-malformed -> signature-mismatch

    `trust_store` MUST be a `hub.coherence.trust_store.TrustStore` loaded
    from a provisioned trust file. A caller-supplied keyring (list, dict, or
    any other non-TrustStore value) is rejected outright: caller input is
    not trust. `reference_time` governs the key validity window and is the
    consumer's context time, not the host clock.

    Evidence binding (Gate 2.3): `payload`, `result`, `evidence_manifest`
    and `attestation` are the real evidence bytes. Every digest the envelope
    declares (`payload_digest`, and every `evidence_refs` entry matched by
    purpose) is recomputed from the supplied bytes; declared-but-missing
    bytes are non-PASS, as are bytes that do not hash to the declared
    digest. `audience`, when supplied, is the audience the consumer
    believes it is.

    Raw bytes are the v2 wire object and are routed through the strict parser
    first (`hub.coherence.strict_parse`): duplicate keys at any depth, invalid
    UTF-8, unbounded resources, unknown critical fields, an unsupported
    version/direction, invalid types and noncanonical bytes are rejected before
    canonicalization, then the v2 shape is verified. A dict is the already
    parsed v1 flat envelope (backward-compatible path).
    """
    if isinstance(envelope, (bytes, bytearray, memoryview)):
        return strict_parse.verify_wire_envelope(
            bytes(envelope), trust_store, reference_time=reference_time,
            payload=payload, audience=audience, result=result,
            evidence_manifest=evidence_manifest, attestation=attestation)
    if not isinstance(trust_store, TrustStore):
        return False, "caller-supplied-keyring-rejected"
    if not isinstance(envelope, dict):
        return False, "envelope-malformed"
    version = envelope.get("contract_version")
    if version != CONTRACT_VERSION:
        return False, f"unsupported-contract-version:{version!r}"
    for field in SIGNED_FIELDS:
        if field not in envelope:
            return False, f"missing-binding-field:{field}"
    for field in envelope:
        if field not in ENVELOPE_FIELDS:
            return False, f"unknown-critical-field:{field}"
    direction = envelope.get("direction")
    if direction not in SUPPORTED_DIRECTIONS:
        return False, f"unsupported-direction:{direction!r}"

    reference = None
    if reference_time is not None:
        reference = _parse_time(reference_time)
        if reference is None:
            return False, "reference-time-unparseable"

    key_id = envelope.get("producer_key_id")
    entry, reason = trust_store.evaluate(
        key_id, producer_id=envelope.get("producer_id"), direction=direction,
        audience=envelope.get("consumer_audience"), reference_time=reference)
    if reason:
        return False, reason

    if audience is not None and envelope.get("consumer_audience") != audience:
        return False, f"audience-mismatch:{envelope.get('consumer_audience')}"

    public = _public_bytes(entry)
    if public is None:
        return False, f"key-entry-missing-public-key:{key_id}"
    if key_id_for(public) != key_id:
        return False, f"key-id-mismatch:{key_id}"

    ok, reason = _bind_v1_evidence(envelope, payload, result,
                                   evidence_manifest, attestation)
    if not ok:
        return False, reason

    raw = _signature_bytes(signature)
    if raw is None:
        return False, "signature-malformed"
    if not ed25519.verify(public, canonical_envelope_bytes(envelope), raw):
        return False, "signature-mismatch"
    return True, None


__all__ = [
    "CONTRACT_VERSION", "ENVELOPE_FIELDS", "SIGNED_FIELDS",
    "EvidenceSignatureError", "canonical_envelope_bytes", "key_id_for",
    "sign_envelope", "verify_envelope",
]
