# // spec: coh-id-01, coh-id-05, coh-eval-01
"""Canonicalization and domain-separated digests (frozen profile).

Restricted RFC 8785 subset: sorted keys, no duplicate keys, UTF-8, int64
integers only (floats rejected — out of scope for v1), single number format.
File payloads are hashed as raw bytes; normalization applies to manifest
representation only, never to the bytes a file digest commits to.
"""
import hashlib
import json

INT64_MIN = -(2 ** 63)
INT64_MAX = 2 ** 63 - 1

ROLE_TAGS = frozenset({
    "subject-manifest/v1",
    "package/v1",
    "policy/v1",
    "context/v1",
    "evidence-manifest/v1",
    "decision/v1",
    "file/v1",
    # Domain separation: a signer set is its own identity — attest's
    # signer_set_digest must not be conflatable with any other role's digest.
    "signer-set/v1",
})


class CanonError(ValueError):
    """Raised when a value cannot be canonicalized under the profile."""


def _check(obj):
    if isinstance(obj, bool) or obj is None or isinstance(obj, str):
        return
    if isinstance(obj, int):
        if not (INT64_MIN <= obj <= INT64_MAX):
            raise CanonError(f"integer out of int64 range: {obj!r}")
        return
    if isinstance(obj, float):
        raise CanonError(f"floats are outside the v1 canonical profile: {obj!r}")
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise CanonError(f"non-string object key: {k!r}")
            _check(v)
        return
    if isinstance(obj, (list, tuple)):
        for v in obj:
            _check(v)
        return
    raise CanonError(f"unsupported type for canonical profile: {type(obj).__name__}")


def canon(obj) -> bytes:
    """Canonical JSON bytes under the restricted profile."""
    _check(obj)
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def digest(role_tag: str, payload: bytes) -> str:
    """Domain-separated sha256: tag bytes + 0x00 + payload."""
    if role_tag not in ROLE_TAGS:
        raise CanonError(f"unknown digest role tag: {role_tag!r}")
    h = hashlib.sha256()
    h.update(role_tag.encode("utf-8"))
    h.update(b"\x00")
    h.update(payload)
    return "sha256:" + h.hexdigest()


def digest_bytes(role_tag: str, payload: bytes) -> str:
    """Digest raw file bytes (no canonicalization)."""
    return digest(role_tag, payload)


def digest_obj(role_tag: str, obj) -> str:
    """Canonicalize then digest."""
    return digest(role_tag, canon(obj))
