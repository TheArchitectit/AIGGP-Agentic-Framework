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
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHANGE = REPO / "openspec" / "changes" / "add-oap-evidence-consumer"
sys.path.insert(0, str(REPO))

from hub.coherence import canon, ed25519, oap_evidence


PAYLOAD = b'{"decision":"PASS","subject":"fixture-subject"}'
SEED = bytes([0x11]) * ed25519.SEED_SIZE
KEY_ID = oap_evidence.key_id_for(ed25519.public_key(SEED))


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
FROZEN_SCHEMA_SHA256 = {
    CHANGE / "schemas" / "oap-evidence-envelope.schema.json":
        "7a4e126059c45702fa44c0ca612616996db9b694107d5ac605afbcef6fe0d5b5",
    REPO / "hub" / "coherence" / "schemas" / "result.schema.json":
        "8560e9efb9e7a5180ffc113d67d0b13537de8a40003ad256908d97bd1f5a4f33",
    REPO / "hub" / "coherence" / "schemas" / "attestation.schema.json":
        "553812d39fa521bf322d3fbdfc85b9a1b75d6e5375600bcdae20828a393844b6",
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
        cls.keyring = [{
            "key_id": cls.key_id,
            "public_key": cls.public.hex(),
            "audience": "oap-observer",
            "valid_from": "2026-10-01T00:00:00Z",
            "valid_until": "2026-11-01T00:00:00Z",
            "revoked": False,
        }]
        cls.reference_time = "2026-10-04T12:30:00Z"

    def _verify(self, envelope=None, signature=None, keyring=None, **kwargs):
        kwargs.setdefault("reference_time", self.reference_time)
        return oap_evidence.verify_envelope(
            envelope if envelope is not None else self.envelope,
            signature if signature is not None else self.signature,
            keyring if keyring is not None else self.keyring, **kwargs)

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
        self.assertEqual(reason, "signature-mismatch")

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
        revoked = [dict(self.keyring[0], revoked=True)]
        ok, reason = self._verify(keyring=revoked)
        self.assertFalse(ok)
        self.assertEqual(reason, f"revoked-key:{self.key_id}")

    def test_audience_mismatch_fails(self):
        ok, reason = self._verify(audience="some-other-oap")
        self.assertFalse(ok)
        self.assertEqual(reason, "audience-mismatch:oap-observer")

    def test_key_provisioned_for_other_audience_fails(self):
        other_audience = [dict(self.keyring[0], audience="different-audience")]
        ok, reason = self._verify(keyring=other_audience)
        self.assertFalse(ok)
        self.assertEqual(reason, "key-audience-mismatch:different-audience")

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
        mismatched = [dict(self.keyring[0],
                           public_key=ed25519.public_key(_seed(0x44)).hex())]
        ok, reason = self._verify(keyring=mismatched)
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
        "payload_digest": "sha256:" + hashlib.sha256(PAYLOAD).hexdigest(),
        "evidence_refs": [
            {"name": "result.json", "digest": "sha256:" + "aa" * 32,
             "purpose": "canonical-result"},
        ],
    }


if __name__ == "__main__":
    unittest.main()
