# // spec: coh-ev-04
"""Authorized input retention (coh-ev-04): where reproduction needs the exact
subject bytes, the immutable input bundle is preserved on a channel SEPARATE
from public evidence, retrievable only under an authorization distinct from
evidence-read access, and expiry (evaluated against a trusted time, never the
host clock) invalidates cache reuse for the affected identities.

Public evidence proves a finding with digests + minimum-disclosure excerpts and
needs no retrieval secret to read. This channel holds the raw input bytes, so
it is gated by its own HMAC-capability token (a control-plane secret the
evidence reader does not hold) and its own lifetime. All fixtures synthetic
(R9); time is always an explicit `as_of`, never datetime.now().
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import retention

FIXED = "2026-09-17T00:00:00Z"
KEY = "1" * 64
OTHER_KEY = "2" * 64


def _key_env(val):
    """Patch the retention key env for a single test (the HUB_COHERENCE_*
    pattern issue.py / attest.py establish — the module reads its secret
    through the same environment contract as its signing siblings)."""
    os.environ["HUB_COHERENCE_RETENTION_KEY"] = val


class RetentionTestCase(unittest.TestCase):
    def setUp(self):
        _key_env(KEY)
        self.addCleanup(os.environ.pop, "HUB_COHERENCE_RETENTION_KEY", None)

    def test_retained_bundle_lives_outside_the_public_evidence_channel(self):
        """coh-ev-04: retained inputs are stored SEPARATELY from public
        evidence. A retained write under a store root must not create or touch
        a sibling `evidence/` tree — the two channels have different
        confidentiality and different readers."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "retention-store"
            ref = retention.retain(root, "sha256:" + "a" * 64,
                                   b"# product: widget\n",
                                   retained_at=FIXED, retention_days=30)
            self.assertFalse((Path(td) / "evidence").exists(),
                             "the retention write must not touch public evidence")
            self.assertTrue((root / "bundles").is_dir(),
                            "retention has its own storage area")
            token = retention.issue(ref)
            self.assertEqual(retention.read(root, ref, as_of=FIXED,
                                            authorization=token),
                             b"# product: widget\n")


class TestDistinctAuthorization(RetentionTestCase):
    def test_no_authorization_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "retention-store"
            ref = retention.retain(root, "sha256:" + "b" * 64, b"x",
                                   retained_at=FIXED, retention_days=30)
            with self.assertRaises(retention.RetentionError) as cm:
                retention.read(root, ref, as_of=FIXED, authorization=None)
            self.assertIn("retention-unauthorized", str(cm.exception))

    def test_authorization_for_another_bundle_is_refused(self):
        """A token bound to ref-2 must not unlock ref-1: capabilities are
        per-bundle, not a global 'reader' role."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "retention-store"
            ref1 = retention.retain(root, "sha256:" + "1" * 64, b"x",
                                    retained_at=FIXED, retention_days=30)
            ref2 = retention.retain(root, "sha256:" + "2" * 64, b"y",
                                    retained_at=FIXED, retention_days=30)
            wrong = retention.issue(ref2)
            with self.assertRaises(retention.RetentionError) as cm:
                retention.read(root, ref1, as_of=FIXED, authorization=wrong)
            self.assertIn("retention-unauthorized", str(cm.exception))
            # Same key, correct token: succeeds. Proves the refusal above was
            # the binding, not the key or the read path.
            self.assertEqual(retention.read(root, ref1, as_of=FIXED,
                                            authorization=retention.issue(ref1)),
                             b"x")

    def test_a_capability_under_a_different_key_is_refused(self):
        """The authorization is the control-plane RETENTION secret; a caller
        who does not hold it (evidence-read-only) cannot forge a token even
        knowing the ref."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "retention-store"
            ref = retention.retain(root, "sha256:" + "d" * 64, b"x",
                                   retained_at=FIXED, retention_days=30)
            _key_env(OTHER_KEY)
            try:
                forged = retention.issue(ref)   # now derived from OTHER_KEY
            finally:
                _key_env(KEY)
            with self.assertRaises(retention.RetentionError) as cm:
                retention.read(root, ref, as_of=FIXED, authorization=forged)
            self.assertIn("retention-unauthorized", str(cm.exception))


