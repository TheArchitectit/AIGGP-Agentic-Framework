# // spec: coh-oap-01, coh-oap-07, coh-oap-hard-04
"""Freeze-pin the cross-language `devgate.oap-evidence/v2` reference vectors.

These vectors are produced by the EXISTING Python producer/verifier. The test
REGENERATES them from the current code and asserts byte-identity to the
committed file, plus a SHA-256 pin, so any silent drift in
`oap_v2_producer` / `strict_parse` / `trust_store` / `replay_guard` /
`oap_observer` fails CI. It never writes the committed file — drift must be a
deliberate, reviewed regeneration.

Honesty (see vectors/README.md): the vectors are Python-produced reference
material. No independent Go OAP receiver exists yet, so consumption of these
vectors by a Go implementation is NOT_EXERCISED. Every verdict is
NON-AUTHORIZING and observe-only.
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.fixtures.oap.oap_vectors import build_vectors, dumps  # noqa: E402
from hub.coherence import ed25519_vetted  # noqa: E402

VECTORS = (REPO / "openspec" / "changes" / "add-oap-evidence-consumer"
           / "vectors" / "oap-evidence-v2-vectors.json")

# Deliberate freeze pin. Update only as part of a reviewed regeneration.
FROZEN_VECTORS_SHA256 = \
    "8f3cec8f6d62c02cc15e0299db238af60ff41e6b96c08cd8fe3b1bbdb86197d7"

REQUIRED_CASES = frozenset({
    "valid_artifact",
    "identity_low_order_key_forgery",
    "duplicate_json_key",
    "wrong_domain_separation_tag",
    "expired_timestamp",
    "not_yet_valid_timestamp",
    "replayed_jti",
    "wrong_audience",
    "wrong_tenant",
    "lying_digest",
    "lying_cross_link",
})


class TestOapEvidenceVectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ed25519_vetted.AVAILABLE:
            raise unittest.SkipTest(
                "NOT_RUN: vetted Ed25519 provider unavailable; cannot "
                "regenerate reference vectors")
        cls.committed = VECTORS.read_bytes()

    def test_committed_file_matches_sha256_pin(self):
        self.assertEqual(
            hashlib.sha256(self.committed).hexdigest(),
            FROZEN_VECTORS_SHA256,
            "the committed vectors file drifted from its frozen SHA-256 pin; "
            "regenerate deliberately and re-review before updating the pin")

    def test_regenerated_vectors_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            regenerated = dumps(build_vectors(Path(tmp)))
        self.assertEqual(
            regenerated, self.committed,
            "the current code no longer reproduces the committed vectors; a "
            "silent change in the producer/parser/trust/observer path would "
            "break the cross-language contract")

    def test_vectors_carry_required_cases_and_non_authorizing_marker(self):
        doc = json.loads(self.committed)
        names = {case["name"] for case in doc["cases"]}
        self.assertEqual(doc["case_count"], len(doc["cases"]))
        self.assertTrue(
            REQUIRED_CASES <= names,
            f"missing adversarial cases: {sorted(REQUIRED_CASES - names)}")
        self.assertIs(doc["status"]["non_authorizing"], True)
        self.assertEqual(doc["status"]["go_receiver"], "NOT_EXERCISED")
        for case in doc["cases"]:
            self.assertIn("expected", case)
            self.assertTrue(case["canonical_bytes_hex"])


if __name__ == "__main__":
    unittest.main()
