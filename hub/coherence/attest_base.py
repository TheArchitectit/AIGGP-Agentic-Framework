# // spec: coh-ev-05
"""Shared attestation primitives: error type, key material, statement bytes.

Both attestation chains (detached S5 and run-sealing) commit to the same
signed statement shape so an attestation produced by either chain verifies
under either verifier. Everything except the signature itself is inside the
statement — including the signer — so an attestation cannot be re-attributed
by editing the signer block.
"""
import hashlib
import json
import os
from pathlib import Path

from . import canon

SIGNER_KEYS_ENV = "HUB_COHERENCE_SIGNER_KEYS"
SIGNER_KEY_ENV = "HUB_COHERENCE_SIGNER_KEY"
SIGNER_KEY_ID_ENV = "HUB_COHERENCE_SIGNER_KEY_ID"
SIGNER_IDENTITY_ENV = "HUB_COHERENCE_SIGNER_IDENTITY"
EVALUATOR_IMAGE_ENV = "HUB_COHERENCE_EVALUATOR_IMAGE_DIGEST"
SIGNATURE_PREFIX = "hmac-sha256:"
ATTESTATION_API = "devgate.spec-coherence.attestation/v1"
SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


class AttestationError(RuntimeError, ValueError):
    """attestation failure (exit-33 class)."""


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
    """Exactly the bytes the signature commits to."""
    return canon.canon({
        "statement_digest": statement_digest,
        "bound": bound,
        "signer": signer,
        "issued_at": issued_at,
    })


def signer_set_digest(entries) -> str:
    """Digest of an approved-signer set.

    Accepts either the S5 list-of-entries form (bound as the context's
    signer_set_digest) or the run-sealing signer-set DOCUMENT form. Two
    shapes, one role: detect a swapped set.
    """
    if isinstance(entries, list):
        return canon.digest_obj("context/v1", {"kind": "signer-set",
                                               "entries": entries})
    if isinstance(entries, dict):
        return canon.digest_obj("signer-set/v1", entries)
    raise AttestationError("signer set must be a list or document")