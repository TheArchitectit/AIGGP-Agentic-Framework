"""Conformance checks for the OAP evidence envelope detached signature.

Companion to tests/test_oap_evidence_schema.py: that file pins the observe-only
envelope SHAPE; this file pins the canonical-bytes signing/verification half of
the peer-side method (openspec/changes/add-oap-evidence-consumer/secure-method.md).

The signature is Ed25519 implemented in stdlib (`hub.coherence.ed25519`, no
third-party dependency); its correctness is pinned here against the RFC 8032
§7.1 vectors. The negative controls required by the slice are: tampered
payload/digest, wrong key id, expired key, revoked key.
"""
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHANGE = REPO / "openspec" / "changes" / "add-oap-evidence-consumer"
sys.path.insert(0, str(REPO))

from hub.coherence import canon, ed25519, oap_evidence
from hub.coherence.trust_store import TrustStore, TrustStoreError, digest_of

try:
    from hub.coherence import ed25519_vetted
except Exception as _vetted_import_error:  # pragma: no cover - packaging probe
    ed25519_vetted = None
    _VETTED_AVAILABLE = False
    _VETTED_SKIP = (
        f"NOT_RUN: vetted Ed25519 provider (hub.coherence.ed25519_vetted) "
        f"unavailable: {_vetted_import_error!r}")
else:
    _VETTED_AVAILABLE = bool(getattr(ed25519_vetted, "AVAILABLE", False))
    if _VETTED_AVAILABLE:
        _VETTED_SKIP = ""
    else:
        _VETTED_SKIP = (
            "NOT_RUN: vetted Ed25519 provider package "
            f"({getattr(ed25519_vetted, 'PROVIDER', 'cryptography')}) not importable "
            "in this runtime; production signing stays non-authorizing")


PAYLOAD = b'{"decision":"PASS","subject":"fixture-subject"}'
# Real evidence bytes the envelope's declared digests must commit to
# (Gate 2.3: declared digests are recomputed from supplied bytes).
RESULT = b'{"decision":"PASS","exit_code":0}'
MANIFEST = b'{"refs":["result.json"]}'
ATTESTATION = b"detached-attestation-bytes"
SEED = bytes([0x11]) * ed25519.SEED_SIZE
KEY_ID = oap_evidence.key_id_for(ed25519.public_key(SEED))


def _trust_file(directory, entries, *, snapshot_time=None):
    """Write a provisioned trust file with the given entries; return path."""
    path = Path(directory) / f"trust-{len(entries)}-{id(entries)}.json"
    doc = {"entries": entries}
    if snapshot_time is not None:
        doc["snapshot_time"] = snapshot_time
    path.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    return path


def _trust_entry(**overrides):
    entry = {
        "producer_id": "devgate-instance-1",
        "key_id": KEY_ID,
        "public_key": ed25519.public_key(SEED).hex(),
        "audience": "oap-observer",
        "direction": "devgate-to-oap",
        "valid_from": "2026-10-01T00:00:00Z",
        "valid_until": "2026-11-01T00:00:00Z",
        "revoked": False,
        "revocation_version": 1,
    }
    entry.update(overrides)
    return entry


def _seed(byte):
    return bytes([byte]) * ed25519.SEED_SIZE


# RFC 8032 §7.1 test vectors: (seed, public key, message, signature), all hex.
RFC8032 = (
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb882"
     "1590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1"
     "e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025", "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b"
     "538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
)

# Freeze pins (constraint: existing canonical DevGate schemas must not change).
# Update deliberately, never as a side effect of an unrelated slice.
#
# These are the SHA-256 of the COMMITTED (LF) bytes. `.gitattributes` pins the
# checkout to LF for exactly this reason: a pin taken from a CRLF working copy
# passes on Windows and fails on Linux, which is a property of the checkout,
# not of the schema. Change a schema → update its pin from the new blob.
FROZEN_SCHEMA_SHA256 = {
    CHANGE / "schemas" / "oap-evidence-envelope.schema.json":
        "7a4e126059c45702fa44c0ca612616996db9b694107d5ac605afbcef6fe0d5b5",
    REPO / "hub" / "coherence" / "schemas" / "result.schema.json":
        "49f8af5888615827a4b72ba726fc23fd0ccfcdf2da8aa803a92a990b49cc84cd",
    REPO / "hub" / "coherence" / "schemas" / "attestation.schema.json":
        "1832be3fc841bf2c71b2ad8702bc835d346c3894ce7590fd8df11712c7fc20ae",
}


