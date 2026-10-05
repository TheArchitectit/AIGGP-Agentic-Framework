# // spec: coh-oap-01, coh-oap-07
"""Strict raw-bytes ingestion for the `devgate.oap-evidence/v2` wire object.

Gate 1.3/1.4 (openspec/changes/harden-oap-evidence-verification/contract-v2.md).

`json.loads` erases duplicate object keys and accepts UTF-16/32, a BOM and
unbounded nesting, so a dict handed to a verifier has already lost the facts a
strict receiver needs. This module is the mandatory first stage of the v2
verification path: raw bytes in, a shape-checked envelope out, with

  - duplicate keys rejected at **every** object depth,
  - UTF-8 decoded strictly (no BOM, no other encoding),
  - bounded resources (64 KiB total, depth 32, 1024 bytes per string),
  - unknown critical fields, unsupported versions/directions, invalid types,
    noncanonical wire bytes and status/exit laundering rejected before any
    canonicalization or signature work.

It never canonicalizes a lossy projection of a larger object: rejection happens
before `hub.coherence.canon` ever sees the value.

The signed bytes for a v2 body are ASCII `devgate.oap-evidence/v2`, one zero
byte, then the canonical `body` bytes. Key ids are `ed25519:` plus all 64
lowercase hex of SHA-256 over ASCII `devgate.oap-evidence.key-id/v2`, one zero
byte, then the 32 raw public-key bytes (v1's 32-hex truncated id is not
v2-compatible; see `hub.coherence.oap_evidence`).

Gate 0 quarantine (see inventory-s-e0.md) still applies: `verify_wire_envelope`
returns a mathematical verdict that is NON-AUTHORIZING. It is observe-only and
MUST NOT satisfy a mandatory, promotion, release, or OAP-effect check until
Gates 1-3 pass and the security reviewer plus OAP owner approve.
"""
import hashlib
import json
import re
from datetime import datetime

from . import canon, ed25519

# --- resource bounds (contract-v2.md §2) -----------------------------------
MAX_BYTES = 64 * 1024
MAX_DEPTH = 32
MAX_STRING = 1024

# --- wire shape ------------------------------------------------------------
CONTRACT_VERSION = "devgate.oap-evidence/v2"
SUPPORTED_VERSIONS = frozenset({CONTRACT_VERSION})
SUPPORTED_DIRECTIONS = frozenset({"devgate-to-oap"})

TOP_LEVEL_FIELDS = frozenset({"body", "signature"})

# Exact `body` member set (contract-v2.md §2). All required, none optional.
BODY_FIELDS = frozenset({
    "contract_version", "direction", "producer_id", "consumer_audience",
    "tenant_or_project_id", "subject_kind", "subject_digest", "request_id",
    "evaluation_id", "nonce", "idempotency_key", "issued_at", "expires_at",
    "policy_digest", "context_digest", "evaluator_digest", "native_decision",
    "native_exit_code", "semantics", "native_status", "native_reason",
    "result_digest", "evidence_manifest_digest", "attestation_digest",
    "payload_digest", "observe_only",
})

SIGNATURE_FIELDS = frozenset({"algorithm", "key_id", "value"})
SIGNATURE_ALGORITHM = "Ed25519"
SIGNATURE_PREFIX = "ed25519:"
KEY_ID_PREFIX = "ed25519:"
DOMAIN_TAG = b"devgate.oap-evidence/v2"
KEY_ID_TAG = "devgate.oap-evidence.key-id/v2"

# Bounded identifier / reason sizes (contract-v2.md §2).
IDENTIFIER_MAX = 256
REASON_MAX = 512
MAX_LIFETIME_SECONDS = 300  # maximum lifetime for the first pilot ≤ 5 minutes

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
KEY_ID_RE = re.compile(r"^ed25519:[0-9a-f]{64}$")
SIGNATURE_VALUE_RE = re.compile(r"^ed25519:[0-9a-f]{128}$")

