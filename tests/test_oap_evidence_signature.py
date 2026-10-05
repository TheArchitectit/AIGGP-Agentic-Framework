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





class TestEnvelopeCanonicalBytes(unittest.TestCase):
    def test_frozen_field_list_matches_secure_method(self):
        text = (CHANGE / "secure-method.md").read_text(encoding="utf-8")
        section = text.split("## Envelope (both directions)")[1]
        section = section.split("## Verification stages")[0]
        required, _, _ = section.partition("Unknown critical fields")
        listed = re.findall(r"`([a-z_]+)`", required)
        self.assertEqual(listed, list(oap_evidence.ENVELOPE_FIELDS))
        self.assertEqual(
            oap_evidence.SIGNED_FIELDS,
            tuple(f for f in oap_evidence.ENVELOPE_FIELDS if f != "signature"))

    def test_signature_is_detached_from_the_signed_bytes(self):
        envelope = _envelope()
        unsigned = oap_evidence.canonical_envelope_bytes(envelope)
        with_placeholder = dict(envelope, signature="ed25519:" + "00" * 64)
        self.assertEqual(
            oap_evidence.canonical_envelope_bytes(with_placeholder), unsigned)

    def test_canonical_bytes_are_sorted_utf8_without_duplicates(self):
        envelope = _envelope()
        raw = oap_evidence.canonical_envelope_bytes(envelope)
        parsed = json.loads(raw.decode("utf-8"))
        self.assertEqual(raw, canon.canon(parsed))
        self.assertEqual(raw, canon.canon(
            dict(reversed(list(parsed.items())))))
        self.assertEqual(raw.decode("utf-8"), json.dumps(
            parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=True))

    def test_missing_binding_field_is_not_signable(self):
        envelope = _envelope()
        for field in oap_evidence.SIGNED_FIELDS:
            stripped = dict(envelope)
            stripped.pop(field)
            with self.assertRaises(oap_evidence.EvidenceSignatureError):
                oap_evidence.canonical_envelope_bytes(stripped)


