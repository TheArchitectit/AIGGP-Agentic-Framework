"""Conformance checks for the proposed, observe-only OAP evidence envelope."""
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHANGE = REPO / "openspec" / "changes" / "add-oap-evidence-consumer"
SCHEMA_PATH = CHANGE / "schemas" / "oap-evidence-envelope.schema.json"
FIXTURES = CHANGE / "fixtures"
sys.path.insert(0, str(REPO))

from hub.coherence import schemacheck


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


if __name__ == "__main__":
    unittest.main()
