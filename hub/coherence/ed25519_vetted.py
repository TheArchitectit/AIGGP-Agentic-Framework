# // spec: coh-oap-01
"""Vetted constant-time Ed25519 provider wrapper (Gate 1, design §1a).

Production signing SHALL use this module (cryptography.hazmat Ed25519), not
`hub.coherence.ed25519`. The pure-Python module remains a test-vector /
educational reference only and MUST NOT sign with a production key.

Decision record (S-E1 task 1.1):
  Provider     : PyCA `cryptography`, observed 45.0.7 at decision time.
  Binding      : cryptography.hazmat.primitives.asymmetric.ed25519
                 (Ed25519PrivateKey / Ed25519PublicKey).
  Signing      : Ed25519PrivateKey.from_private_bytes(seed).sign(message)
                 — constant-time private-key operation. The pure-Python
                 scalar path is NOT constant-time and is not used here.
  Provenance   : github.com/pyca/cryptography, Apache-2.0 OR BSD-3-Clause,
                 published wheels for CPython on Windows/macOS/Linux.
  Runtime      : optional dependency. Absence is a packaging blocker: stay
                 observe-only/non-authorizing. Never fall back to the
                 pure-Python signer or HMAC for a production key.
  Profile      : strict cofactorless verification matching
                 `hub.coherence.ed25519.verify`:
                   - exact lengths (pk 32, sig 64)
                   - S < L
                   - canonical A and R (y < p, x=0 => sign bit 0)
                   - A and R on edwards25519
                   - neither A nor R small-order (order divides 8)
                 The strict checks run HERE before the provider verify:
                 OpenSSL acceptance of low-order A is version-dependent
                 (cryptography 45.0.7 accepts some low-order A with S=0).
  Review       : independent security review of this decision is still
                 required for Gate 1 exit; until Gates 1–3 pass and the
                 reviewer plus OAP owner approve, outputs stay NON-AUTHORIZING.

GATE 0 QUARANTINE: NON_AUTHORIZING is True. A True `verify` is a strict
mathematical equation check only — not authenticity, not authorization.
"""
import hashlib

try:
    import cryptography
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
except ImportError as _import_error:  # pragma: no cover - packaging probe
    cryptography = None
    InvalidSignature = None
    Ed25519PrivateKey = None
    Ed25519PublicKey = None
    _PROVIDER_IMPORT_ERROR = _import_error
else:
    _PROVIDER_IMPORT_ERROR = None

PROVIDER = "cryptography"
PROVIDER_VERSION = getattr(cryptography, "__version__", None)
AVAILABLE = cryptography is not None

# Gate 0 quarantine marker (see module docstring and inventory-s-e0.md).
NON_AUTHORIZING = True

SEED_SIZE = 32
PUBLIC_KEY_SIZE = 32
SIGNATURE_SIZE = 64

_Q = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _Q - 2, _Q)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)

# Complete set of edwards25519 encodings whose order divides the cofactor 8.
# Rejected for both A and R; includes the identity (first entry).
_LOW_ORDER_ENCODINGS = frozenset(bytes.fromhex(h) for h in (
    "0100000000000000000000000000000000000000000000000000000000000000",
    "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000080",
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
    "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a",
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc85",
    "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac03fa",
))


class Ed25519Error(ValueError):
    """Malformed seed, public key, or signature input."""


def _require_provider():
    if not AVAILABLE:
        raise Ed25519Error(
            "vetted Ed25519 provider unavailable: "
            f"{_PROVIDER_IMPORT_ERROR!r}; stay non-authorizing, do not fall back")


def _xrecover(y):
    xx = (y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q) % _Q
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q:
        x = (x * _I) % _Q
    if x % 2:
        x = _Q - x
    return x


def _decode_point_strict(raw: bytes):
    """Strict RFC 8032 point decode — same profile as hub.coherence.ed25519.

    Rejects malformed length, noncanonical y >= p, the invalid sign-bit
    encoding (x=0 with sign=1), points off the curve, and low-order points
    (including the identity). Raises Ed25519Error on any violation.
    """
    if len(raw) != PUBLIC_KEY_SIZE:
        raise Ed25519Error("point encoding must be 32 bytes")
    if raw in _LOW_ORDER_ENCODINGS:
        raise Ed25519Error("low-order point")
    y = int.from_bytes(raw, "little") & ((1 << 255) - 1)
    if y >= _Q:
        raise Ed25519Error("noncanonical y coordinate")
    sign = raw[31] >> 7
    x = _xrecover(y)
    if x == 0 and sign:
        raise Ed25519Error("invalid sign bit: x=0 with sign=1")
    if (x & 1) != sign:
        x = _Q - x
    if (-x * x + y * y - 1 - _D * x * x * y * y) % _Q:
        raise Ed25519Error("point is not on edwards25519")


def public_key(seed: bytes) -> bytes:
    """Derive the 32-byte Ed25519 public key from a 32-byte seed."""
    _require_provider()
    if len(seed) != SEED_SIZE:
        raise Ed25519Error("seed must be 32 bytes")
    private = Ed25519PrivateKey.from_private_bytes(seed)
    return private.public_key().public_bytes_raw()


def sign(seed: bytes, message: bytes) -> bytes:
    """64-byte Ed25519 signature via the vetted constant-time provider."""
    _require_provider()
    if len(seed) != SEED_SIZE:
        raise Ed25519Error("seed must be 32 bytes")
    return Ed25519PrivateKey.from_private_bytes(seed).sign(message)


def verify(public: bytes, message: bytes, signature: bytes) -> bool:
    """Strict verification: True only when the RFC 8032 equation holds.

    Applies the full strict encoding profile (lengths, S < L, canonical
    on-curve A/R, no low-order points) BEFORE the provider verify, so
    acceptance does not depend on which low-order points the linked
    OpenSSL happens to tolerate. Still NON-AUTHORIZING.
    """
    _require_provider()
    if not isinstance(public, (bytes, bytearray)) or len(public) != PUBLIC_KEY_SIZE:
        return False
    if not isinstance(signature, (bytes, bytearray)) or len(signature) != SIGNATURE_SIZE:
        return False
    public = bytes(public)
    signature = bytes(signature)
    s = int.from_bytes(signature[32:], "little")
    if s >= _L:
        return False
    try:
        _decode_point_strict(public)
        _decode_point_strict(signature[:32])
    except Ed25519Error:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(signature, message)
    except (InvalidSignature, ValueError):
        return False
    return True