class TestEd25519Primitive(unittest.TestCase):
    def test_rfc8032_vectors_sign_and_verify(self):
        for seed_hex, pk_hex, msg_hex, sig_hex in RFC8032:
            with self.subTest(seed=seed_hex[:16]):
                seed = bytes.fromhex(seed_hex)
                message = bytes.fromhex(msg_hex)
                self.assertEqual(ed25519.public_key(seed).hex(), pk_hex)
                self.assertEqual(ed25519.sign(seed, message).hex(), sig_hex)
                self.assertTrue(ed25519.verify(
                    bytes.fromhex(pk_hex), message, bytes.fromhex(sig_hex)))

    def test_verify_rejects_tampered_message_and_malformed_input(self):
        seed_hex, pk_hex, msg_hex, sig_hex = RFC8032[1]
        pk = bytes.fromhex(pk_hex)
        message = bytes.fromhex(msg_hex)
        sig = bytes.fromhex(sig_hex)
        self.assertFalse(ed25519.verify(pk, message + b"\x00", sig))
        self.assertFalse(ed25519.verify(pk, b"\xff" + message, sig))
        self.assertFalse(ed25519.verify(pk, message, sig[:63]))
        # A flipped bit inside S keeps it a canonical scalar but breaks the
        # equation: rejection must come from the check, not from the range test.
        self.assertFalse(ed25519.verify(
            pk, message, sig[:40] + bytes([sig[40] ^ 0x01]) + sig[41:]))
        self.assertFalse(ed25519.verify(b"\x00", message, sig))
        # s >= L is a non-canonical scalar and must be rejected outright.
        self.assertFalse(ed25519.verify(pk, message, sig[:32] + b"\xff" * 32))

    def test_seed_size_is_enforced(self):
        for bad in (b"", b"\x00" * 31, b"\x00" * 33):
            with self.assertRaises(ed25519.Ed25519Error):
                ed25519.public_key(bad)
            with self.assertRaises(ed25519.Ed25519Error):
                ed25519.sign(bad, b"m")


# The eight small-order edwards25519 encodings (order 1, 2, 4, or 8).
LOW_ORDER_POINTS = (
    "0100000000000000000000000000000000000000000000000000000000000000",
    "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",
    "0000000000000000000000000000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000000000000000080",
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
    "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a",
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc85",
    "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac03fa",
)

# edwards25519 prime; y values in [P, 2**255-1] are noncanonical.
_EDWARDS_P = 2 ** 255 - 19

_IDENTITY_ENC = bytes.fromhex(LOW_ORDER_POINTS[0])


class TestStrictPointValidation(unittest.TestCase):
    """Adversarial encodings the pre-fix decoder accepted.

    hub/coherence/ed25519.py:76-85 previously decoded y without y < p,
    ignored the x=0/sign=1 rule, and never rejected small-order points.
    """

    def test_identity_public_key_rejected(self):
        self.assertEqual(_IDENTITY_ENC, bytes([0x01]) + bytes(31))
        self.assertFalse(ed25519.verify(_IDENTITY_ENC, b"", b"\x00" * 64))
        self.assertFalse(ed25519.verify(_IDENTITY_ENC, b"m", b"\x00" * 64))

    def test_identity_r_rejected_with_valid_a(self):
        pk = ed25519.public_key(_seed(0x11))
        self.assertFalse(ed25519.verify(pk, b"m", _IDENTITY_ENC + bytes(32)))

    def test_low_order_points_rejected_as_a_or_r(self):
        message = b"low-order-message"
        for hexenc in LOW_ORDER_POINTS:
            point = bytes.fromhex(hexenc)
            other = ed25519.public_key(_seed(0x11))
            with self.subTest(point=hexenc[:16]):
                self.assertFalse(ed25519.verify(point, message, bytes(64)))
                self.assertFalse(ed25519.verify(
                    other, message, point + bytes(32)))

    def test_noncanonical_y_rejected(self):
        # y = 1 + p fits in 255 bits but is >= p; must not decode.
        y = 1 + _EDWARDS_P
        self.assertLess(y, 1 << 255)
        self.assertGreaterEqual(y, _EDWARDS_P)
        raw = y.to_bytes(32, "little")
        self.assertFalse(ed25519.verify(raw, b"m", bytes(64)))
        # Max 255-bit y (all bits below the sign bit set) is also noncanonical.
        raw_max = bytes([0xFF]) * 31 + bytes([0x7F])
        self.assertFalse(ed25519.verify(raw_max, b"m", bytes(64)))

    def test_invalid_sign_bit_rejected(self):
        # x=0 with sign=1 is not a canonical encoding (RFC 8032 5.1.3).
        for base in (
            bytes([0x01]) + bytes(31),  # identity, x=0
            bytes.fromhex(LOW_ORDER_POINTS[1]),  # (0, -1), x=0
        ):
            signed = bytearray(base)
            signed[31] |= 0x80
            with self.subTest(base=base.hex()[:16]):
                self.assertFalse(ed25519.verify(bytes(signed), b"m", bytes(64)))

    def test_malformed_lengths_rejected(self):
        pk = ed25519.public_key(_seed(0x11))
        sig = ed25519.sign(_seed(0x11), b"m")
        for bad_pk in (b"", b"\x00" * 31, b"\x00" * 33):
            self.assertFalse(ed25519.verify(bad_pk, b"m", sig))
        for bad_sig in (b"", b"\x00" * 63, b"\x00" * 65):
            self.assertFalse(ed25519.verify(pk, b"m", bad_sig))

    def test_s_greater_or_equal_l_rejected(self):
        pk = ed25519.public_key(_seed(0x11))
        r = ed25519.sign(_seed(0x11), b"m")[:32]
        s_max = (2 ** 256 - 1).to_bytes(32, "little")
        self.assertFalse(ed25519.verify(pk, b"m", r + s_max))
        s_l = (2 ** 252 + 27742317777372353535851937790883648493).to_bytes(32, "little")
        self.assertFalse(ed25519.verify(pk, b"m", r + s_l))


