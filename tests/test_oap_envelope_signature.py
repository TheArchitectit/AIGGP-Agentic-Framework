"""Envelope-level conformance for the OAP evidence detached signature.

Split out of tests/test_oap_evidence_signature.py: that file pins the
Ed25519 primitive and the strict point/forgery profile, this one pins the
envelope half — canonical bytes, sign/verify binding, caller-keyring
refusal, the bounded public surface, and the frozen schema bytes. Both
halves are collected by pytest; the primitive half is what the OAP
mutation battery names by path.
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
