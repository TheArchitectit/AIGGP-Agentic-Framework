# // spec: coh-id-01
"""Golden-vector conformance: the REAL hub.coherence.canon must reproduce the
frozen vectors byte-for-byte (coh-id-01's compatibility contract).

Audit finding F13: `vectors.json` was consumed by nothing and its generator
re-implemented canon locally — a serialization change in canon.py would have
passed green while silently breaking the compatibility contract. Now:
- this test fails if canon's output drifts from the frozen vectors;
- the generator (compute_golden.py) imports the real module, so regeneration
  exercises the real code path and its independence is the cross-check.
"""
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from hub.coherence import canon  # noqa: E402

VECTORS = json.loads(
    (REPO / "tests/fixtures/coherence/vectors.json").read_text())
FIXTURES = REPO / "tests/fixtures/coherence"


class TestGoldenVectors(unittest.TestCase):
    def setUp(self):
        self.v = VECTORS["vectors"]

    def test_raw_byte_digests(self):
        lf = (FIXTURES / "hello_lf.txt").read_bytes()
        crlf = (FIXTURES / "hello_crlf.txt").read_bytes()
        self.assertEqual(canon.digest("file/v1", lf), self.v["hello_lf_raw"])
        self.assertEqual(canon.digest("file/v1", crlf), self.v["hello_crlf_raw"])
        # LF vs CRLF are DIFFERENT content — raw-byte hashing must not fold them.
        self.assertEqual(lf == crlf, self.v["hello_lf_eq_crlf"])

    def test_canonical_bytes_and_digest(self):
        obj = json.loads((FIXTURES / "canonical_sample.json").read_text())
        self.assertEqual(canon.canon(obj).decode("utf-8"),
                         self.v["canonical_sample_bytes"])
        self.assertEqual(canon.digest("decision/v1", canon.canon(obj)),
                         self.v["canonical_sample_digest"])

    def test_domain_separation(self):
        lf = (FIXTURES / "hello_lf.txt").read_bytes()
        self.assertEqual(canon.digest("file/v1", lf), self.v["role_file"])
        self.assertEqual(canon.digest("subject-manifest/v1", lf),
                         self.v["role_subject"])
        self.assertTrue(self.v["roles_differ"])

    def test_canon_rejects_profile_violations(self):
        # The frozen profile rejects floats and non-int64 integers outright.
        with self.assertRaises(canon.CanonError):
            canon.canon({"x": 1.5})
        with self.assertRaises(canon.CanonError):
            canon.canon({"x": 2 ** 63})
        with self.assertRaises(canon.CanonError):
            canon.digest("not-a-role/v1", b"")


class TestSuiteFloor(unittest.TestCase):
    """Meta-test (fw-ci-01): collection must never silently shrink. F12 let a
    foreign `tests` package drop five conformance files while 239 other tests
    still passed and everyone saw green. Bump FLOOR deliberately when test
    files are added; a drop below the floor means test files stopped being
    collected."""

    def test_discovered_test_file_count_at_least_floor(self):
        discovered = sorted(p.name for p in (REPO / "tests").glob("test_*.py"))
        floor = 30
        self.assertGreaterEqual(
            len(discovered), floor,
            f"test collection shrank: {len(discovered)} files discovered "
            f"({', '.join(discovered)}). If you removed or renamed tests, "
            f"lower the FLOOR in {__file__} DELIBERATELY; if not, find what "
            f"stopped them being collected.")


if __name__ == "__main__":
    unittest.main()
