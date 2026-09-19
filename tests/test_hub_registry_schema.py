# // spec: mon-registry-01, mon-sec-02
"""The shipped registry schema must describe what the hub actually writes.

Audit-found drift: the hardening change moved heartbeat tokens from plaintext
(`heartbeat_token`) to salted hashes (`heartbeat_token_hash` + top-level
`token_salt`), but `hub/schema/runners.schema.json` still REQUIRED the old
field and — with `additionalProperties: false` — rejected the new one. The
redacted example is the public documentation of the registry shape; letting it
drift silently makes the schema worse than none.

These tests validate a REAL saved registry (produced by Registry.save) and the
shipped example against the shipped schema via the coherence schemacheck.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from hub.registry import Registry  # noqa: E402
from hub.coherence import schemacheck  # noqa: E402

SCHEMA_PATH = REPO / "hub" / "schema" / "runners.schema.json"
EXAMPLE_PATH = REPO / "hub" / "schema" / "runners.example.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


class TestRegistrySchemaMatchesCode(unittest.TestCase):
    def test_real_saved_registry_validates(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "runners.json"
            reg = Registry(str(path))
            reg.add_enrollment_token("tok")
            reg.enroll("r1", "OWNER/REPO", ["devgate"], "host")
            reg.save()
            doc = json.loads(path.read_text())
        errs = schemacheck.validate(doc, _schema())
        self.assertEqual(errs, [], f"saved registry violates its schema: {errs}")

    def test_revoked_registry_validates(self):
        """Revocation nulls the verifier — the schema must allow that shape."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "runners.json"
            reg = Registry(str(path))
            reg.enroll("r1", "OWNER/REPO", [], "")
            reg.revoke("r1")
            reg.save()
            doc = json.loads(path.read_text())
        errs = schemacheck.validate(doc, _schema())
        self.assertEqual(errs, [], f"revoked registry violates schema: {errs}")

    def test_schema_rejects_plaintext_token_field(self):
        """The schema must NOT accept a plaintext heartbeat_token — that is
        the at-rest property mon-sec-02 guarantees."""
        doc = {
            "version": 1, "enrollment_tokens": [],
            "runners": [{
                "name": "r1", "repo": "O/R", "enrolled_at": "2026-09-19T00:00:00Z",
                "heartbeat_token": "plaintext-secret",
            }],
        }
        errs = schemacheck.validate(doc, _schema())
        self.assertTrue(errs, "plaintext heartbeat_token must violate the schema")

    def test_shipped_example_validates(self):
        # `_comment` is human-facing documentation metadata; the live registry
        # never writes it, so it is not in the schema. The example's DATA must
        # satisfy the schema.
        example = json.loads(EXAMPLE_PATH.read_text())
        example.pop("_comment", None)
        errs = schemacheck.validate(example, _schema())
        self.assertEqual(errs, [], f"shipped example violates its schema: {errs}")


if __name__ == "__main__":
    unittest.main()
