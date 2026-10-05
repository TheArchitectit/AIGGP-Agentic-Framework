# // spec: coh-oap-01
"""Pure-stdlib Ed25519 (RFC 8032) — no third-party cryptography dependency.

The coherence package is stdlib-only by contract and neither `cryptography` nor
`nacl` is guaranteed in the pinned runtime, so this module implements the RFC
8032 Ed25519 signature scheme over edwards25519 using only `hashlib`. That
keeps artifact signing and verification working with nothing installed.

Scope: deterministic keygen from a 32-byte seed, deterministic sign, and strict
(cofactorless) verification of the RFC 8032 equation `[s]B = R + [k]A`.
Verification rejects identity and other low-order A/R points, noncanonical
y >= p, invalid sign bits, S >= L, and malformed lengths. Correctness is
pinned by the RFC 8032 §7.1 test vectors in
`tests/test_oap_evidence_signature.py`.

Production status (design §1a / S-E1): this module is a test-vector and
educational reference only. Private-key signing for any production key MUST
use `hub.coherence.ed25519_vetted` (constant-time vetted provider). This
module MUST NOT be presented as the mandatory verifier until the change's
later gates and independent review complete.

Honest limitation: the scalar arithmetic is plain Python, so it is not
constant-time. It is unsuitable where an attacker can time the signing process
on the same host; it is adequate for detached artifact verification. Do not
present it as more than that.

GATE 0 QUARANTINE (openspec/changes/harden-oap-evidence-verification):
every artifact produced or checked through this path is NON-AUTHORIZING.
A True return from `verify` is a mathematical equation check only — it is
not authenticity, not authorization, and MUST NOT satisfy a mandatory,
promotion, release, or OAP-effect check until that change's Gates 1–3
pass and an independent security reviewer plus the OAP owner approve.
See NON_AUTHORIZING and inventory-s-e0.md.
"""
import hashlib

_Q = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _Q - 2, _Q)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)

SEED_SIZE = 32
PUBLIC_KEY_SIZE = 32
SIGNATURE_SIZE = 64

# Gate 0 quarantine marker. True while outputs of this path remain
# non-authorizing (see module docstring and inventory-s-e0.md). Callers
# must treat a successful verify as math-only, never as a grant.
NON_AUTHORIZING = True


class Ed25519Error(ValueError):
    """Malformed seed, public key, or signature input."""


def _xrecover(y):
    xx = (y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q) % _Q
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q:
        x = (x * _I) % _Q
    if x % 2:
        x = _Q - x
    return x


_BASE_Y = (4 * pow(5, _Q - 2, _Q)) % _Q
_BASE = (_xrecover(_BASE_Y), _BASE_Y)
_IDENTITY = (0, 1)


def _add(p, q):
    """Twisted Edwards addition for a = -1 (the edwards25519 shape)."""
    x1, y1 = p
    x2, y2 = q
    k = _D * x1 * x2 * y1 * y2
    x3 = (x1 * y2 + x2 * y1) * pow(1 + k, _Q - 2, _Q)
    y3 = (y1 * y2 + x1 * x2) * pow(1 - k, _Q - 2, _Q)
    return (x3 % _Q, y3 % _Q)


def _scalarmult(point, scalar):
    result = _IDENTITY
    addend = point
    while scalar > 0:
        if scalar & 1:
            result = _add(result, addend)
        addend = _add(addend, addend)
        scalar >>= 1
    return result


def _encode_point(point):
    x, y = point
    return (y | ((x & 1) << 255)).to_bytes(PUBLIC_KEY_SIZE, "little")


def _is_small_order(point):
    """True when the point order divides the cofactor 8 (includes identity).

    The edwards25519 group order is 8*L, so [8]P is the identity exactly
    when P is one of the eight small-order points. Rejecting those closes
    the identity-key / identity-R / S=0 forgery class.
    """
    return _scalarmult(point, 8) == _IDENTITY


def _decode_point(raw):
    """Strict RFC 8032 point decode.

    Rejects malformed length, noncanonical y >= p, the invalid sign-bit
    encoding (x=0 with sign=1), points off the curve, and low-order
    points (including the identity). A successful decode is a canonical
    point of order > 8.
    """
    if len(raw) != PUBLIC_KEY_SIZE:
        raise Ed25519Error("point encoding must be 32 bytes")
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
    point = (x, y)
    if _is_small_order(point):
        raise Ed25519Error("low-order point")
    return point


def _clamped_scalar(h32):
    a = int.from_bytes(h32, "little")
    a &= (1 << 255) - 8  # clear the low 3 cofactor bits and the top bit
    a |= 1 << 254        # set the high bit of the secret scalar
    return a


def public_key(seed: bytes) -> bytes:
    """Derive the 32-byte Ed25519 public key from a 32-byte seed."""
    if len(seed) != SEED_SIZE:
        raise Ed25519Error("seed must be 32 bytes")
    return _encode_point(
        _scalarmult(_BASE, _clamped_scalar(hashlib.sha512(seed).digest()[:32])))


def sign(seed: bytes, message: bytes) -> bytes:
    """Deterministic 64-byte Ed25519 signature (RFC 8032)."""
    if len(seed) != SEED_SIZE:
        raise Ed25519Error("seed must be 32 bytes")
    h = hashlib.sha512(seed).digest()
    a = _clamped_scalar(h[:32])
    pk = _encode_point(_scalarmult(_BASE, a))
    r = int.from_bytes(hashlib.sha512(h[32:] + message).digest(), "little") % _L
    r_encoded = _encode_point(_scalarmult(_BASE, r))
    k = int.from_bytes(
        hashlib.sha512(r_encoded + pk + message).digest(), "little") % _L
    s = (r + k * a) % _L
    return r_encoded + s.to_bytes(32, "little")


def verify(public: bytes, message: bytes, signature: bytes) -> bool:
    """Strict verification: True only when the RFC 8032 equation holds.

    Strict profile: exact lengths, S < L, canonical A and R encodings
    (y < p, valid sign bit), both on-curve, and neither small-order.
    The identity-key / identity-R / S=0 forgery is rejected. Still
    NON-AUTHORIZING (see NON_AUTHORIZING) — math only.
    """
    if len(public) != PUBLIC_KEY_SIZE or len(signature) != SIGNATURE_SIZE:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _L:
        return False
    try:
        a = _decode_point(public)
        r = _decode_point(signature[:32])
    except Ed25519Error:
        return False
    k = int.from_bytes(
        hashlib.sha512(signature[:32] + public + message).digest(), "little") % _L
    return _scalarmult(_BASE, s) == _add(r, _scalarmult(a, k))
