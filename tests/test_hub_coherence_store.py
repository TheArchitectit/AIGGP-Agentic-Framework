# // spec: coh-ev-02, coh-ev-04, coh-ctx-05
"""S5 remainder: the immutable evidence store, retryable/resumable upload,
the TOTAL decision-cache key, and TTL/retention invalidation.

The failure-injection half is the point: tampering at rest, partial
uploads, stale cache entries, and revoked signers must each produce the
documented refusal — a store or cache that quietly accepts these is the
false-verification channel the whole design exists to close.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import canon, evidence, store
from hub.coherence.resource_limits import BudgetExceeded


def _seal_bundle(td: Path, assertion_id="a1"):
    findings = [{
        "assertion_id": assertion_id,
        "finding_key": f"{assertion_id}|x|identity-mismatch",
        "outcome": "VIOLATED", "enforcement": "BLOCK", "severity": "high",
        "subject_locations": ["README.md"], "expected": "widget",
        "observed": "other", "evidence_refs": [],
    }]
    return evidence.seal(findings, str(td))


class TestLocalBundleStore(unittest.TestCase):
    def test_put_then_get_round_trips(self):
        with tempfile.TemporaryDirectory() as td:
            s = store.LocalBundleStore(td)
            d = s.put("file/v1", b"payload-bytes")
            self.assertEqual(s.get(d), b"payload-bytes")

    def test_put_same_content_is_idempotent_noop(self):
        with tempfile.TemporaryDirectory() as td:
            s = store.LocalBundleStore(td)
            d1 = s.put("file/v1", b"same")
            d2 = s.put("file/v1", b"same")
            self.assertEqual(d1, d2)

    def test_digest_collision_with_different_content_is_hard_error(self):
        """The store never overwrites, never silently ignores a collision:
        same address + different bytes must stop the world."""
        with tempfile.TemporaryDirectory() as td:
            s = store.LocalBundleStore(td)
            d = s.put("file/v1", b"original")
            # Forge a different payload at the same content address.
            obj = s._path_for(d)
            obj.write_bytes(b"tampered-at-rest")
            with self.assertRaises(store.StoreError) as c:
                s.put("file/v1", b"original")
            self.assertIn("collision", str(c.exception))

    def test_tamper_at_rest_detected_on_read(self):
        with tempfile.TemporaryDirectory() as td:
            s = store.LocalBundleStore(td)
            d = s.put("file/v1", b"honest")
            obj = s._path_for(d)
            obj.write_bytes(b"swapped")
            with self.assertRaises(store.StoreError) as c:
                s.get(d)
            self.assertIn("tampered at rest", str(c.exception))

    def test_malformed_digest_rejected(self):
        s = store.LocalBundleStore("/tmp/unused")
        with self.assertRaises(store.StoreError):
            s.has("not-a-digest")

    def test_role_separation_same_bytes_different_objects(self):
        with tempfile.TemporaryDirectory() as td:
            s = store.LocalBundleStore(td)
            d1 = s.put("file/v1", b"x")
            d2 = s.put("policy/v1", b"x")
            self.assertNotEqual(d1, d2)
            self.assertEqual(s.get(d1), b"x")
            self.assertEqual(s.get(d2), b"x")


class TestUploadBundle(unittest.TestCase):
    def test_upload_round_trip_and_manifest_last(self):
        with tempfile.TemporaryDirectory() as td, \
                tempfile.TemporaryDirectory() as sd:
            bundle = Path(td)
            _seal_bundle(bundle)
            s = store.LocalBundleStore(sd)
            out = store.upload_bundle(s, str(bundle))
            self.assertEqual(out["failed"], [])
            # One finding object + the manifest = two stored objects.
            self.assertEqual(len(out["uploaded"]), 2)
            self.assertEqual(len(out["already_present"]), 0)
            # Every manifest object is retrievable from the store.
            manifest = json.loads((bundle / "evidence-manifest.json").read_text())
            for obj in manifest["objects"]:
                payload = s.get(obj["digest"])
                self.assertEqual(
                    canon.digest_bytes("evidence-manifest/v1", payload),
                    obj["digest"])

    def test_retried_upload_resumes_partial(self):
        """A partial upload (crash between objects) is COMPLETED by a retry:
        existing objects are verified skips, the rest uploads — never
        duplicated, never faked."""
        with tempfile.TemporaryDirectory() as td, \
                tempfile.TemporaryDirectory() as sd:
            bundle = Path(td)
            _seal_bundle(bundle)
            s = store.LocalBundleStore(sd)
            manifest = json.loads(
                (bundle / "evidence-manifest.json").read_text())
            # Simulate a partial upload: only the FIRST object landed.
            first = manifest["objects"][0]
            payload = (bundle / first["path"]).read_bytes()
            s.put("evidence-manifest/v1", payload)
            out = store.upload_bundle(s, str(bundle))
            self.assertEqual(out["failed"], [])
            self.assertEqual(len(out["already_present"]), 1)
            # Both objects plus the manifest are now present exactly once.
            self.assertTrue(s.has(first["digest"]))
            for obj in manifest["objects"]:
                self.assertTrue(s.has(obj["digest"]))

    def test_tampered_object_since_seal_is_refused(self):
        with tempfile.TemporaryDirectory() as td, \
                tempfile.TemporaryDirectory() as sd:
            bundle = Path(td)
            _seal_bundle(bundle)
            manifest = json.loads(
                (bundle / "evidence-manifest.json").read_text())
            # Tamper a sealed object AFTER sealing.
            obj_path = bundle / manifest["objects"][0]["path"]
            obj_path.write_bytes(b'{"forged": true}')
            s = store.LocalBundleStore(sd)
            out = store.upload_bundle(s, str(bundle))
            self.assertEqual(len(out["failed"]), 1)
            self.assertEqual(out["failed"][0]["reason"],
                             "tampered-since-seal")

    def test_transient_store_failures_are_retried(self):
        """Backoff retry: a store that fails twice then succeeds yields a
        complete upload — controlled, observable, recoverable."""
        with tempfile.TemporaryDirectory() as td, \
                tempfile.TemporaryDirectory() as sd:
            bundle = Path(td)
            _seal_bundle(bundle)
            s = store.LocalBundleStore(sd)
            sleeps = []
            real_put = s.put
            calls = {"n": 0}

            def flaky(role_tag, payload):
                calls["n"] += 1
                if calls["n"] <= 2:
                    raise store.StoreError("transient outage")
                return real_put(role_tag, payload)

            with mock.patch.object(s, "put", side_effect=flaky):
                out = store.upload_bundle(s, str(bundle), sleep=sleeps.append)
            self.assertEqual(out["failed"], [])
            self.assertGreaterEqual(len(sleeps), 2, "backoff must have run")

    def test_collision_is_never_retried(self):
        """A tamper signal (digest collision) propagates immediately —
        retrying a tamper signal would be indistinguishable from accepting
        it."""
        with tempfile.TemporaryDirectory() as td, \
                tempfile.TemporaryDirectory() as sd:
            bundle = Path(td)
            _seal_bundle(bundle)
            s = store.LocalBundleStore(sd)
            manifest = json.loads(
                (bundle / "evidence-manifest.json").read_text())
            first = manifest["objects"][0]
            payload = (bundle / first["path"]).read_bytes()
            d = s.put("evidence-manifest/v1", payload)
            s._path_for(d).write_bytes(b"corrupted")  # poison the address
            with self.assertRaises(store.StoreError):
                store.upload_bundle(s, str(bundle))


class TestCompleteCacheKey(unittest.TestCase):
    """coh-ctx-05: the key must be TOTAL — every input changes the key."""

    BASE = dict(
        subject_digest="sha256:" + "a" * 64,
        openspec_digest="sha256:" + "b" * 64,
        policy_digest="sha256:" + "c" * 64,
        context_digest="sha256:" + "d" * 64,
        evaluator_image_digest="sha256:" + "e" * 64,
    )

    def _key(self, **overrides):
        return store.decision_cache_key(**{**self.BASE, **overrides})

    def test_identical_inputs_same_key(self):
        self.assertEqual(self._key(), self._key())

    def _assert_changes_key(self, **overrides):
        self.assertNotEqual(self._key(), self._key(**overrides))

    def test_every_single_input_changes_the_key(self):
        self._assert_changes_key(subject_digest="sha256:" + "1" * 64)
        self._assert_changes_key(openspec_digest="sha256:" + "2" * 64)
        self._assert_changes_key(policy_digest="sha256:" + "3" * 64)
        self._assert_changes_key(context_digest="sha256:" + "4" * 64)
        self._assert_changes_key(evaluator_image_digest=None)  # unknown identity ≠ attributed
        self._assert_changes_key(plugin_digests=["sha256:" + "5" * 64])
        self._assert_changes_key(captured_fact_digests=["sha256:" + "6" * 64])
        self._assert_changes_key(ttl_seconds=3600)
        self._assert_changes_key(retention_days=30)
        self._assert_changes_key(signer_key_id="abcd1234")

    def test_plugin_order_is_irrelevant(self):
        a = self._key(plugin_digests=["sha256:" + "5" * 64,
                                      "sha256:" + "7" * 64])
        b = self._key(plugin_digests=["sha256:" + "7" * 64,
                                      "sha256:" + "5" * 64])
        self.assertEqual(a, b)

    def test_unknown_vs_attributed_identity_differ(self):
        """A decision made under an unknown evaluator identity is NOT
        interchangeable with one made under an attributed identity."""
        self.assertNotEqual(
            self._key(evaluator_image_digest=None),
            self._key(evaluator_image_digest="sha256:" + "e" * 64))


class TestCacheValidity(unittest.TestCase):
    """coh-ev-04: TTL and retention expiry invalidate, regardless of
    content identity; malformed entries miss, never hit."""

    def test_fresh_entry_valid(self):
        self.assertTrue(store.cache_entry_valid(
            {"stored_epoch": 1_000_000.0}, now_epoch=1_000_060.0,
            ttl_seconds=120, retention_days=365))

    def test_ttl_expiry_invalidates(self):
        # elapsed 3601s > ttl 3600s
        self.assertFalse(store.cache_entry_valid(
            {"stored_epoch": 1_000_000.0}, now_epoch=1_003_601.0,
            ttl_seconds=3600, retention_days=365))

    def test_retention_expiry_invalidates_even_with_long_ttl(self):
        """Retention is the hard wall: an unexpired TTL cannot resurrect an
        entry whose retention window closed."""
        self.assertFalse(store.cache_entry_valid(
            {"stored_epoch": 0.0}, now_epoch=400 * 86400.0,
            ttl_seconds=None, retention_days=365))

    def test_malformed_entries_miss_never_hit(self):
        for bad in (None, {}, {"no_epoch": 1}, "entry", 42):
            self.assertFalse(store.cache_entry_valid(
                bad, now_epoch=1000.0, ttl_seconds=60, retention_days=30))


if __name__ == "__main__":
    unittest.main()