class TestEnvelopeSignVerify(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = _seed(0x11)
        cls.public = ed25519.public_key(cls.seed)
        cls.key_id = oap_evidence.key_id_for(cls.public)
        cls.envelope = _envelope(cls.key_id)
        cls.signature = oap_evidence.sign_envelope(cls.envelope, cls.seed)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.trust_path = _trust_file(cls.tmp.name, [{
            "producer_id": "devgate-instance-1",
            "key_id": cls.key_id,
            "public_key": cls.public.hex(),
            "audience": "oap-observer",
            "direction": "devgate-to-oap",
            "valid_from": "2026-10-01T00:00:00Z",
            "valid_until": "2026-11-01T00:00:00Z",
            "revoked": False,
            "revocation_version": 1,
        }])
        cls.trust = TrustStore.load(cls.trust_path)
        cls.reference_time = "2026-10-04T12:30:00Z"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _verify(self, envelope=None, signature=None, entries=None, **kwargs):
        kwargs.setdefault("reference_time", self.reference_time)
        kwargs.setdefault("payload", PAYLOAD)
        kwargs.setdefault("result", RESULT)
        if entries is None:
            trust = self.trust
        else:
            trust = TrustStore.load(_trust_file(self.tmp.name, entries))
        return oap_evidence.verify_envelope(
            envelope if envelope is not None else self.envelope,
            signature if signature is not None else self.signature,
            trust, **kwargs)

    def test_valid_envelope_verifies(self):
        ok, reason = self._verify()
        self.assertTrue(ok, reason)
        self.assertIsNone(reason)

    def test_signature_prefix_and_length(self):
        self.assertTrue(self.signature.startswith("ed25519:"))
        self.assertEqual(len(self.signature), len("ed25519:") + 128)

    def test_payload_digest_binding_accepts_the_real_payload(self):
        ok, reason = self._verify(payload=PAYLOAD)
        self.assertTrue(ok, reason)

    def test_tampered_envelope_field_fails_signature(self):
        for field, value in (("native_status", "PASS"),
                             ("tenant_or_project_id", "other-project"),
                             ("nonce", "deadbeef")):
            tampered = dict(self.envelope, **{field: value})
            with self.subTest(field=field):
                ok, reason = self._verify(envelope=tampered)
                self.assertFalse(ok)
                self.assertEqual(reason, "signature-mismatch")

    def test_tampered_payload_digest_field_fails_signature(self):
        tampered = dict(self.envelope,
                        payload_digest="sha256:" + "00" * 32)
        ok, reason = self._verify(envelope=tampered)
        self.assertFalse(ok)
        # Gate 2.3: the recomputed digest catches the lie before the
        # (equally valid over the tampered bytes) signature check would.
        self.assertEqual(reason, "payload-digest-mismatch")

    def test_tampered_payload_bytes_fail_digest_binding(self):
        ok, reason = self._verify(payload=PAYLOAD + b"extra")
        self.assertFalse(ok)
        self.assertEqual(reason, "payload-digest-mismatch")

    def test_wrong_key_id_fails(self):
        stranger_id = oap_evidence.key_id_for(ed25519.public_key(_seed(0x22)))
        tampered = dict(self.envelope, producer_key_id=stranger_id)
        ok, reason = self._verify(envelope=tampered)
        self.assertFalse(ok)
        self.assertEqual(reason, f"unknown-key:{stranger_id}")

    def test_signature_by_another_key_fails(self):
        # The attacker's move: keep the legitimate producer_key_id but sign the
        # canonical bytes with a key they control. sign_envelope refuses to do
        # this, so the forgery is built with the raw primitive.
        forged = "ed25519:" + ed25519.sign(
            _seed(0x33),
            oap_evidence.canonical_envelope_bytes(self.envelope)).hex()
        ok, reason = self._verify(signature=forged)
        self.assertFalse(ok)
        self.assertEqual(reason, "signature-mismatch")

    def test_expired_key_fails(self):
        ok, reason = self._verify(reference_time="2026-12-01T00:00:00Z")
        self.assertFalse(ok)
        self.assertEqual(reason, "key-expired")

    def test_not_yet_valid_key_fails(self):
        ok, reason = self._verify(reference_time="2026-09-01T00:00:00Z")
        self.assertFalse(ok)
        self.assertEqual(reason, "key-not-yet-valid")

    def test_revoked_key_fails(self):
        ok, reason = self._verify(entries=[_trust_entry(revoked=True)])
        self.assertFalse(ok)
        self.assertEqual(reason, f"revoked-key:{self.key_id}")

    def test_audience_mismatch_fails(self):
        ok, reason = self._verify(audience="some-other-oap")
        self.assertFalse(ok)
        self.assertEqual(reason, "audience-mismatch:oap-observer")

    def test_key_provisioned_for_other_audience_fails(self):
        ok, reason = self._verify(
            entries=[_trust_entry(audience="different-audience")])
        self.assertFalse(ok)
        self.assertEqual(reason, "key-audience-mismatch:different-audience")

    def test_key_provisioned_for_other_producer_fails(self):
        ok, reason = self._verify(
            entries=[_trust_entry(producer_id="someone-else")])
        self.assertFalse(ok)
        self.assertEqual(reason, "key-producer-mismatch:someone-else")

    def test_key_provisioned_for_other_direction_fails(self):
        ok, reason = self._verify(entries=[_trust_entry(direction="oap-to-devgate")])
        self.assertFalse(ok)
        self.assertEqual(reason, "key-direction-mismatch:oap-to-devgate")

    def test_unknown_critical_field_fails(self):
        tampered = dict(self.envelope, unexpected_critical_field="x")
        ok, reason = self._verify(envelope=tampered)
        self.assertFalse(ok)
        self.assertEqual(reason, "unknown-critical-field:unexpected_critical_field")

    def test_unsupported_contract_version_fails(self):
        tampered = dict(self.envelope, contract_version="devgate.oap-evidence/v2")
        ok, reason = self._verify(envelope=tampered)
        self.assertFalse(ok)
        self.assertEqual(reason, "unsupported-contract-version:'devgate.oap-evidence/v2'")

    def test_missing_binding_field_fails_before_signature(self):
        stripped = dict(self.envelope)
        stripped.pop("policy_digest")
        ok, reason = self._verify(envelope=stripped)
        self.assertFalse(ok)
        self.assertEqual(reason, "missing-binding-field:policy_digest")

    def test_malformed_signature_fails(self):
        for bad in ("", "ed25519:", "ed25519:zz", "hmac-sha256:" + "00" * 32,
                    b"\x00" * 63):
            with self.subTest(bad=str(bad)[:16]):
                ok, reason = self._verify(signature=bad)
                self.assertFalse(ok)
                self.assertEqual(reason, "signature-malformed")

    def test_key_entry_public_key_must_hash_to_the_declared_key_id(self):
        mismatched = [_trust_entry(
            public_key=ed25519.public_key(_seed(0x44)).hex())]
        ok, reason = self._verify(entries=mismatched)
        self.assertFalse(ok)
        self.assertEqual(reason, f"key-id-mismatch:{self.key_id}")

    def test_signing_refuses_a_mismatched_producer_key_id(self):
        stranger_id = oap_evidence.key_id_for(ed25519.public_key(_seed(0x22)))
        with self.assertRaises(oap_evidence.EvidenceSignatureError):
            oap_evidence.sign_envelope(
                dict(self.envelope, producer_key_id=stranger_id), self.seed)

    def test_key_id_is_domain_separated_from_a_bare_public_key_hash(self):
        bare = "sha256:" + hashlib.sha256(self.public).hexdigest()
        self.assertNotEqual(self.key_id, bare)
        self.assertTrue(self.key_id.startswith("ed25519:"))
        self.assertEqual(
            oap_evidence.key_id_for(self.public),
            oap_evidence.key_id_for(bytes(self.public)))


class TestEvidenceBinding(unittest.TestCase):
    """Gate 2.3: declared digests are recomputed from real bytes; missing,
    substituted, or unverifiable evidence is non-PASS even under a valid
    signature."""

    @classmethod
    def setUpClass(cls):
        cls.seed = _seed(0x11)
        cls.key_id = oap_evidence.key_id_for(ed25519.public_key(cls.seed))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.trust = TrustStore.load(_trust_file(
            cls.tmp.name, [_trust_entry(key_id=cls.key_id)]))
        cls.reference_time = "2026-10-04T12:30:00Z"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _verify(self, envelope, **kwargs):
        kwargs.setdefault("reference_time", self.reference_time)
        kwargs.setdefault("payload", PAYLOAD)
        kwargs.setdefault("result", RESULT)
        return oap_evidence.verify_envelope(
            envelope, oap_evidence.sign_envelope(envelope, self.seed),
            self.trust, **kwargs)

    def test_complete_evidence_verifies(self):
        ok, reason = self._verify(_envelope(self.key_id),
                                  evidence_manifest=MANIFEST,
                                  attestation=ATTESTATION)
        self.assertTrue(ok, reason)

    def test_substituted_result_fails(self):
        ok, reason = self._verify(_envelope(self.key_id), result=b'{"lie":1}')
        self.assertFalse(ok)
        self.assertEqual(reason, "canonical-result-digest-mismatch")

    def test_substituted_manifest_fails(self):
        envelope = _envelope(self.key_id)
        envelope["evidence_refs"] = envelope["evidence_refs"] + [
            {"name": "manifest.json", "digest": digest_of(MANIFEST),
             "purpose": "evidence-manifest"},
        ]
        ok, reason = self._verify(envelope,
                                  evidence_manifest=b'{"refs":["lie.json"]}')
        self.assertFalse(ok)
        self.assertEqual(reason, "evidence-manifest-digest-mismatch")

    def test_substituted_attestation_fails(self):
        envelope = _envelope(self.key_id)
        envelope["evidence_refs"] = envelope["evidence_refs"] + [
            {"name": "attestation.bin", "digest": digest_of(ATTESTATION),
             "purpose": "detached-attestation"},
        ]
        ok, reason = self._verify(envelope, attestation=b"other-attestation")
        self.assertFalse(ok)
        self.assertEqual(reason, "detached-attestation-digest-mismatch")

    def test_missing_payload_is_non_pass(self):
        ok, reason = self._verify(_envelope(self.key_id), payload=None)
        self.assertFalse(ok)
        self.assertEqual(reason, "missing-evidence-bytes:payload")

    def test_missing_result_is_non_pass(self):
        ok, reason = self._verify(_envelope(self.key_id), result=None)
        self.assertFalse(ok)
        self.assertEqual(reason, "missing-evidence-bytes:canonical-result")

    def test_missing_manifest_is_non_pass(self):
        envelope = _envelope(self.key_id)
        envelope["evidence_refs"] = envelope["evidence_refs"] + [
            {"name": "manifest.json", "digest": digest_of(MANIFEST),
             "purpose": "evidence-manifest"},
        ]
        ok, reason = self._verify(envelope)
        self.assertFalse(ok)
        self.assertEqual(reason, "missing-evidence-bytes:evidence-manifest")

    def test_valid_signature_over_lying_result_digest_fails(self):
        # The signer is honest; the envelope lies that the result digest is
        # something else. The signature over the lying envelope is valid, so
        # only the recomputed digest stops it.
        envelope = _envelope(self.key_id)
        envelope["evidence_refs"] = [
            {"name": "result.json", "digest": "sha256:" + "aa" * 32,
             "purpose": "canonical-result"},
        ]
        signature = oap_evidence.sign_envelope(envelope, self.seed)
        ok, reason = oap_evidence.verify_envelope(
            envelope, signature, self.trust,
            reference_time=self.reference_time, payload=PAYLOAD,
            result=RESULT)
        self.assertFalse(ok)
        self.assertEqual(reason, "canonical-result-digest-mismatch")

    def test_valid_signature_over_lying_payload_digest_fails(self):
        envelope = dict(_envelope(self.key_id),
                        payload_digest="sha256:" + "dd" * 32)
        signature = oap_evidence.sign_envelope(envelope, self.seed)
        ok, reason = oap_evidence.verify_envelope(
            envelope, signature, self.trust,
            reference_time=self.reference_time, payload=PAYLOAD)
        self.assertFalse(ok)
        self.assertEqual(reason, "payload-digest-mismatch")

    def test_unretrievable_evidence_purpose_denies(self):
        envelope = _envelope(self.key_id)
        envelope["evidence_refs"] = envelope["evidence_refs"] + [
            {"name": "remote.json", "digest": "sha256:" + "ab" * 32,
             "purpose": "remote-artifact"},
        ]
        ok, reason = self._verify(envelope)
        self.assertFalse(ok)
        self.assertEqual(reason, "missing-evidence-bytes:remote-artifact")


class TestCallerKeyringRejected(unittest.TestCase):
    """Gate 2.2/2.4 wiring: the receiver never accepts a caller-supplied
    keyring; trust comes only from the independently provisioned
    TrustStore file."""

    @classmethod
    def setUpClass(cls):
        cls.seed = _seed(0x11)
        cls.public = ed25519.public_key(cls.seed)
        cls.key_id = oap_evidence.key_id_for(cls.public)
        cls.envelope = _envelope(cls.key_id)
        cls.signature = oap_evidence.sign_envelope(cls.envelope, cls.seed)

    def _verify_with(self, third_arg):
        return oap_evidence.verify_envelope(
            self.envelope, self.signature, third_arg,
            reference_time="2026-10-04T12:30:00Z", payload=PAYLOAD,
            result=RESULT)

    def test_caller_list_keyring_is_rejected(self):
        attacker = [{
            "key_id": self.key_id,
            "public_key": self.public.hex(),
            "audience": "oap-observer",
            "revoked": False,
        }]
        ok, reason = self._verify_with(attacker)
        self.assertFalse(ok)
        self.assertEqual(reason, "caller-supplied-keyring-rejected")

    def test_caller_dict_keyring_is_rejected(self):
        attacker = {self.key_id: {
            "key_id": self.key_id,
            "public_key": self.public.hex(),
            "audience": "oap-observer",
            "revoked": False,
        }}
        ok, reason = self._verify_with(attacker)
        self.assertFalse(ok)
        self.assertEqual(reason, "caller-supplied-keyring-rejected")

    def test_attacker_key_in_caller_keyring_never_verifies(self):
        # Even a fully self-consistent attacker keyring (their key, their
        # signature over a well-formed envelope) is rejected as caller input.
        attacker_seed = _seed(0x66)
        attacker_public = ed25519.public_key(attacker_seed)
        attacker_key_id = oap_evidence.key_id_for(attacker_public)
        envelope = _envelope(attacker_key_id)
        signature = oap_evidence.sign_envelope(envelope, attacker_seed)
        ok, reason = oap_evidence.verify_envelope(envelope, signature, [{
            "key_id": attacker_key_id,
            "public_key": attacker_public.hex(),
            "audience": "oap-observer",
            "revoked": False,
        }])
        self.assertFalse(ok)
        self.assertEqual(reason, "caller-supplied-keyring-rejected")

    def test_trust_store_cannot_be_built_from_caller_data(self):
        with self.assertRaises(TrustStoreError):
            TrustStore([_trust_entry()])

    def test_raw_wire_path_rejects_caller_keyring_too(self):
        ok, reason = oap_evidence.verify_envelope(
            b"not-even-json", None, [{"key_id": "ed25519:" + "0" * 64}])
        self.assertFalse(ok)
        self.assertEqual(reason, "caller-supplied-keyring-rejected")


class TestBoundedSliceSurface(unittest.TestCase):
    def test_public_api_is_closed(self):
        self.assertEqual(
            set(oap_evidence.__all__),
            {"CONTRACT_VERSION", "ENVELOPE_FIELDS", "SIGNED_FIELDS",
             "EvidenceSignatureError", "canonical_envelope_bytes", "key_id_for",
             "sign_envelope", "verify_envelope"})

    def test_no_io_or_policy_mutation_capability_is_imported(self):
        forbidden = {"socket", "urllib", "http", "requests", "subprocess",
                     "shutil", "os", "ssl", "ftplib", "smtplib"}
        imported = {name for name, value in vars(oap_evidence).items()
                    if isinstance(value, type(sys))}
        self.assertEqual(imported & forbidden, set())
        self.assertEqual(set(oap_evidence.__dict__) & {
            "mutate_policy", "set_policy", "grant", "revoke", "server",
            "serve", "serve_forever", "publish"}, set())

    def test_existing_canonical_schemas_are_unchanged(self):
        for path, expected in FROZEN_SCHEMA_SHA256.items():
            with self.subTest(schema=path.name):
                self.assertTrue(path.exists(), path)
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), expected,
                    f"{path.name} changed: this slice must not edit existing "
                    f"canonical DevGate schemas")


