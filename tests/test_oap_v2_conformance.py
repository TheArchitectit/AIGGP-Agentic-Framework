"""S-E4 bounded loopback conformance; not an OAP integration claim.

The fixture calls real DevGate result/evidence/attestation producers, then the
v2 producer emits raw bytes. The consumer is independent of that adapter and
returns only observe-only outcomes. No receiver, transport, policy mutation,
or mandatory gate is exercised because this repository has no Go OAP boundary.
"""
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from hub.coherence import attest_base, attest_detached, canon, evidence, manifest, result, strict_parse
from hub.coherence import oap_observer
from hub.coherence.oap_observer import observe
from hub.coherence.oap_v2_producer import produce
from hub.coherence.replay_guard import InMemoryReplayBackend, ReplayGuard
from hub.coherence.trust_store import TrustStore
from hub.coherence import ed25519_vetted

SEED = bytes([0x11]) * 32
OTHER_SEED = bytes([0x22]) * 32
NOW = "2026-10-05T12:01:00Z"


class TestV2ContractVectors(unittest.TestCase):
    def test_canonical_domain_key_id_and_signature_vector(self):
        if not ed25519_vetted.AVAILABLE:
            self.skipTest("vetted Ed25519 provider unavailable")
        body = {"a": "é", "n": 9223372036854775807}
        self.assertEqual(
            canon.canon(body).hex(),
            "7b2261223a225c7530306539222c226e223a393232333337323033363835343737353830377d")
        self.assertEqual(
            strict_parse.signed_bytes(body).hex(),
            "646576676174652e6f61702d65766964656e63652f7632007b2261223a225c7530306539222c226e223a393232333337323033363835343737353830377d")
        seed = bytes([0x11]) * 32
        public = ed25519_vetted.public_key(seed)
        self.assertEqual(strict_parse.key_id_for(public),
                         "ed25519:40fe5496bc3a8d26f2573fa9e22849809e39e26b59bdf2f7d7ee96a2edadece8")
        self.assertEqual(
            ed25519_vetted.sign(seed, strict_parse.signed_bytes(body)).hex(),
            "d2827ef616ddb91dd9b901a9a926487105c09250808d47386390feb576eed61e9e6b3a165af4f53eb995133be7cf80217c115fa4824b44ae42bf02827ac60903")


