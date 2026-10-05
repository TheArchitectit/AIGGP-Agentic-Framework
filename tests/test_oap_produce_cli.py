# // spec: coh-oap-01, coh-oap-07, coh-oap-hard-04
"""Conformance for the observe-only `devgate.oap-evidence/v2` producer CLI.

Exercises `tools/oap_produce.py`: the real producer path emits contract-v2 wire
envelopes as NDJSON, the valid artifact is accepted by the real wire verifier
and observe-only consumer, and every adversarial variant is rejected at the
stage it is meant to fail. The CLI's stdout must be byte-for-byte the wire shape
`strict_parse.verify_wire_envelope` parses, so a co-located consumer can read it.

Scope honesty: this repository has no Go OAP receiver, so no Go consumer path is
exercised here. The CLI is the producer side of a local pipe only; every verdict
is NON-AUTHORIZING.
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "tools" / "oap_produce.py"

from hub.coherence import canon, oap_observer, strict_parse  # noqa: E402
from hub.coherence.oap_observer import observe  # noqa: E402
from hub.coherence.replay_guard import InMemoryReplayBackend, ReplayGuard  # noqa: E402
from hub.coherence.trust_store import TrustStore  # noqa: E402


def _load_cli():
    spec = importlib.util.spec_from_file_location("oap_produce_cli", CLI)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLI_MOD = _load_cli()


class TestOapProduceCli(unittest.TestCase):
    def setUp(self):
        if not CLI_MOD.ed25519_vetted.AVAILABLE:
            self.skipTest("vetted Ed25519 provider unavailable")
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bundle = CLI_MOD.build_bundle()
        # default store: registers the real signing key, audience oap-observer.
        self.trust = self._store("default", CLI_MOD.AUDIENCE)
        # identity-key store: registers the low-order identity key so the
        # forgery reaches the signature stage instead of failing as unknown-key.
        identity = {
            "snapshot_time": CLI_MOD.REFERENCE_TIME,
            "entries": [dict(CLI_MOD._trust_doc()["entries"][0],
                             key_id=strict_parse.key_id_for(CLI_MOD.IDENTITY_PUBLIC),
                             public_key=CLI_MOD.IDENTITY_PUBLIC.hex())],
        }
        self.trust_identity = self._write_store("identity-key", identity)
        self.expected = dict(CLI_MOD.BASE_BODY, direction="devgate-to-oap")

    def tearDown(self):
        self.tmp.cleanup()

    def _write_store(self, name, doc):
        path = self.root / f"trust-{name}.json"
        path.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
        return TrustStore.load(path)

    def _store(self, name, audience):
        return self._write_store(name, CLI_MOD._trust_doc(audience=audience))

    def _verify(self, raw, trust=None, **kwargs):
        return strict_parse.verify_wire_envelope(
            raw, self.trust if trust is None else trust,
            reference_time=kwargs.pop("reference_time", CLI_MOD.REFERENCE_TIME),
            payload=kwargs.pop("payload", self.bundle["payload"]),
            result=kwargs.pop("result", self.bundle["result"]),
            evidence_manifest=kwargs.pop("evidence_manifest", self.bundle["manifest"]),
            attestation=kwargs.pop("attestation", self.bundle["attestation"]),
            audience=kwargs.pop("audience", None))

    def _observe(self, raw, **kwargs):
        return observe(
            raw, self.trust, self.expected,
            reference_time=kwargs.pop("reference_time", CLI_MOD.REFERENCE_TIME),
            payload=kwargs.pop("payload", self.bundle["payload"]),
            result=kwargs.pop("result", self.bundle["result"]),
            evidence_manifest=kwargs.pop("evidence_manifest", self.bundle["manifest"]),
            attestation=kwargs.pop("attestation", self.bundle["attestation"]),
            replay_guard=kwargs.pop("replay_guard", ReplayGuard(InMemoryReplayBackend())),
            operation="observe-coherence", now=1_000_000.0, revocation_version=7)

    def _case(self, name):
        return CLI_MOD.build_case(name, self.bundle)

    # --- the real producer artifact is accepted ---------------------------
    def test_valid_case_is_accepted_by_wire_verifier_and_observer(self):
        (raw,) = self._case("valid")
        self.assertEqual(strict_parse.parse_envelope(raw)["body"]["contract_version"],
                         "devgate.oap-evidence/v2")
        self.assertEqual(self._verify(raw, audience=CLI_MOD.AUDIENCE), (True, None))
        verdict = self._observe(raw)
        self.assertEqual((verdict.accepted, verdict.reason),
                         (True, "non-authorizing:observed"))
        self.assertIs(oap_observer.NON_AUTHORIZING, True)

    # --- every adversarial variant fails where it is meant to -------------
    def test_adversarial_variants_are_rejected(self):
        (forgery,) = self._case("identity-low-order-forgery")
        self.assertEqual(self._verify(forgery, trust=self.trust_identity)[1],
                         "signature-mismatch")

        (duplicate,) = self._case("duplicate-key")
        self.assertEqual(self._verify(duplicate), (False, "duplicate-key:body"))

        (wrong_tag,) = self._case("wrong-domain-tag")
        self.assertEqual(self._verify(wrong_tag)[1], "signature-mismatch")

        (expired,) = self._case("expired")
        self.assertEqual(self._verify(expired)[1], "envelope-expired")

        (wrong_audience,) = self._case("wrong-audience")
        self.assertTrue(
            self._verify(wrong_audience, audience=CLI_MOD.AUDIENCE)[1]
            .startswith("key-audience-mismatch"))

        (wrong_tenant,) = self._case("wrong-tenant")
        self.assertEqual(self._verify(wrong_tenant), (True, None))
        self.assertEqual(self._observe(wrong_tenant).reason,
                         "context-mismatch:tenant_or_project_id")

    def test_lying_cross_link_and_replayed_jti_are_rejected(self):
        (lying,) = self._case("lying-cross-link")
        # Wire digests bind the tampered result bytes; the observer's
        # cross-binding stage then rejects the inconsistent result<->body link.
        self.assertEqual(self._verify(lying, result=self.bundle["result"] + b"x")[1],
                         "result-digest-mismatch")
        tampered = canon.canon(dict(self.bundle["result_doc"],
                                    subject_digest="sha256:" + "9" * 64))
        self.assertEqual(self._verify(lying, result=tampered), (True, None))
        self.assertEqual(self._observe(lying, result=tampered).reason,
                         "result-binding-mismatch:subject_digest")

        first_raw, second_raw = self._case("replayed-jti")
        self.assertEqual(first_raw, second_raw)
        guard = ReplayGuard(InMemoryReplayBackend())
        first = self._observe(first_raw, replay_guard=guard)
        second = self._observe(second_raw, replay_guard=guard)
        self.assertTrue(first.accepted)
        self.assertTrue(second.reason.startswith("replay:duplicate"))

    # --- every emitted line is exact contract-v2 wire bytes ---------------
    def test_every_case_emits_wire_shaped_bytes(self):
        for name, raw in CLI_MOD.build_all(CLI_MOD.CASES):
            with self.subTest(case=name):
                self.assertIsInstance(raw, bytes)
                parsed = json.loads(raw.decode("utf-8"))
                if name == "duplicate-key":
                    # deliberately non-canonical/duplicate: strict parse rejects.
                    with self.assertRaises(strict_parse.StrictParseError):
                        strict_parse.parse_envelope(raw)
                    self.assertIn(b'"body":{}', raw)
                    continue
                # Byte-for-byte canonical: a canonical-bytes receiver accepts it.
                self.assertEqual(canon.canon(parsed), raw)
                self.assertEqual(strict_parse.parse_envelope(raw)["body"][
                    "contract_version"], "devgate.oap-evidence/v2")

    # --- the CLI itself is an observe-only NDJSON pipe producer -----------
    def test_cli_emits_ndjson_and_is_observe_only(self):
        proc = subprocess.run(
            [sys.executable, str(CLI), "--all", "--observe-only"],
            cwd=str(REPO), capture_output=True, check=True)
        lines = [ln for ln in proc.stdout.split(b"\n") if ln.strip()]
        # valid + 7 adversarial + 2 identical replay lines = 10 envelopes.
        self.assertEqual(len(lines), 10)
        self.assertEqual(lines[0], self._case("valid")[0])
        self.assertEqual(lines[-1], self._case("valid")[0])
        # Valid line verifies; the duplicate-key line is rejected at parse.
        self.assertEqual(self._verify(lines[0], audience=CLI_MOD.AUDIENCE), (True, None))
        self.assertEqual(strict_parse.verify_wire_envelope(lines[2], self.trust),
                         (False, "duplicate-key:body"))
        self.assertIs(CLI_MOD.NON_AUTHORIZING, True)
        self.assertIn("observe", CLI_MOD.DOC_LINE.lower())
        doc = subprocess.run(
            [sys.executable, str(CLI), "--doc", "--case", "valid"],
            cwd=str(REPO), capture_output=True, check=True)
        self.assertIn(b"OBSERVE-ONLY", doc.stderr)

    def test_cli_writes_out_file_and_evidence_bundle(self):
        out = self.root / "envelopes.ndjson"
        ev = self.root / "evidence"
        subprocess.run(
            [sys.executable, str(CLI), "--case", "valid",
             "--out", str(out), "--evidence-dir", str(ev)],
            cwd=str(REPO), capture_output=True, check=True)
        self.assertEqual(out.read_bytes(), self._case("valid")[0] + b"\n")
        self.assertEqual((ev / "result.bin").read_bytes(), self.bundle["result"])
        loaded = TrustStore.load(ev / "keys.json")
        key_id = strict_parse.key_id_for(
            CLI_MOD.ed25519_vetted.public_key(CLI_MOD.SEED))
        self.assertIsNotNone(loaded.lookup(key_id))
        expected = json.loads((ev / "expected.json").read_text(encoding="utf-8"))
        self.assertEqual(expected["direction"], "devgate-to-oap")
        self.assertEqual((ev / "reference-time.txt").read_text().strip(),
                         CLI_MOD.REFERENCE_TIME)


if __name__ == "__main__":
    unittest.main()