class TestExpiry(RetentionTestCase):
    def test_expired_retention_fails_closed_with_a_distinct_reason(self):
        """'retention expiry MUST invalidate cached-result reuse': past the
        window, retrieval fails with a reason the cache layer can act on
        (distinct from unauthorized, so the operator sees what changed)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "retention-store"
            ref = retention.retain(root, "sha256:" + "e" * 64, b"secret-input",
                                   retained_at=FIXED, retention_days=30)
            token = retention.issue(ref)
            # Day 14: still inside the window.
            self.assertEqual(retention.read(root, ref, as_of="2026-10-01T00:00:00Z",
                                            authorization=token),
                             b"secret-input")
            # Day 31: expired.
            with self.assertRaises(retention.RetentionError) as cm:
                retention.read(root, ref, as_of="2026-10-18T00:00:00Z",
                               authorization=token)
            self.assertIn("retention-expired", str(cm.exception))

    def test_expiry_is_evaluated_against_as_of_not_the_host_clock(self):
        """If the check used the host clock this test would be a time bomb and
        the module would fail design.md:R2 — an `as_of` inside the window must
        always succeed, regardless of when the test suite runs."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "retention-store"
            ref = retention.retain(root, "sha256:" + "f" * 64, b"y",
                                   retained_at=FIXED, retention_days=30)
            token = retention.issue(ref)
            # This `as_of` is inside the window. It cannot be expired by the
            # host clock, because the module must not consult it.
            self.assertEqual(
                retention.read(root, ref, as_of="2026-09-20T00:00:00Z",
                               authorization=token), b"y")

    def test_zero_day_retention_expires_at_the_boundary(self):
        """retention_days=0 is legal per assertion.schema.json (minimum 0);
        the bundle is retained only for the retention instant itself."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "retention-store"
            ref = retention.retain(root, "sha256:" + "0" * 64, b"z",
                                   retained_at=FIXED, retention_days=0)
            token = retention.issue(ref)
            # Same instant is inside the window; one second later is out.
            self.assertEqual(retention.read(root, ref, as_of=FIXED,
                                            authorization=token), b"z")
            with self.assertRaises(retention.RetentionError) as cm:
                retention.read(root, ref, as_of="2026-09-17T00:00:01Z",
                               authorization=token)
            self.assertIn("retention-expired", str(cm.exception))

    def test_malformed_as_of_is_rejected_not_silently_ignored(self):
        """An unparseable time cannot be an expiry check that 'passes' by
        default — fail closed with a specific reason."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "retention-store"
            ref = retention.retain(root, "sha256:" + "1" * 64, b"q",
                                   retained_at=FIXED, retention_days=30)
            token = retention.issue(ref)
            with self.assertRaises(retention.RetentionError) as cm:
                retention.read(root, ref, as_of="not-a-timestamp",
                               authorization=token)
            self.assertIn("retention-bad-time", str(cm.exception))


class TestContentIntegrity(RetentionTestCase):
    def test_read_refuses_a_bundle_that_no_longer_matches_its_digest(self):
        """A retained bundle is only useful if it IS the input it claims:
        digest mismatch on read fails closed (the store may have been edited
        or corrupted), even when the token and window are valid."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "retention-store"
            ref = retention.retain(root, "sha256:" + "2" * 64, b"original",
                                   retained_at=FIXED, retention_days=30)
            token = retention.issue(ref)
            # Corrupt the bytes on disk.
            blobs = list((root / "bundles").glob("*"))
            self.assertEqual(len(blobs), 1)
            blobs[0].write_bytes(b"tampered")
            with self.assertRaises(retention.RetentionError) as cm:
                retention.read(root, ref, as_of=FIXED, authorization=token)
            self.assertIn("retention-tampered", str(cm.exception))

    def test_a_ref_that_is_not_a_bundle_digest_is_rejected_before_touching_disk(self):
        """The read path interpolates `ref` into the bundle/record file names.
        A caller-supplied traversal ref would be caught downstream by the
        content-digest check — but the same round-9 principle applies: a
        path-shaped input must be rejected at the boundary, not saved by an
        implicit invariant elsewhere, or the failure mode drifts into a
        filesystem-existence oracle as the file layout evolves.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "retention-store"
            token = retention.issue("sha256:" + "a" * 64)  # any token will do
            for bad in ("../../etc/shadow", "not-a-digest", "", None,
                        "sha256:xyz", "sha256:" + "a" * 63,
                        "sha256:" + "g" * 64):
                with self.subTest(ref=bad):
                    with self.assertRaises(retention.RetentionError) as cm:
                        retention.read(root, bad, as_of=FIXED,
                                       authorization=token)
                    self.assertIn("retention-bad-ref", str(cm.exception))

    def test_retain_is_idempotent_for_identical_bytes(self):
        """Re-retaining the same input is a no-op: the digest is the bundle
        identity, so no duplicate blob or new record is created."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "retention-store"
            r1 = retention.retain(root, "sha256:" + "3" * 64, b"same",
                                  retained_at=FIXED, retention_days=30)
            r2 = retention.retain(root, "sha256:" + "3" * 64, b"same",
                                  retained_at=FIXED, retention_days=30)
            self.assertEqual(r1, r2)
            blobs = list((root / "bundles").glob("*"))
            self.assertEqual(len(blobs), 1, "no duplicate blob per digest")


if __name__ == "__main__":
    unittest.main()