STRING_FIELDS = (
    "producer_id", "consumer_audience", "tenant_or_project_id", "subject_kind",
    "request_id", "evaluation_id", "nonce", "idempotency_key",
)
DIGEST_FIELDS = (
    "subject_digest", "policy_digest", "context_digest", "evaluator_digest",
    "result_digest", "evidence_manifest_digest", "attestation_digest",
    "payload_digest",
)
STATUSES = frozenset({
    "PASS", "ADVISORY", "FAIL", "ERROR", "EMPTY", "SKIP", "UNKNOWN",
    "INCONCLUSIVE", "MALFORMED",
})
# native_decision -> admissible native_exit_code values (contract-v2.md §2).
DECISION_EXIT_CODES = {
    "PASS": frozenset({0}),
    "ADVISORY": frozenset({10}),
    "FAIL": frozenset({20}),
    "ERROR": frozenset({30, 31, 32, 33, 40}),
}
SEMANTICS = frozenset({"fresh-promotion", "replay"})


class StrictParseError(ValueError):
    """Raised when raw wire bytes are not an acceptable v2 envelope.

    The message is a stable, redaction-safe reason class (`duplicate-key:…`,
    `unsupported-contract-version:…`, …); it never contains secret material.
    """


def _object_pairs_hook(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise StrictParseError(f"duplicate-key:{key}")
        obj[key] = value
    return obj


def _check_limits(node) -> None:
    """Iteratively bound depth, string size, number domain. No recursion."""
    stack = [(node, 1)]
    while stack:
        value, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise StrictParseError(f"too-deep:{depth}")
        if isinstance(value, str):
            if len(value.encode("utf-8")) > MAX_STRING:
                raise StrictParseError("string-too-long")
        elif isinstance(value, bool) or value is None:
            continue
        elif isinstance(value, int):
            if not (canon.INT64_MIN <= value <= canon.INT64_MAX):
                raise StrictParseError(f"integer-out-of-range:{value!r}")
        elif isinstance(value, float):
            raise StrictParseError("float-not-allowed")
        elif isinstance(value, dict):
            for key, sub in value.items():
                if len(key.encode("utf-8")) > MAX_STRING:
                    raise StrictParseError("string-too-long")
                stack.append((sub, depth + 1))
        elif isinstance(value, list):
            for sub in value:
                stack.append((sub, depth + 1))
        else:  # pragma: no cover - json only produces the types above
            raise StrictParseError("unsupported-value")


def parse_object(raw: bytes):
    """Parse raw bytes into a Python value under the strict rules.

    Rejects anything that is not bounded, strictly-UTF-8 JSON with no
    duplicate keys at any depth. Returns the parsed value.
    """
    if isinstance(raw, (bytearray, memoryview)):
        raw = bytes(raw)
    if not isinstance(raw, bytes):
        raise StrictParseError("envelope-malformed:not-bytes")
    if len(raw) > MAX_BYTES:
        raise StrictParseError(f"too-large:{len(raw)}")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise StrictParseError("bom-not-allowed")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise StrictParseError("invalid-utf8") from None
    try:
        parsed = json.loads(text, object_pairs_hook=_object_pairs_hook)
    except StrictParseError:
        raise
    except RecursionError:
        raise StrictParseError(f"too-deep:{MAX_DEPTH}") from None
    except json.JSONDecodeError as exc:
        raise StrictParseError(f"malformed-json:{exc.msg}") from None
    _check_limits(parsed)
    return parsed


def _require_string(body, field, limit):
    value = body[field]
    if not isinstance(value, str) or isinstance(value, bool):
        raise StrictParseError(f"invalid-type:{field}")
    if not (1 <= len(value.encode("utf-8")) <= limit):
        raise StrictParseError(f"invalid-length:{field}")


def _require_digest(body, field):
    value = body[field]
    if not isinstance(value, str) or not DIGEST_RE.match(value):
        raise StrictParseError(f"invalid-digest:{field}")


def parse_utc_seconds(value):
    """Parse a UTC RFC3339-seconds timestamp (`YYYY-MM-DDTHH:MM:SSZ`)."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _validate_body(body) -> None:
    if not isinstance(body, dict):
        raise StrictParseError("envelope-malformed:body")
    for key in body:
        if key not in BODY_FIELDS:
            raise StrictParseError(f"unknown-critical-field:{key}")
    for field in sorted(BODY_FIELDS):
        if field not in body:
            raise StrictParseError(f"missing-required-field:{field}")
    for field in STRING_FIELDS:
        _require_string(body, field, IDENTIFIER_MAX)
    _require_string(body, "native_reason", REASON_MAX)
    for field in DIGEST_FIELDS:
        _require_digest(body, field)

    decision = body["native_decision"]
    if decision not in DECISION_EXIT_CODES:
        raise StrictParseError(f"invalid-decision:{decision!r}")
    exit_code = body["native_exit_code"]
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise StrictParseError("invalid-type:native_exit_code")
    if exit_code not in DECISION_EXIT_CODES[decision]:
        raise StrictParseError(f"decision-exit-mismatch:{decision}/{exit_code}")
    if body["native_status"] not in STATUSES:
        raise StrictParseError(f"invalid-status:{body['native_status']!r}")
    if body["semantics"] not in SEMANTICS:
        raise StrictParseError(f"invalid-semantics:{body['semantics']!r}")

    issued = parse_utc_seconds(body["issued_at"])
    expires = parse_utc_seconds(body["expires_at"])
    if issued is None:
        raise StrictParseError("invalid-timestamp:issued_at")
    if expires is None:
        raise StrictParseError("invalid-timestamp:expires_at")
    lifetime = (expires - issued).total_seconds()
    if lifetime <= 0:
        raise StrictParseError("invalid-lifetime:non-positive")
    if lifetime > MAX_LIFETIME_SECONDS:
        raise StrictParseError(f"invalid-lifetime:exceeds-{MAX_LIFETIME_SECONDS}s")

    if body["observe_only"] is not True:
        raise StrictParseError("invalid-flag:observe_only")


def _check_status_semantics(body) -> None:
    """PASS/0 paired with a non-PASS native status is a laundering attempt."""
    if body["native_decision"] == "PASS" and body["native_status"] != "PASS":
        raise StrictParseError(
            f"status-exit-mismatch:PASS/{body['native_status']}")


def _validate_signature(signature) -> None:
    if not isinstance(signature, dict):
        raise StrictParseError("envelope-malformed:signature")
    for key in signature:
        if key not in SIGNATURE_FIELDS:
            raise StrictParseError(f"unknown-critical-field:signature.{key}")
    for field in sorted(SIGNATURE_FIELDS):
        if field not in signature:
            raise StrictParseError(f"missing-required-field:signature.{field}")
    if signature["algorithm"] != SIGNATURE_ALGORITHM:
        raise StrictParseError(f"unsupported-algorithm:{signature['algorithm']!r}")
    if not isinstance(signature["key_id"], str) or \
            not KEY_ID_RE.match(signature["key_id"]):
        raise StrictParseError("invalid-key-id")
    if not isinstance(signature["value"], str) or \
            not SIGNATURE_VALUE_RE.match(signature["value"]):
        raise StrictParseError("invalid-signature")


def parse_envelope(raw: bytes) -> dict:
    """Parse and shape-check a v2 wire envelope. Returns the `{body,signature}`.

    Fails closed with a distinct reason at the first failed gate. The whole
    wire object must additionally be canonical bytes: a noncanonical
    serialization is rejected, not silently re-signed.
    """
    if isinstance(raw, (bytearray, memoryview)):
        raw = bytes(raw)
    obj = parse_object(raw)
    if not isinstance(obj, dict):
        raise StrictParseError("envelope-malformed:not-an-object")
    for key in obj:
        if key not in TOP_LEVEL_FIELDS:
            raise StrictParseError(f"unknown-critical-field:{key}")
    for key in ("body", "signature"):
        if key not in obj:
            raise StrictParseError(f"missing-required-field:{key}")

    body = obj["body"]
    if not isinstance(body, dict):
        raise StrictParseError("envelope-malformed:body")
    version = body.get("contract_version")
    if version not in SUPPORTED_VERSIONS:
        raise StrictParseError(f"unsupported-contract-version:{version!r}")
    direction = body.get("direction")
    if direction not in SUPPORTED_DIRECTIONS:
        raise StrictParseError(f"unsupported-direction:{direction!r}")

    _validate_body(body)
    _validate_signature(obj["signature"])
    _check_status_semantics(body)

    if canon.canon(obj) != raw:
        raise StrictParseError("noncanonical-json")
    return obj


def key_id_for(public_key: bytes) -> str:
    """Full 64-hex, domain-separated v2 key id (public metadata, not a secret)."""
    if len(public_key) != ed25519.PUBLIC_KEY_SIZE:
        raise StrictParseError("public key must be 32 bytes")
    h = hashlib.sha256()
    h.update(KEY_ID_TAG.encode("utf-8"))
    h.update(b"\x00")
    h.update(public_key)
    return KEY_ID_PREFIX + h.hexdigest()


def signed_bytes(body: dict) -> bytes:
    """Exact bytes the v2 signature commits to: domain tag + NUL + canonical body."""
    return DOMAIN_TAG + b"\x00" + canon.canon(body)


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


def _lookup(keyring, key_id):
    if isinstance(keyring, dict):
        return keyring.get(key_id)
    for entry in keyring or []:
        if isinstance(entry, dict) and entry.get("key_id") == key_id:
            return entry
    return None


def verify_wire_envelope(raw, keyring, *, reference_time=None, payload=None,
                         audience=None) -> tuple:
    """Verify a raw v2 wire envelope. Returns (ok, reason).

    The strict parse/shape gate runs first; every later reason is distinct so a
    failure at one stage cannot be smoothed into a later stage's success. The
    verdict is NON-AUTHORIZING (Gate 0 quarantine; observe-only).
    """
    try:
        envelope = parse_envelope(raw)
    except StrictParseError as exc:
        return False, str(exc)

    body = envelope["body"]
    signature = envelope["signature"]
    key_id = signature["key_id"]

    entry = _lookup(keyring, key_id)
    if not isinstance(entry, dict):
        return False, f"unknown-key:{key_id}"
    if entry.get("revoked"):
        return False, f"revoked-key:{key_id}"

    provisioned_audience = entry.get("audience")
    if provisioned_audience is not None and \
            provisioned_audience != body["consumer_audience"]:
        return False, f"key-audience-mismatch:{provisioned_audience}"
    if audience is not None and body["consumer_audience"] != audience:
        return False, f"audience-mismatch:{body['consumer_audience']}"

    reference = None
    if reference_time is not None:
        reference = parse_utc_seconds(reference_time)
        if reference is None:
            return False, "reference-time-unparseable"
        valid_from = parse_utc_seconds(entry.get("valid_from")) \
            if entry.get("valid_from") else None
        if entry.get("valid_from") and valid_from is None:
            return False, "key-window-unparseable:valid_from"
        if valid_from is not None and reference < valid_from:
            return False, "key-not-yet-valid"
        valid_until = parse_utc_seconds(entry.get("valid_until")) \
            if entry.get("valid_until") else None
        if entry.get("valid_until") and valid_until is None:
            return False, "key-window-unparseable:valid_until"
        if valid_until is not None and reference > valid_until:
            return False, "key-expired"

    public = _public_bytes(entry)
    if public is None:
        return False, f"key-entry-missing-public-key:{key_id}"
    if key_id_for(public) != key_id:
        return False, f"key-id-mismatch:{key_id}"

    if payload is not None:
        actual = "sha256:" + hashlib.sha256(payload).hexdigest()
        if body["payload_digest"] != actual:
            return False, "payload-digest-mismatch"

    raw_signature = bytes.fromhex(signature["value"][len(SIGNATURE_PREFIX):])
    if not ed25519.verify(public, signed_bytes(body), raw_signature):
        return False, "signature-mismatch"

    if reference is not None:
        issued = parse_utc_seconds(body["issued_at"])
        expires = parse_utc_seconds(body["expires_at"])
        if reference < issued:
            return False, "envelope-not-yet-valid"
        if reference >= expires:
            return False, "envelope-expired"
    return True, None


__all__ = [
    "BODY_FIELDS", "CONTRACT_VERSION", "MAX_BYTES", "MAX_DEPTH", "MAX_STRING",
    "SUPPORTED_DIRECTIONS", "SUPPORTED_VERSIONS", "StrictParseError",
    "key_id_for", "parse_envelope", "parse_object", "parse_utc_seconds",
    "signed_bytes", "verify_wire_envelope",
]
