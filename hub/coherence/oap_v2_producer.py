# // spec: coh-oap-01, coh-oap-07
"""DevGate-side construction of the frozen v2 observe-only wire artifact.

This is a bounded local producer adapter. It serializes already-sealed DevGate
result, evidence-manifest, and detached-attestation bytes; it does not publish,
authorize, or provide transport. Private-key signing requires the vetted
constant-time provider and never falls back to the educational implementation.
"""
from . import canon, ed25519_vetted, strict_parse
from .trust_store import digest_of

NON_AUTHORIZING = True


def produce(body: dict, *, payload: bytes, result: bytes,
            evidence_manifest: bytes, attestation: bytes, seed: bytes) -> bytes:
    """Build one canonical raw v2 artifact from exact sealed bytes.

    The caller supplies the producer's already-created body context. All four
    detached byte values are bound afresh here so a producer cannot sign a
    digest for different evidence. The resulting artifact is observe-only.
    """
    if not ed25519_vetted.AVAILABLE:
        raise RuntimeError("vetted Ed25519 provider unavailable")
    if not all(isinstance(value, bytes) for value in
               (payload, result, evidence_manifest, attestation)):
        raise TypeError("all evidence inputs must be bytes")
    body = dict(body)
    body.update({
        "contract_version": strict_parse.CONTRACT_VERSION,
        "direction": "devgate-to-oap",
        "result_digest": digest_of(result),
        "evidence_manifest_digest": digest_of(evidence_manifest),
        "attestation_digest": digest_of(attestation),
        "payload_digest": digest_of(payload),
        "observe_only": True,
    })
    public = ed25519_vetted.public_key(seed)
    signature = {
        "algorithm": "Ed25519",
        "key_id": strict_parse.key_id_for(public),
        "value": "ed25519:" + ed25519_vetted.sign(seed,
                                                     strict_parse.signed_bytes(body)).hex(),
    }
    return canon.canon({"body": body, "signature": signature})


__all__ = ["NON_AUTHORIZING", "produce"]
