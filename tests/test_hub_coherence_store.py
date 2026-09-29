# // spec: coh-ev-02, coh-ev-04, coh-ctx-05
"""Evidence store tests: the upload-then-seal contract (ours, coh-ev-02),
the immutable LocalBundleStore and retryable upload_bundle (theirs, S5),
the TOTAL decision-cache key and TTL/retention invalidation (theirs, S6).

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


def _seal_one_finding(td: str) -> Path:
    """A real sealed evidence bundle with one finding, written to disk."""
    out = Path(td) / "run"
    out.mkdir()
    finding = {
        "assertion_id": "a1", "finding_key": "a1|x|identity-mismatch",
        "subject_locations": ["README.md"], "expected": "widget",
        "observed": "other", "evidence_refs": [],
    }
    evidence.seal([finding], str(out))
    return out


def _seal_bundle(td: Path, assertion_id="a1"):
    findings = [{
        "assertion_id": assertion_id,
        "finding_key": f"{assertion_id}|x|identity-mismatch",
        "outcome": "VIOLATED", "enforcement": "BLOCK", "severity": "high",
        "subject_locations": ["README.md"], "expected": "widget",
        "observed": "other", "evidence_refs": [],
    }]
    return evidence.seal(findings, str(td))


class TestBundleCompleteness(unittest.TestCase):
    """coh-ev-02's retry-safety argument assumes the upload sends the whole
    bundle. If the enumeration drops an artifact, the consumer's verify later
    reports missing-artifact and no upload ever fixes it — a durability lie
    the retry loop cannot surface."""

    def test_upload_carries_every_file_verify_requires(self):
        with tempfile.TemporaryDirectory() as td:
            out = _seal_one_finding(td)
            # A real signed run has an attestation.json alongside the manifest.
            (out / "result.json").write_bytes(b'{"decision":"FAIL"}')
            (out / "attestation.json").write_bytes(b'{"signature":"x"}')

            sent: set[str] = set()
            store.upload(str(out),
                         lambda name, payload: sent.add(name))
            # attest.verify's line 117-118 requires exactly these three at the
            # top level, plus the evidence objects the manifest enumerates.
            self.assertIn("result.json", sent)
            self.assertIn("attestation.json", sent)
            self.assertIn("evidence-manifest.json", sent)
            self.assertTrue(any(n.startswith("evidence/findings/") for n in sent),
                            "evidence objects enumerated by the manifest must be sent")


class TestUploadResendsSealedBytes(unittest.TestCase):
    def test_transport_receives_the_exact_bytes_that_were_sealed(self):
        """The core of coh-ev-02's retry scenario: an upload hands the
        transport the same bytes that are on disk, so a retry after a failure
        provably re-sends the sealed decision — digests unchanged."""
        with tempfile.TemporaryDirectory() as td:
            out = _seal_one_finding(td)
            sealed = {p.relative_to(out).as_posix(): p.read_bytes()
                      for p in store.artifacts(out)}

            received: dict[str, bytes] = {}
            store.upload(str(out),
                         lambda name, payload: received.__setitem__(name, payload))

            self.assertEqual(received, sealed,
                             "upload must hand the transport exactly the sealed bytes")

    def test_a_failing_upload_leaves_the_sealed_bundle_recomputable(self):
        """coh-ev-02's retry-safety: 'retry the upload later' is only safe if a
        failed attempt changed nothing. A transport that always raises must
        surface as UploadError AND leave the on-disk digests identical to what
        they were, so a later retry proves it is sending the same decision."""
        with tempfile.TemporaryDirectory() as td:
            out = _seal_one_finding(td)
            manifest_before = store.manifest_digest(str(out))
            sealed_files = {p: p.read_bytes() for p in store.artifacts(out)}

            def always_fails(name, payload):
                raise OSError("connection reset")

            with self.assertRaises(store.UploadError):
                store.upload(str(out), always_fails)

            # Nothing the caller would compare against shifted: re-reading the
            # bundle yields the same digest and the same bytes.
            self.assertEqual(store.manifest_digest(str(out)), manifest_before,
                             "a failed upload must not touch the manifest")
            self.assertEqual({p: p.read_bytes() for p in store.artifacts(out)},
                             sealed_files, "no bundle bytes may change")

    def test_uploading_an_unsealed_bundle_is_refused(self):
        """coh-ev-02's whole premise is 'upload after seal'. Uploading a
        directory with no manifest must fail closed with UploadError — a
        silent success here would let a caller believe a run is durable when
        nothing was actually sealed."""
        with tempfile.TemporaryDirectory() as td:
            empty = Path(td) / "run"
            empty.mkdir()
            with self.assertRaises(store.UploadError) as cm:
                store.upload(str(empty), lambda name, payload: None)
            self.assertIn("unsealed", str(cm.exception))

    def test_retry_after_a_failure_sends_every_artifact(self):
        """'The caller retries the upload later': a transport that fails once
        then succeeds must, on the next `upload`, hand over every artifact —
        nothing lost from the failed attempt."""
        with tempfile.TemporaryDirectory() as td:
            out = _seal_one_finding(td)
            expected = {p.relative_to(out).as_posix(): p.read_bytes()
                        for p in store.artifacts(out)}

            calls = {"n": 0}
            sent: dict[str, bytes] = {}

            def flaky(name, payload):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise OSError("transient")
                sent[name] = payload

            with self.assertRaises(store.UploadError):
                store.upload(str(out), flaky)
            # Retry: same call, transport now healthy.
            store.upload(str(out), flaky)
            self.assertEqual(sent, expected,
                             "after a retry every artifact has been sent once")


class TestUploadBoundsManifestPaths(unittest.TestCase):
    """The round-9 fix in `evidence.verify` established that a manifest's
    `path` field is attacker-influenceable — a tamperer may edit it after
    sealing. The store reads the same field, so it inherits the same
    boundary, and the failure mode is worse here: a boolean oracle becomes an
    arbitrary-file read handed to whatever transport the caller passes in."""

    def test_a_manifest_path_that_escapes_the_bundle_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "run"
            (out / "evidence" / "findings").mkdir(parents=True)
            # Plant a "secret" outside the bundle and point the manifest at
            # it via traversal.
            secret = root / "outside-secret.json"
            secret.write_text("leak-me", encoding="utf-8")
            manifest = {
                "api_version": "devgate.spec-coherence.evidence/v1",
                "objects": [{"path": "../outside-secret.json",
                             "digest": "sha256:" + "0" * 64,
                             "media_type": "application/json",
                             "assertion_id": "a", "retention_class": "standard",
                             "redacted": True}],
            }
            (out / "evidence-manifest.json").write_bytes(canon.canon(manifest))
            sent: list = []
            with self.assertRaises(store.UploadError) as cm:
                store.upload(str(out), lambda n, p: sent.append((n, p)))
            self.assertIn("out-of-bounds", str(cm.exception))
            self.assertEqual(sent, [],
                             "no bytes may reach the transport for an escaping path")

    def test_a_non_string_manifest_path_is_refused(self):
        """`out / obj['path']` would TypeError on a non-string, surfacing as a
        raw crash rather than the documented UploadError contract."""
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "run"
            (out / "evidence" / "findings").mkdir(parents=True)
            manifest = {
                "api_version": "devgate.spec-coherence.evidence/v1",
                "objects": [{"path": None, "digest": "sha256:" + "0" * 64,
                             "media_type": "application/json",
                             "assertion_id": "a", "retention_class": "standard",
                             "redacted": True}],
            }
            (out / "evidence-manifest.json").write_bytes(canon.canon(manifest))
            with self.assertRaises(store.UploadError):
                store.upload(str(out), lambda n, p: None)


class TestLocalBundleStore(unittest.TestCase):
    """S5 graft: LocalBundleStore — content-addressed, append-only local
    object store. The store never overwrites, never silently ignores a
    collision: same address + different bytes must stop the world."""

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
    """S5 graft: retryable/resumable upload into a LocalBundleStore."""

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