class TestMandatoryCheckRejectsIdentityForgery(unittest.TestCase):
    """Mandatory security check: identity A + identity R + S=0 must FAIL.

    Without the strict point-validation fix this test fails — the unsafe
    verifier accepted the forgery for arbitrary messages — so the pre-fix
    path cannot satisfy a mandatory check (see inventory-s-e0.md).
    """

    def test_identity_a_identity_r_s_zero_fails_multiple_messages(self):
        identity_a = _IDENTITY_ENC
        identity_r = _IDENTITY_ENC
        forged = identity_r + bytes(32)  # S = 0
        for message in (b"", b"m", b"hello world", b"\x00" * 64,
                        b'{"decision":"PASS"}', bytes(range(256))):
            with self.subTest(message=message[:20]):
                self.assertFalse(
                    ed25519.verify(identity_a, message, forged),
                    "identity-key forgery must never verify")

    def test_identity_forgery_cannot_verify_envelope(self):
        identity_a = _IDENTITY_ENC
        forged = "ed25519:" + (_IDENTITY_ENC + bytes(32)).hex()
        key_id = oap_evidence.key_id_for(identity_a)
        envelope = _envelope(key_id)
        with tempfile.TemporaryDirectory() as tmp:
            trust = TrustStore.load(_trust_file(tmp, [{
                "producer_id": "devgate-instance-1",
                "key_id": key_id,
                "public_key": identity_a.hex(),
                "audience": "oap-observer",
                "direction": "devgate-to-oap",
                "valid_from": None,
                "valid_until": None,
                "revoked": False,
                "revocation_version": 1,
            }]))
            ok, reason = oap_evidence.verify_envelope(
                envelope, forged, trust, payload=PAYLOAD, result=RESULT)
        self.assertFalse(ok)
        self.assertIn(reason, ("signature-mismatch",
                               f"key-id-mismatch:{key_id}"))


