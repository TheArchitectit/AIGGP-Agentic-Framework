"""Conformance checks for the proposed, observe-only OAP evidence envelope."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHANGE = REPO / "openspec" / "changes" / "add-oap-evidence-consumer"
SCHEMA_PATH = CHANGE / "schemas" / "oap-evidence-envelope.schema.json"
FIXTURES = CHANGE / "fixtures"
sys.path.insert(0, str(REPO))

from hub.coherence import canon, ed25519, oap_evidence, schemacheck, strict_parse
from hub.coherence.trust_store import TrustStore, digest_of

# Real evidence bytes the v2 fixtures' digests commit to (Gate 2.3).
FIXTURE_PAYLOAD = b'{"decision":"PASS","subject":"fixture-subject"}'
FIXTURE_RESULT = b'{"decision":"PASS","exit_code":0}'
FIXTURE_MANIFEST = b'{"refs":["result.json"]}'
FIXTURE_ATTESTATION = b"detached-attestation-bytes"


class TestOapEvidenceEnvelope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def _fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def test_schema_uses_only_enforced_constraint_vocabulary(self):
        unsupported = set()

        def walk(node):
            if isinstance(node, dict):
                unsupported.update(k for k in node if k in {
                    "maxLength", "maxItems", "minLength", "minItems",
                    "minimum", "pattern", "type", "required", "enum",
                    "const", "additionalProperties", "properties", "items",
                    "$ref", "format", "definitions", "title", "description",
                    "$schema", "$id",
                } and k not in schemacheck.SUPPORTED)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(self.schema)
        self.assertEqual(unsupported, set())

    def test_valid_fixture_passes_schema(self):
        fixture = self._fixture("valid-pass-envelope.json")
        self.assertEqual(schemacheck.validate(fixture, self.schema), [])
        self.assertTrue(fixture["observe_only"])
        self.assertEqual(fixture["operation_scope"]["effect_authority"], "none")

    def test_unknown_critical_fixture_fails_schema(self):
        fixture = self._fixture("invalid-unknown-critical-field.json")
        self.assertTrue(schemacheck.validate(fixture, self.schema))

    def test_status_laundering_fixture_fails_conformance(self):
        fixture = self._fixture("invalid-status-laundering.json")
        self.assertEqual(schemacheck.validate(fixture, self.schema), [])

        def conforms(doc):
            non_pass = {"ERROR", "SKIP", "UNKNOWN", "INCONCLUSIVE", "ADVISORY", "FAIL"}
            return not (doc["native_status"] in non_pass
                        and doc["devgate"]["decision"] == "PASS")

        self.assertIn(fixture["native_status"], {
            "ERROR", "SKIP", "UNKNOWN", "INCONCLUSIVE", "ADVISORY", "FAIL",
        })
        self.assertEqual(fixture["devgate"]["decision"], "PASS")
        self.assertFalse(conforms(fixture),
                         "non-PASS native status must not be represented as DevGate PASS")

    def test_maximum_string_and_array_bounds_are_enforced(self):
        fixture = self._fixture("valid-pass-envelope.json")
        fixture["native_reason"] = "x" * 513
        fixture["evidence_refs"].extend(fixture["evidence_refs"] * 5 +
                                        fixture["evidence_refs"][:1])
        errors = schemacheck.validate(fixture, self.schema)
        self.assertTrue(any("above maxLength" in error for error in errors), errors)
        self.assertTrue(any("above maxItems" in error for error in errors), errors)


CHANGE_V2 = REPO / "openspec" / "changes" / "harden-oap-evidence-verification"
SCHEMA_V2_PATH = CHANGE_V2 / "schemas" / "oap-evidence-envelope-v2.schema.json"
FIXTURES_V2 = CHANGE_V2 / "fixtures"
SIGNER_SEED = bytes([0x11]) * ed25519.SEED_SIZE


class TestOapEvidenceEnvelopeV2(unittest.TestCase):
    """Gate 1.3/1.4: v2 wire shape, strict parser and the v2 fixture corpus.

    Every negative fixture is exercised through `hub.coherence.strict_parse`
    (the raw-bytes boundary) and, where it is structurally valid JSON, through
    `hub.coherence.schemacheck` against the v2 schema — demonstrating that the
    schema alone is necessary but not sufficient (status/exit laundering and
    expiry pass the schema and must still be denied by the parser/receiver).
    """

    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_V2_PATH.read_text(encoding="utf-8"))
        cls.public = ed25519.public_key(SIGNER_SEED)
        cls.key_id = strict_parse.key_id_for(cls.public)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.trust_path = Path(cls.tmp.name) / "trust.json"
        cls.trust_path.write_text(json.dumps({
            "snapshot_time": "2026-10-04T12:00:00Z",
            "entries": [{
                "producer_id": "devgate-instance-1",
                "key_id": cls.key_id,
                "public_key": cls.public.hex(),
                "audience": "oap-observer",
                "direction": "devgate-to-oap",
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_until": "2027-01-01T00:00:00Z",
                "revoked": False,
                "revocation_version": 1,
            }],
        }, separators=(",", ":")), encoding="utf-8")
        cls.trust = TrustStore.load(cls.trust_path)
        cls.reference_time = "2026-10-04T12:01:00Z"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _raw(self, name):
        return (FIXTURES_V2 / name).read_bytes()

    def _doc(self, name):
        return json.loads(self._raw(name).decode("utf-8"))

    def _evidence(self, **overrides):
        supplied = {
            "payload": FIXTURE_PAYLOAD,
            "result": FIXTURE_RESULT,
            "evidence_manifest": FIXTURE_MANIFEST,
            "attestation": FIXTURE_ATTESTATION,
        }
        supplied.update(overrides)
        return supplied

    # -- schema hygiene ----------------------------------------------------
    def test_schema_uses_only_enforced_constraint_vocabulary(self):
        unsupported = set()

        def walk(node):
            if isinstance(node, dict):
                unsupported.update(k for k in node if k in {
                    "maxLength", "maxItems", "minLength", "minItems",
                    "minimum", "pattern", "type", "required", "enum",
                    "const", "additionalProperties", "properties", "items",
                    "$ref", "format", "definitions", "title", "description",
                    "$schema", "$id",
                } and k not in schemacheck.SUPPORTED)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(self.schema)
        self.assertEqual(unsupported, set())
        self.assertEqual(set(self.schema["required"]), {"body", "signature"})

    # -- positive ----------------------------------------------------------
    def test_valid_fixture_parses_canonically_and_passes_schema(self):
        raw = self._raw("valid-v2-envelope.json")
        envelope = strict_parse.parse_envelope(raw)
        self.assertEqual(schemacheck.validate(envelope, self.schema), [])
        body = envelope["body"]
        self.assertEqual(body["contract_version"], "devgate.oap-evidence/v2")
        self.assertEqual(body["direction"], "devgate-to-oap")
        self.assertIs(body["observe_only"], True)
        # The wire object itself is canonical bytes and the key id is 64-hex.
        self.assertEqual(canon.canon(envelope), raw)
        self.assertEqual(envelope["signature"]["key_id"], self.key_id)
        self.assertEqual(len(envelope["signature"]["value"]), len("ed25519:") + 128)

    def test_valid_fixture_verifies_signature_and_shape(self):
        ok, reason = strict_parse.verify_wire_envelope(
            self._raw("valid-v2-envelope.json"), self.trust,
            reference_time=self.reference_time, **self._evidence())
        self.assertTrue(ok, reason)
        self.assertIsNone(reason)

    def test_payload_digest_binding_rejects_unrelated_bytes(self):
        ok, reason = strict_parse.verify_wire_envelope(
            self._raw("valid-v2-envelope.json"), self.trust,
            reference_time=self.reference_time,
            **self._evidence(payload=b"not the payload"))
        self.assertFalse(ok)
        self.assertEqual(reason, "payload-digest-mismatch")

    def test_verify_envelope_routes_raw_bytes_through_strict_parse(self):
        # Integration: the verification path accepts raw v2 bytes.
        ok, reason = oap_evidence.verify_envelope(
            self._raw("valid-v2-envelope.json"), None, self.trust,
            reference_time=self.reference_time, **self._evidence())
        self.assertTrue(ok, reason)
        # ...and a duplicate-key artifact is rejected before any crypto runs.
        ok, reason = oap_evidence.verify_envelope(
            self._raw("invalid-duplicate-key-top.json"), None, self.trust)
        self.assertFalse(ok)
        self.assertEqual(reason, "duplicate-key:body")

    def test_caller_supplied_keyring_rejected_on_wire_path(self):
        ok, reason = strict_parse.verify_wire_envelope(
            self._raw("valid-v2-envelope.json"), self._doc(
                "valid-v2-envelope.json")["signature"]["key_id"] and [
                    {"key_id": self.key_id,
                     "public_key": self.public.hex()}],
            reference_time=self.reference_time, **self._evidence())
        self.assertFalse(ok)
        self.assertEqual(reason, "caller-supplied-keyring-rejected")

    # -- strict-parse negatives -------------------------------------------
    def _assert_parse_reason(self, name, reason):
        with self.assertRaises(strict_parse.StrictParseError) as ctx:
            strict_parse.parse_envelope(self._raw(name))
        self.assertEqual(str(ctx.exception), reason)

    def test_duplicate_keys_rejected_at_every_depth(self):
        self._assert_parse_reason(
            "invalid-duplicate-key-top.json", "duplicate-key:body")
        self._assert_parse_reason(
            "invalid-duplicate-key-nested.json", "duplicate-key:native_reason")

    def test_noncanonical_json_rejected(self):
        self._assert_parse_reason("invalid-noncanonical.json", "noncanonical-json")

    def test_oversized_payload_rejected(self):
        raw = self._raw("invalid-oversized.json")
        self.assertGreater(len(raw), strict_parse.MAX_BYTES)
        with self.assertRaises(strict_parse.StrictParseError) as ctx:
            strict_parse.parse_envelope(raw)
        self.assertTrue(str(ctx.exception).startswith("too-large"), ctx.exception)

    def test_wrong_version_rejected(self):
        self._assert_parse_reason(
            "invalid-wrong-version.json",
            "unsupported-contract-version:'devgate.oap-evidence/v1'")

    def test_wrong_direction_rejected(self):
        self._assert_parse_reason(
            "invalid-wrong-direction.json",
            "unsupported-direction:'oap-to-devgate'")

    def test_missing_required_field_rejected(self):
        self._assert_parse_reason(
            "invalid-missing-required-field.json",
            "missing-required-field:payload_digest")

    def test_status_exit_mismatch_rejected(self):
        self._assert_parse_reason(
            "invalid-status-exit-mismatch.json",
            "status-exit-mismatch:PASS/ERROR")

    def test_truncated_v1_key_id_rejected(self):
        fixture = self._doc("valid-v2-envelope.json")
        # A v1-style 32-hex key id is not v2-compatible.
        fixture["signature"]["key_id"] = "ed25519:" + "ab" * 16
        self.assertTrue(schemacheck.validate(fixture, self.schema))
        with self.assertRaises(strict_parse.StrictParseError) as ctx:
            strict_parse.parse_envelope(canon.canon(fixture))
        self.assertEqual(str(ctx.exception), "invalid-key-id")

    # -- schema-necessary-not-sufficient ----------------------------------
    def test_status_laundering_passes_schema_but_parser_denies(self):
        fixture = self._doc("invalid-status-exit-mismatch.json")
        # Each field is individually in-range, so the schema accepts it...
        self.assertEqual(schemacheck.validate(fixture, self.schema), [])
        # ...yet the semantic relation PASS/0 vs ERROR must be rejected.
        self.assertEqual(fixture["body"]["native_decision"], "PASS")
        self.assertEqual(fixture["body"]["native_exit_code"], 0)
        self.assertEqual(fixture["body"]["native_status"], "ERROR")
        with self.assertRaises(strict_parse.StrictParseError):
            strict_parse.parse_envelope(self._raw("invalid-status-exit-mismatch.json"))

    def test_schema_rejects_wrong_version_missing_field_and_direction(self):
        for name in ("invalid-wrong-version.json",
                     "invalid-missing-required-field.json",
                     "invalid-wrong-direction.json"):
            with self.subTest(fixture=name):
                self.assertTrue(
                    schemacheck.validate(self._doc(name), self.schema))

    def test_expired_envelope_denies_at_receiver_time(self):
        raw = self._raw("invalid-expired-envelope.json")
        # Shape is valid, so the strict parser accepts it...
        strict_parse.parse_envelope(raw)
        # ...but the receiver's authenticated time is past expiry.
        ok, reason = strict_parse.verify_wire_envelope(
            raw, self.trust, reference_time="2026-10-04T12:00:00Z",
            **self._evidence())
        self.assertFalse(ok)
        self.assertEqual(reason, "envelope-expired")


if __name__ == "__main__":
    unittest.main()