class TestQuarantineNonAuthorizing(unittest.TestCase):
    """Gate 0: outputs of the evidence path are explicitly non-authorizing.

    See openspec/changes/harden-oap-evidence-verification/inventory-s-e0.md.
    A successful verify is math-only and must not satisfy a mandatory,
    promotion, release, or OAP-effect check.
    """

    def test_modules_carry_the_non_authorizing_marker(self):
        self.assertIs(ed25519.NON_AUTHORIZING, True)
        self.assertIs(oap_evidence.NON_AUTHORIZING, True)

    def test_verified_envelope_is_still_non_authorizing(self):
        seed = _seed(0x11)
        public = ed25519.public_key(seed)
        key_id = oap_evidence.key_id_for(public)
        envelope = _envelope(key_id)
        signature = oap_evidence.sign_envelope(envelope, seed)
        with tempfile.TemporaryDirectory() as tmp:
            trust = TrustStore.load(_trust_file(
                tmp, [_trust_entry(key_id=key_id,
                                   public_key=public.hex())]))
            ok, reason = oap_evidence.verify_envelope(
                envelope, signature, trust, payload=PAYLOAD, result=RESULT)
        self.assertTrue(ok, reason)
        self.assertIs(oap_evidence.NON_AUTHORIZING, True,
                      "verify success is non-authorizing; it is not a grant")

    def test_no_authorization_api_exists_on_the_quarantined_path(self):
        self.assertEqual(
            set(oap_evidence.__dict__) & {
                "grant", "authorize", "authorize_evidence",
                "promote", "allow_mandatory", "effect_authority"}, set())
        self.assertEqual(
            set(ed25519.__dict__) & {
                "grant", "authorize", "promote", "allow_mandatory"}, set())





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