def _adversarial_point_vectors(pk, r_prefix):
    """(label, public, message, signature) vectors both providers must reject.

    Same strict-validation classes as hub/coherence/ed25519.py and
    hub/coherence/ed25519_vetted.py: identity A + identity R + S=0,
    noncanonical y, low-order A/R, S >= L, malformed lengths.
    """
    s_zero = bytes(32)
    vectors = [
        ("identity-a-identity-r-s0",
         _IDENTITY_ENC, b"m", _IDENTITY_ENC + s_zero),
        ("identity-a-identity-r-s0-empty-msg",
         _IDENTITY_ENC, b"", _IDENTITY_ENC + s_zero),
        ("identity-a-identity-r-s0-json",
         _IDENTITY_ENC, b'{"decision":"PASS"}', _IDENTITY_ENC + s_zero),
        ("identity-r-valid-a",
         pk, b"m", _IDENTITY_ENC + s_zero),
        ("s-max",
         pk, b"m", r_prefix + (2 ** 256 - 1).to_bytes(32, "little")),
        ("s-eq-l",
         pk, b"m", r_prefix + (2 ** 252 + 27742317777372353535851937790883648493)
          .to_bytes(32, "little")),
    ]
    # Noncanonical y (y >= p) as A and as R.
    y_noncanon = (1 + _EDWARDS_P).to_bytes(32, "little")
    y_max = bytes([0xFF]) * 31 + bytes([0x7F])
    vectors.append(("noncanonical-y-a", y_noncanon, b"m", bytes(64)))
    vectors.append(("noncanonical-y-max-a", y_max, b"m", bytes(64)))
    vectors.append(("noncanonical-y-r", pk, b"m", y_noncanon + s_zero))
    # Every small-order encoding as A and as R.
    for hexenc in LOW_ORDER_POINTS:
        point = bytes.fromhex(hexenc)
        vectors.append((f"low-order-a:{hexenc[:8]}", point, b"m", bytes(64)))
        vectors.append((f"low-order-r:{hexenc[:8]}", pk, b"m", point + s_zero))
    # Invalid sign-bit encodings (x=0 with sign=1).
    for base in (bytes([0x01]) + bytes(31),
                 bytes.fromhex(LOW_ORDER_POINTS[1])):
        signed = bytearray(base)
        signed[31] |= 0x80
        vectors.append((f"invalid-sign-bit:{bytes(signed).hex()[:8]}",
                        bytes(signed), b"m", bytes(64)))
        vectors.append((f"invalid-sign-bit-r:{bytes(signed).hex()[:8]}",
                        pk, b"m", bytes(signed) + s_zero))
    return vectors


def _malformed_length_vectors(pk, sig):
    """(public, signature) pairs with wrong lengths — both must reject."""
    return [
        (b"", sig), (b"\x00" * 31, sig), (b"\x00" * 33, sig),
        (pk, b""), (pk, b"\x00" * 63), (pk, b"\x00" * 65),
    ]


@unittest.skipUnless(_VETTED_AVAILABLE, _VETTED_SKIP)
class TestVettedProviderAdversarial(unittest.TestCase):
    """Gate 1.2 adversarial negatives against the vetted constant-time provider.

    Requires the same strict validation as hub/coherence/ed25519.py. Skipped
    with an explicit NOT_RUN reason when the vetted provider is not packaged.
    """

    def test_identity_a_identity_r_s_zero_rejected_multiple_messages(self):
        identity_a = _IDENTITY_ENC
        forged = identity_a + bytes(32)  # R = identity, S = 0
        for message in (b"", b"m", b"hello world", b"\x00" * 64,
                        b'{"decision":"PASS"}', bytes(range(256))):
            with self.subTest(message=message[:20]):
                self.assertFalse(
                    ed25519_vetted.verify(identity_a, message, forged),
                    "identity-key forgery must never verify on the vetted provider")

    def test_adversarial_vectors_match_pure_python_strict_profile(self):
        pk = ed25519_vetted.public_key(_seed(0x11))
        self.assertEqual(pk, ed25519.public_key(_seed(0x11)))
        r_prefix = ed25519_vetted.sign(_seed(0x11), b"m")[:32]
        for label, public, message, signature in _adversarial_point_vectors(
                pk, r_prefix):
            with self.subTest(vector=label):
                self.assertFalse(
                    ed25519_vetted.verify(public, message, signature),
                    f"vetted provider accepted adversarial vector {label}")
                self.assertFalse(
                    ed25519.verify(public, message, signature),
                    f"pure-Python accepted adversarial vector {label}")

    def test_malformed_lengths_rejected(self):
        pk = ed25519_vetted.public_key(_seed(0x11))
        sig = ed25519_vetted.sign(_seed(0x11), b"m")
        for public, signature in _malformed_length_vectors(pk, sig):
            with self.subTest(pk_len=len(public), sig_len=len(signature)):
                self.assertFalse(ed25519_vetted.verify(public, b"m", signature))

    def test_valid_rfc8032_vectors_still_pass(self):
        for seed_hex, pk_hex, msg_hex, sig_hex in RFC8032:
            with self.subTest(seed=seed_hex[:16]):
                seed = bytes.fromhex(seed_hex)
                message = bytes.fromhex(msg_hex)
                self.assertEqual(ed25519_vetted.public_key(seed).hex(), pk_hex)
                self.assertEqual(ed25519_vetted.sign(seed, message).hex(), sig_hex)
                self.assertTrue(ed25519_vetted.verify(
                    bytes.fromhex(pk_hex), message, bytes.fromhex(sig_hex)))

    def test_quarantine_marker_present(self):
        self.assertIs(ed25519_vetted.NON_AUTHORIZING, True)


