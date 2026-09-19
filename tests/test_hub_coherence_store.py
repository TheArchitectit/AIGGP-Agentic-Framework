# // spec: coh-ev-02
"""Store adapter (coh-ev-02): an offline local bundle plus a retryable remote
upload that runs AFTER sealing. The two contracts the spec pins:

  1. Uploading never changes the sealed decision or evidence-manifest digest —
     they were fixed at seal. This is what makes "retry the upload later" safe:
     the bundle you send on the third try is provably the bytes you sealed on
     the first.
  2. Remote upload is a transport the service is HANDED, never a network path
     the service opens: TestStaticDefaultDeny forbids importing any network
     module in hub/coherence, so `upload` takes a callable; with no transport
     the default mode is the offline local bundle (no egress).

All fixtures synthetic (R9).
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import evidence, store


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


if __name__ == "__main__":
    unittest.main()