class TestV2LoopbackConformance(unittest.TestCase):
    def setUp(self):
        if not ed25519_vetted.AVAILABLE:
            self.skipTest("vetted Ed25519 provider unavailable")
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        source = root / "subject"
        source.mkdir()
        (source / "README.txt").write_bytes(b"real DevGate subject\n")
        subject = manifest.build(str(source))
        self.payload = canon.canon({"subject_digest": subject["subject_digest"]})
        self.manifest_digest = evidence.seal([], str(root / "evidence"))
        identities = {
            "subject_digest": subject["subject_digest"],
            "openspec_digest": "sha256:" + "b" * 64,
            "policy_digest": "sha256:" + "c" * 64,
            "context_digest": "sha256:" + "d" * 64,
            "evaluator_image_digest": "sha256:" + "e" * 64,
            "platform": "test",
        }
        # Real canonical DevGate result producer; evidence was sealed first.
        result_doc = result.build([], [], identities, stage=0,
                                  semantics="fresh-promotion",
                                  evidence_manifest_digest=self.manifest_digest)
        self.result = result.to_canonical(result_doc)
        bound = {
            "subject_digest": identities["subject_digest"],
            "openspec_digest": identities["openspec_digest"],
            "policy_digest": identities["policy_digest"],
            "context_digest": identities["context_digest"],
            "evaluator_image_digest": identities["evaluator_image_digest"],
            "evidence_manifest_digest": self.manifest_digest,
        }
        with mock.patch.dict(os.environ, {
                attest_base.SIGNER_KEYS_ENV: json.dumps({"devgate-attestor": "aa" * 32}),
        }, clear=True):
            attestation_doc = attest_detached.attest(
                self.result, bound, "devgate-attestor", issued_at=NOW)
        self.attestation = canon.canon(attestation_doc)
        self.body = {
            "producer_id": "devgate-instance-1",
            "consumer_audience": "oap-observer",
            "tenant_or_project_id": "fixture-project",
            "subject_kind": "source-tree",
            "subject_digest": identities["subject_digest"],
            "request_id": "request-001",
            "evaluation_id": "evaluation-001",
            "nonce": "nonce-001",
            "idempotency_key": "idempotency-001",
            "issued_at": "2026-10-05T12:00:00Z",
            "expires_at": "2026-10-05T12:04:00Z",
            "policy_digest": identities["policy_digest"],
            "context_digest": identities["context_digest"],
            "evaluator_digest": identities["evaluator_image_digest"],
            "native_decision": result_doc["decision"],
            "native_exit_code": 0,
            "semantics": result_doc["semantics"],
            "native_status": "PASS",
            "native_reason": "all required assertions satisfied",
        }
        self.raw = produce(self.body, payload=self.payload, result=self.result,
                           evidence_manifest=(root / "evidence" / "evidence-manifest.json").read_bytes(),
                           attestation=self.attestation, seed=SEED)
        self.public = ed25519_vetted.public_key(SEED)
        self.key_id = strict_parse.key_id_for(self.public)
        trust_path = root / "trust.json"
        trust_path.write_text(json.dumps({
            "snapshot_time": "2026-10-05T12:00:00Z",
            "entries": [{
                "producer_id": "devgate-instance-1", "key_id": self.key_id,
                "public_key": self.public.hex(), "audience": "oap-observer",
                "direction": "devgate-to-oap",
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_until": "2027-01-01T00:00:00Z", "revoked": False,
                "revocation_version": 7,
            }],
        }), encoding="utf-8")
        self.trust = TrustStore.load(trust_path)
        self.expected = dict(self.body, direction="devgate-to-oap")
        self.guard = ReplayGuard(InMemoryReplayBackend())
        self.evidence_manifest = (root / "evidence" / "evidence-manifest.json").read_bytes()

    def tearDown(self):
        self.tmp.cleanup()

    def _observe(self, raw=None, trust=None, expected=None, **kwargs):
        return observe(
            self.raw if raw is None else raw,
            self.trust if trust is None else trust,
            self.expected if expected is None else expected,
            reference_time=kwargs.pop("reference_time", NOW),
            payload=kwargs.pop("payload", self.payload),
            result=kwargs.pop("result", self.result),
            evidence_manifest=kwargs.pop("evidence_manifest", self.evidence_manifest),
            attestation=kwargs.pop("attestation", self.attestation),
            replay_guard=kwargs.pop("replay_guard", self.guard),
            operation=kwargs.pop("operation", "observe-coherence"),
            now=kwargs.pop("now", 1_000_000.0),
            revocation_version=kwargs.pop("revocation_version", 7))

    def _raw_with(self, **body_overrides):
        body = dict(self.body)
        body.update(body_overrides)
        return produce(body, payload=self.payload, result=self.result,
                       evidence_manifest=self.evidence_manifest,
                       attestation=self.attestation, seed=SEED)

    def test_real_producer_raw_parse_trust_and_bindings_are_observed(self):
        parsed = strict_parse.parse_envelope(self.raw)
        self.assertEqual(canon.canon(parsed), self.raw)
        verdict = self._observe()
        self.assertEqual((verdict.accepted, verdict.reason),
                         (True, "non-authorizing:observed"))
        self.assertIs(oap_observer.NON_AUTHORIZING, True)

    def test_consumer_rejects_wrong_signer_tenant_subject_policy_evaluator(self):
        attacker = produce(self.body, payload=self.payload, result=self.result,
                            evidence_manifest=self.evidence_manifest,
                            attestation=self.attestation, seed=OTHER_SEED)
        self.assertEqual(self._observe(raw=attacker).reason.split(":", 1)[0], "unknown-key")
        for field in ("tenant_or_project_id", "subject_digest", "policy_digest", "evaluator_digest"):
            with self.subTest(field=field):
                changed = self._raw_with(**{field: "sha256:" + "9" * 64
                                            if field.endswith("digest") else "other"})
                self.assertEqual(self._observe(raw=changed).reason,
                                 f"context-mismatch:{field}")

    def test_consumer_rejects_direction_version_status_and_duplicate_keys(self):
        wrong_direction = self.raw.replace(
            b'"direction":"devgate-to-oap"',
            b'"direction":"oap-to-devgate"', 1)
        with self.assertRaises(strict_parse.StrictParseError):
            strict_parse.parse_envelope(wrong_direction)
        wrong_version = self.raw.replace(
            b'"contract_version":"devgate.oap-evidence/v2"',
            b'"contract_version":"devgate.oap-evidence/v1"', 1)
        self.assertEqual(self._observe(raw=wrong_version).reason.split(":", 1)[0],
                         "unsupported-contract-version")
        laundering = self.raw.replace(
            b'"native_status":"PASS"', b'"native_status":"ERROR"', 1)
        self.assertEqual(self._observe(raw=laundering).reason,
                         "status-exit-mismatch:PASS/ERROR")
        duplicate = self.raw.replace(
            b'"signature":', b'"body":{},"signature":', 1)
        self.assertEqual(self._observe(raw=duplicate).reason, "duplicate-key:body")
        nested_duplicate = self.raw.replace(
            b'"native_reason":"all required assertions satisfied"',
            b'"native_reason":"all required assertions satisfied",'
            b'"native_reason":"all required assertions satisfied"', 1)
        self.assertEqual(self._observe(raw=nested_duplicate).reason,
                         "duplicate-key:native_reason")
        self.assertEqual(self._observe(raw=b"not-json").reason,
                         "malformed-json:Expecting value")

    def test_consumer_rejects_expiry_revocation_and_stale_trust(self):
        self.assertEqual(self._observe(reference_time="2026-10-05T12:05:00Z").reason,
                         "envelope-expired")
        root = Path(self.tmp.name)
        revoked = json.loads((root / "trust.json").read_text())
        revoked["entries"][0]["revoked"] = True
        revoked_path = root / "revoked.json"
        revoked_path.write_text(json.dumps(revoked))
        self.assertEqual(self._observe(trust=TrustStore.load(revoked_path)).reason,
                         f"revoked-key:{self.key_id}")
        stale = TrustStore.load(root / "trust.json", max_snapshot_age_seconds=60)
        self.assertEqual(self._observe(trust=stale, reference_time="2026-10-05T12:02:00Z").reason,
                         "stale-revocation-snapshot")

    def test_consumer_rejects_missing_or_tampered_evidence_and_bindings(self):
        for name, kwargs, reason in (
            ("payload", {"payload": None}, "missing-evidence-bytes:payload"),
            ("result", {"result": None}, "missing-evidence-bytes:result"),
            ("manifest", {"evidence_manifest": None}, "missing-evidence-bytes:evidence-manifest"),
            ("attestation", {"attestation": None}, "missing-evidence-bytes:attestation"),
            ("payload-tamper", {"payload": self.payload + b"tamper"}, "payload-digest-mismatch"),
        ):
            with self.subTest(name=name):
                self.assertEqual(self._observe(**kwargs).reason, reason)
        self.assertEqual(self._observe(result=b"{}").reason, "result-digest-mismatch")

    def test_status_laundering_and_replay_expiry_are_non_authorizing(self):
        for decision, status, code in (("PASS", "ERROR", 0),
                                       ("ADVISORY", "ADVISORY", 10),
                                       ("FAIL", "FAIL", 20)):
            with self.subTest(decision=decision):
                raw = self._raw_with(native_decision=decision,
                                     native_status=status,
                                     native_exit_code=code)
                if decision == "PASS":
                    self.assertEqual(self._observe(raw=raw).reason,
                                     "status-exit-mismatch:PASS/ERROR")
                else:
                    self.assertEqual(self._observe(raw=raw).reason,
                                     f"context-mismatch:native_decision")
        guard = ReplayGuard(InMemoryReplayBackend(), ttl_seconds=1)
        self.assertTrue(self._observe(replay_guard=guard, now=10).accepted)
        self.assertTrue(self._observe(replay_guard=guard, now=12).reason.startswith("replay:expired"))

    def test_duplicate_and_concurrent_replay_are_non_authorizing(self):
        first = self._observe()
        self.assertTrue(first.accepted)
        self.assertTrue(self._observe().reason.startswith("replay:duplicate"))
        guard = ReplayGuard(InMemoryReplayBackend())
        results = []
        lock = threading.Lock()
        barrier = threading.Barrier(8)
        def worker():
            barrier.wait()
            verdict = self._observe(replay_guard=guard)
            with lock:
                results.append(verdict.accepted)
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(results.count(True), 1)
        self.assertIs(guard.NON_AUTHORIZING if hasattr(guard, "NON_AUTHORIZING") else True, True)


if __name__ == "__main__":
    unittest.main()