@unittest.skipUnless(_VETTED_AVAILABLE, _VETTED_SKIP)
class TestCrossProviderInterop(unittest.TestCase):
    """Sign with one Ed25519 provider, verify with the other (and vice versa).

    Both providers must accept the same positives and reject the same
    adversarial vectors. If this class is NOT_RUN, the interop gap is the
    missing vetted provider (see _VETTED_SKIP).
    """

    def test_sign_cryptography_verify_pure_python(self):
        for seed_hex, pk_hex, msg_hex, sig_hex in RFC8032:
            with self.subTest(seed=seed_hex[:16]):
                seed = bytes.fromhex(seed_hex)
                message = bytes.fromhex(msg_hex)
                signature = ed25519_vetted.sign(seed, message)
                self.assertEqual(signature.hex(), sig_hex)
                self.assertTrue(ed25519.verify(
                    bytes.fromhex(pk_hex), message, signature))

    def test_sign_pure_python_verify_cryptography(self):
        for seed_hex, pk_hex, msg_hex, sig_hex in RFC8032:
            with self.subTest(seed=seed_hex[:16]):
                seed = bytes.fromhex(seed_hex)
                message = bytes.fromhex(msg_hex)
                signature = ed25519.sign(seed, message)
                self.assertTrue(ed25519_vetted.verify(
                    bytes.fromhex(pk_hex), message, signature))

    def test_adversarial_vectors_rejected_by_both_providers(self):
        seed = _seed(0x11)
        pk = ed25519_vetted.public_key(seed)
        self.assertEqual(pk, ed25519.public_key(seed))
        r_prefix = ed25519_vetted.sign(seed, b"m")[:32]
        for label, public, message, signature in _adversarial_point_vectors(
                pk, r_prefix):
            with self.subTest(vector=label):
                self.assertFalse(ed25519_vetted.verify(public, message, signature),
                                 f"vetted accepted {label}")
                self.assertFalse(ed25519.verify(public, message, signature),
                                 f"pure-Python accepted {label}")

    def test_malformed_lengths_rejected_by_both_providers(self):
        seed = _seed(0x11)
        pk = ed25519_vetted.public_key(seed)
        sig = ed25519_vetted.sign(seed, b"m")
        for public, signature in _malformed_length_vectors(pk, sig):
            with self.subTest(pk_len=len(public), sig_len=len(signature)):
                self.assertFalse(ed25519_vetted.verify(public, b"m", signature))
                self.assertFalse(ed25519.verify(public, b"m", signature))

    def test_tampered_message_rejected_by_both(self):
        seed = _seed(0x11)
        pk = ed25519_vetted.public_key(seed)
        signature = ed25519_vetted.sign(seed, b"m")
        for provider in (ed25519_vetted, ed25519):
            self.assertFalse(provider.verify(pk, b"m\x00", signature))
            self.assertFalse(provider.verify(pk, b"", signature))


# Shared with tests/test_oap_envelope_signature.py: one primitive-half
# test needs the same envelope fixture. Keep the two copies identical.
def _envelope(key_id=None):
    """A minimal but complete flat envelope per the secure-method field list."""
    return {
        "contract_version": oap_evidence.CONTRACT_VERSION,
        "direction": "devgate-to-oap",
        "producer_id": "devgate-instance-1",
        "producer_key_id": key_id or KEY_ID,
        "consumer_audience": "oap-observer",
        "tenant_or_project_id": "fixture-project",
        "subject_kind": "repository",
        "subject_digest": "sha256:" + "cc" * 32,
        "policy_digest": "sha256:" + "ee" * 32,
        "context_digest": "sha256:" + "ff" * 32,
        "evaluator_digest": "sha256:" + "11" * 32,
        "request_id": "request-001",
        "evaluation_id": "evaluation-001",
        "idempotency_key": "idempotency-001",
        "nonce": "nonce-001",
        "issued_at": "2026-10-04T12:00:00Z",
        "expires_at": "2026-10-04T13:00:00Z",
        "native_status": "ADVISORY",
        "native_reason": "observation-only fixture",
        "payload_digest": digest_of(PAYLOAD),
        "evidence_refs": [
            {"name": "result.json", "digest": digest_of(RESULT),
             "purpose": "canonical-result"},
        ],
    }


if __name__ == "__main__":
    unittest.main()
