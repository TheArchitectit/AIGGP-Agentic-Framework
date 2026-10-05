"""Gate 2.2 unit tests for the independently provisioned trust store.

The receiver's signer registrations and revocation state come from a
provisioned trust file, never from the artifact and never from untrusted
caller input. See hub/coherence/trust_store.py and
openspec/changes/harden-oap-evidence-verification/spec.md
(coh-oap-hard-04).
"""
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from hub.coherence import ed25519, oap_evidence
from hub.coherence.trust_store import TrustStore, TrustStoreError, digest_of

SEED = bytes([0x11]) * ed25519.SEED_SIZE
KEY_ID = oap_evidence.key_id_for(ed25519.public_key(SEED))


def _entry(**overrides):
    entry = {
        "producer_id": "devgate-instance-1",
        "key_id": KEY_ID,
        "public_key": ed25519.public_key(SEED).hex(),
        "audience": "oap-observer",
        "direction": "devgate-to-oap",
        "valid_from": "2026-10-01T00:00:00Z",
        "valid_until": "2026-11-01T00:00:00Z",
        "revoked": False,
        "revocation_version": 3,
    }
    entry.update(overrides)
    return entry


class TrustStoreFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, doc, name="trust.json"):
        path = Path(self.dir) / name
        path.write_text(
            doc if isinstance(doc, str) else json.dumps(doc),
            encoding="utf-8")
        return path

    def _load(self, entries=None, doc=None, **kwargs):
        if doc is None:
            doc = {
                "snapshot_time": "2026-10-04T12:00:00Z",
                "entries": entries if entries is not None else [_entry()],
            }
        return TrustStore.load(self._write(doc), **kwargs)

    # -- correct load ------------------------------------------------------
    def test_correct_trust_store_loads(self):
        store = self._load()
        self.assertEqual(len(store.entries), 1)
        self.assertEqual(store.revocation_version, 3)
        entry = store.lookup(KEY_ID)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["producer_id"], "devgate-instance-1")

    # -- provisioning errors fail closed -----------------------------------
    def test_missing_file_denies(self):
        with self.assertRaises(TrustStoreError):
            TrustStore.load(Path(self.dir) / "absent.json")

    def test_malformed_json_denies(self):
        with self.assertRaises(TrustStoreError):
            TrustStore.load(self._write("{not json"))

    def test_entry_missing_field_denies(self):
        bad = _entry()
        del bad["revocation_version"]
        with self.assertRaises(TrustStoreError):
            self._load([bad])

    def test_entry_unknown_field_denies(self):
        with self.assertRaises(TrustStoreError):
            self._load([dict(_entry(), trust_me=True)])

    def test_duplicate_key_id_denies(self):
        with self.assertRaises(TrustStoreError):
            self._load([_entry(), _entry()])

    def test_bad_public_key_denies(self):
        with self.assertRaises(TrustStoreError):
            self._load([_entry(public_key="zz" * 32)])
        with self.assertRaises(TrustStoreError):
            self._load([_entry(public_key="ab" * 31)])

    def test_bad_revocation_version_denies(self):
        for bad in (-1, "3", True, 1.5):
            with self.subTest(bad=bad):
                with self.assertRaises(TrustStoreError):
                    self._load([_entry(revocation_version=bad)])

    def test_constructor_refuses_caller_data(self):
        with self.assertRaises(TrustStoreError):
            TrustStore([_entry()])

    # -- evaluate: revoked / expired / unknown ------------------------------
    def _reference(self, iso="2026-10-04T12:30:00Z"):
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))

    def test_unknown_key_denies(self):
        store = self._load()
        entry, reason = store.evaluate(
            "ed25519:" + "9" * 32, producer_id="devgate-instance-1",
            direction="devgate-to-oap", audience="oap-observer",
            reference_time=self._reference())
        self.assertIsNone(entry)
        self.assertEqual(reason, "unknown-key:ed25519:" + "9" * 32)

    def test_revoked_entry_denies(self):
        store = self._load([_entry(revoked=True)])
        entry, reason = store.evaluate(
            KEY_ID, producer_id="devgate-instance-1",
            direction="devgate-to-oap", audience="oap-observer",
            reference_time=self._reference())
        self.assertIsNone(entry)
        self.assertEqual(reason, f"revoked-key:{KEY_ID}")

    def test_expired_entry_denies(self):
        store = self._load()
        entry, reason = store.evaluate(
            KEY_ID, producer_id="devgate-instance-1",
            direction="devgate-to-oap", audience="oap-observer",
            reference_time=self._reference("2026-12-01T00:00:00Z"))
        self.assertIsNone(entry)
        self.assertEqual(reason, "key-expired")

    def test_not_yet_valid_entry_denies(self):
        store = self._load()
        entry, reason = store.evaluate(
            KEY_ID, producer_id="devgate-instance-1",
            direction="devgate-to-oap", audience="oap-observer",
            reference_time=self._reference("2026-09-01T00:00:00Z"))
        self.assertIsNone(entry)
        self.assertEqual(reason, "key-not-yet-valid")

    def test_scope_binding_denies(self):
        store = self._load()
        cases = [
            ({"producer_id": "wrong-producer"},
             "key-producer-mismatch:wrong-producer"),
            ({"direction": "oap-to-devgate"},
             "key-direction-mismatch:oap-to-devgate"),
            ({"audience": "other-oap"}, "key-audience-mismatch:other-oap"),
        ]
        for overrides, expected in cases:
            with self.subTest(expected=expected):
                narrow = TrustStore.load(self._write(
                    {"entries": [_entry(**overrides)]},
                    name=f"{expected.split(':')[0]}.json"))
                entry, reason = narrow.evaluate(
                    KEY_ID, producer_id="devgate-instance-1",
                    direction="devgate-to-oap", audience="oap-observer",
                    reference_time=self._reference())
                self.assertIsNone(entry)
                self.assertEqual(reason, expected)

    def test_valid_entry_admits(self):
        store = self._load()
        entry, reason = store.evaluate(
            KEY_ID, producer_id="devgate-instance-1",
            direction="devgate-to-oap", audience="oap-observer",
            reference_time=self._reference())
        self.assertIsNone(reason)
        self.assertIsNotNone(entry)

    # -- stale revocation snapshot -----------------------------------------
    def test_stale_revocation_snapshot_denies(self):
        store = self._load(max_snapshot_age_seconds=600)
        self.assertEqual(store.snapshot_time, "2026-10-04T12:00:00Z")
        entry, reason = store.evaluate(
            KEY_ID, producer_id="devgate-instance-1",
            direction="devgate-to-oap", audience="oap-observer",
            reference_time=self._reference("2026-10-04T12:30:00Z"))
        self.assertIsNone(entry)
        self.assertEqual(reason, "stale-revocation-snapshot")

    def test_fresh_snapshot_admits(self):
        store = self._load(max_snapshot_age_seconds=3600)
        entry, reason = store.evaluate(
            KEY_ID, producer_id="devgate-instance-1",
            direction="devgate-to-oap", audience="oap-observer",
            reference_time=self._reference("2026-10-04T12:30:00Z"))
        self.assertIsNone(reason)

    def test_staleness_bound_requires_snapshot_time(self):
        with self.assertRaises(TrustStoreError):
            self._load(doc={"entries": [_entry()]},
                       max_snapshot_age_seconds=600)


if __name__ == "__main__":
    unittest.main()
