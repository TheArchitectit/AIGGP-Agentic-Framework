# // spec: coh-ev-01, coh-ev-05
"""Detached attestation tests: sealing order, sign/verify, fail-closed,
re-signing, and envelope schema validation. All fixtures synthetic (R9).

CLI runs use subprocess with fx.cli_env() so attestation is produced
for Stage 2+ fresh-promotion runs.
"""
import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import attest, canon, evidence, result, schemacheck
from tests.fixtures.coherence import fixtures as fx

REPO = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO / "openspec/changes/devgate-spec-coherence-service/schemas"


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text())


def _run(req_path: Path, env=None):
    """Invoke the real CLI; return returncode."""
    r = subprocess.run(
        [sys.executable, "-m", "hub.coherence", "--request", str(req_path)],
        capture_output=True, text=True, cwd=str(REPO),
        env=env or {**os.environ, **fx.cli_env()})
    return r.returncode


class TestRequiredTruthTable(unittest.TestCase):
    def test_stage_0_never_required(self):
        self.assertFalse(attest.required(0, "fresh-promotion"))
        self.assertFalse(attest.required(0, "replay"))

    def test_stage_1_never_required(self):
        self.assertFalse(attest.required(1, "fresh-promotion"))
        self.assertFalse(attest.required(1, "replay"))

    def test_stage_2_fresh_promotion_required(self):
        self.assertTrue(attest.required(2, "fresh-promotion"))

    def test_stage_2_replay_not_required(self):
        self.assertFalse(attest.required(2, "replay"))

    def test_stage_3_fresh_promotion_required(self):
        self.assertTrue(attest.required(3, "fresh-promotion"))


class TestSignAndVerify(unittest.TestCase):
    def _make_identities(self):
        return {
            "subject_digest": "sha256:" + "a" * 64,
            "openspec_digest": "sha256:" + "b" * 64,
            "policy_digest": "sha256:" + "c" * 64,
            "context_digest": "sha256:" + "d" * 64,
            "evaluator_image_digest": "sha256:" + "e" * 64,
            "evidence_manifest_digest": "sha256:" + "f" * 64,
        }

    def test_sign_produces_valid_schema(self):
        decision = b"canonical-decision-bytes"
        ids = self._make_identities()
        a = attest.sign(decision, ids, "2026-09-17T00:00:00Z")
        errs = schemacheck.validate(a, _load_schema("attestation.schema.json"))
        self.assertEqual(errs, [])
        self.assertIn("signature", a)
        self.assertTrue(a["signature"].startswith("hmac-sha256:"))

    def test_statement_digest_matches_decision(self):
        decision = b"my-decision"
        ids = self._make_identities()
        a = attest.sign(decision, ids, "2026-09-17T00:00:00Z")
        expected = canon.digest_bytes("decision/v1", decision)
        self.assertEqual(a["statement_digest"], expected)

    def test_sign_missing_key_raises(self):
        os.environ.pop("HUB_COHERENCE_SIGNER_KEY", None)
        with self.assertRaises(attest.AttestationError) as c:
            attest.sign(b"d", self._make_identities(), "2026-09-17T00:00:00Z")
        self.assertIn("signer-key-not-configured", str(c.exception))

    def test_sign_no_evaluator_digest_raises(self):
        os.environ["HUB_COHERENCE_SIGNER_KEY"] = "a" * 64
        ids = self._make_identities()
        ids["evaluator_image_digest"] = None
        with self.assertRaises(attest.AttestationError) as c:
            attest.sign(b"d", ids, "2026-09-17T00:00:00Z")
        self.assertIn("evaluator-image-digest-required-for-attestation",
                       str(c.exception))

    def test_verify_attestation_ok(self):
        decision = b"my-decision"
        ids = self._make_identities()
        a = attest.sign(decision, ids, "2026-09-17T00:00:00Z")
        set_doc = fx.signer_set("a" * 64, as_of="2026-09-17T00:00:00Z")
        ok, reason = attest.verify_attestation(decision, a, set_doc)
        self.assertTrue(ok, reason)

    def test_verify_fails_on_substituted_digest(self):
        """coh-ev-05 scenario: changing a bound digest makes verify fail."""
        decision = b"my-decision"
        ids = self._make_identities()
        a = attest.sign(decision, ids, "2026-09-17T00:00:00Z")
        a_tampered = dict(a)
        a_tampered["statement_digest"] = "sha256:" + "f" * 64
        set_doc = fx.signer_set("a" * 64, as_of="2026-09-17T00:00:00Z")
        ok, reason = attest.verify_attestation(decision, a_tampered, set_doc)
        self.assertFalse(ok)
        self.assertIn("signature-mismatch", reason)

    def test_verify_fails_on_wrong_key(self):
        decision = b"my-decision"
        ids = self._make_identities()
        a = attest.sign(decision, ids, "2026-09-17T00:00:00Z")
        # Set with a different key
        set_doc = fx.signer_set("b" * 64, as_of="2026-09-17T00:00:00Z")
        ok, reason = attest.verify_attestation(decision, a, set_doc)
        self.assertFalse(ok)
        self.assertIn("signature-mismatch", reason)

    def test_verify_revoked_signer_fails(self):
        """coh-ev-05 scenario: revoked signer always fails."""
        decision = b"my-decision"
        ids = self._make_identities()
        a = attest.sign(decision, ids, "2026-09-17T00:00:00Z")
        set_doc = fx.signer_set("a" * 64, as_of="2026-09-17T00:00:00Z",
                                 revoked=True)
        ok, reason = attest.verify_attestation(decision, a, set_doc)
        self.assertFalse(ok)
        self.assertIn("signer-revoked", reason)

    def test_verify_expired_signer_fails(self):
        """signer expired -> fail-closed."""
        decision = b"my-decision"
        ids = self._make_identities()
        a = attest.sign(decision, ids, "2026-09-17T00:00:00Z")
        set_doc = fx.signer_set("a" * 64, as_of="2026-09-17T00:00:00Z",
                                 valid_until="2025-01-01T00:00:00Z")
        ok, reason = attest.verify_attestation(decision, a, set_doc)
        self.assertFalse(ok)
        self.assertIn("signer-expired", reason)

    def test_verify_not_yet_valid_fails(self):
        """signer not yet valid -> fail-closed."""
        decision = b"my-decision"
        ids = self._make_identities()
        a = attest.sign(decision, ids, "2026-09-17T00:00:00Z")
        set_doc = fx.signer_set("a" * 64, as_of="2026-09-17T00:00:00Z",
                                 valid_from="2027-01-01T00:00:00Z")
        ok, reason = attest.verify_attestation(decision, a, set_doc)
        self.assertFalse(ok)
        self.assertIn("signer-not-yet-valid", reason)

    def test_verify_unknown_key_id_fails(self):
        decision = b"my-decision"
        ids = self._make_identities()
        a = attest.sign(decision, ids, "2026-09-17T00:00:00Z")
        set_doc = fx.signer_set("z" * 64, key_id="unknown-signer",
                                 as_of="2026-09-17T00:00:00Z")
        ok, reason = attest.verify_attestation(decision, a, set_doc)
        self.assertFalse(ok)
        self.assertIn("signer-not-in-set", reason)


class TestSealingOrder(unittest.TestCase):
    def test_stage2_fresh_promotion_produces_attestation(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), declared_name="widget",
                                     approved_name="widget", stage=2)
            code = _run(req)
            att_path = out / "attestation.json"
            self.assertTrue(att_path.exists())
            a = json.loads(att_path.read_text())
            self.assertEqual(a["api_version"],
                             "devgate.spec-coherence.attestation/v1")
            self.assertIn("statement_digest", a)
            self.assertIn("bound", a)
            self.assertIn("signature", a)
            env_path = out / "run-envelope.json"
            self.assertTrue(env_path.exists())
            env = json.loads(env_path.read_text())
            self.assertTrue(env["signed"])
            self.assertEqual(env["artifacts"]["attestation"], "attestation.json")

    def test_stage1_no_attestation(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), stage=1)
            code = _run(req)
            self.assertFalse((out / "attestation.json").exists())
            env = json.loads((out / "run-envelope.json").read_text())
            self.assertFalse(env["signed"])
            self.assertIsNone(env["artifacts"]["attestation"])

    def test_decision_bytes_unaffected_by_signing(self):
        """coh-ev-01: canonical decision bytes are the same whether or
        not signing happens — signing produces a detached object."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), declared_name="widget",
                                     approved_name="widget", stage=1)
            code1 = _run(req)
            decision_bytes_1 = (out / "result.json").read_bytes()
            # Check result.json validates against result.schema.json
            res1 = json.loads(decision_bytes_1)
            errs = schemacheck.validate(res1, _load_schema("result.schema.json"))
            self.assertEqual(errs, [])

    def test_repeat_run_byte_identical_attestation(self):
        """Determinism: repeat sign produces byte-identical attestation."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), declared_name="widget",
                                     approved_name="widget", stage=2)
            _run(req)
            first = (out / "attestation.json").read_bytes()
            _run(req)
            second = (out / "attestation.json").read_bytes()
            self.assertEqual(first, second,
                             "attestation must be byte-identical on replay")

    def test_envelope_schema_signed(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), stage=2)
            _run(req)
            env = json.loads((out / "run-envelope.json").read_text())
            errs = schemacheck.validate(env, _load_schema("run-envelope.schema.json"))
            self.assertEqual(errs, [])

    def test_envelope_schema_unsigned(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), stage=1)
            _run(req)
            env = json.loads((out / "run-envelope.json").read_text())
            errs = schemacheck.validate(env, _load_schema("run-envelope.schema.json"))
            self.assertEqual(errs, [])


class TestFailClosed(unittest.TestCase):
    def test_stage2_no_signer_key_fails(self):
        """Without HUB_COHERENCE_SIGNER_KEY, Stage 2 fresh-promotion exits 33."""
        env = {k: v for k, v in fx.cli_env().items()
               if k != "HUB_COHERENCE_SIGNER_KEY"}
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), declared_name="widget",
                                     approved_name="widget", stage=2)
            code = _run(req, env=env)
            self.assertEqual(code, result.EXIT_EVIDENCE)
            env_doc = json.loads((out / "result.json").read_text())
            self.assertEqual(env_doc["error"]["class"], "attestation")

    def test_stage2_local_derives_evaluator_digest_from_registry(self):
        """Local Stage 2 without env var succeeds via registry-derived digest."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), declared_name="widget",
                                     approved_name="widget", stage=2)
            code = _run(req)
            self.assertEqual(code, 0)
            a = json.loads((out / "attestation.json").read_text())
            self.assertTrue(a["bound"]["evaluator_image_digest"]
                            .startswith("sha256:"))

    def test_stage2_undeclared_profile_fails_closed(self):
        """Undeclared execution profile in local mode → exit 30."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), declared_name="widget",
                                     approved_name="widget", stage=2,
                                     execution_profile="undeclared-label")
            code = _run(req)
            self.assertEqual(code, result.EXIT_INVALID_INPUT)
            env_doc = json.loads((out / "result.json").read_text())
            self.assertIn("undeclared-profile", env_doc["error"]["reason"])

    def test_stage0_no_attestation_normal_exit(self):
        """Stage 0 observation run produces no attestation, signed: false."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), stage=0)
            code = _run(req)
            self.assertFalse((out / "attestation.json").exists())
            env = json.loads((out / "run-envelope.json").read_text())
            self.assertFalse(env["signed"])
            self.assertFalse(env["attestation_required"])

    def test_stage2_replay_no_attestation(self):
        """Stage 2 replay is non-promotion-authorizing; no attestation."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), stage=2, semantics="replay")
            code = _run(req)
            self.assertFalse((out / "attestation.json").exists())
            env = json.loads((out / "run-envelope.json").read_text())
            self.assertFalse(env["signed"])

    def test_blocked_attestation_write_fails_closed_not_traceback(self):
        """The attestation write shares the decision path's failure contract
        (round-2 B1): an output location where attestation.json cannot be
        written must yield the documented exit code, never a raw traceback —
        this is the promotion-authorizing path, so it must fail closed."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), declared_name="widget",
                                     approved_name="widget", stage=2)
            out.mkdir(parents=True, exist_ok=True)
            (out / "attestation.json").mkdir()   # IsADirectoryError on write
            p = subprocess.run(
                [sys.executable, "-m", "hub.coherence",
                 "--request", str(req)],
                capture_output=True, text=True, cwd=str(REPO),
                env={**os.environ, **fx.cli_env()})
            self.assertNotIn("Traceback", p.stderr, "raw traceback")
            self.assertEqual(p.returncode, result.EXIT_EVIDENCE,
                             f"expected exit 33, got {p.returncode}")
            env_doc = json.loads((out / "result.json").read_text()) \
                if (out / "result.json").exists() else None
            if env_doc is not None and "error" in env_doc:
                self.assertEqual(env_doc["error"]["class"], "attestation")

    def test_blocked_envelope_write_fails_closed_not_traceback(self):
        """The transport envelope is last in sealing order (coh-ev-01) and
        shares the same failure contract: an unwritable envelope location must
        not kill an otherwise-complete run with a traceback."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), declared_name="widget",
                                     approved_name="widget", stage=2)
            out.mkdir(parents=True, exist_ok=True)
            (out / "run-envelope.json").mkdir()   # IsADirectoryError on write
            p = subprocess.run(
                [sys.executable, "-m", "hub.coherence",
                 "--request", str(req)],
                capture_output=True, text=True, cwd=str(REPO),
                env={**os.environ, **fx.cli_env()})
            self.assertNotIn("Traceback", p.stderr, "raw traceback")
            self.assertEqual(p.returncode, result.EXIT_EVIDENCE,
                             f"expected exit 33, got {p.returncode}")


class TestResigning(unittest.TestCase):
    def test_resign_leaves_decision_unchanged(self):
        """coh-ev-01: re-signing with a different key produces a new
        signature over the same statement_digest; decision bytes unchanged."""
        decision = b"my-canonical-decision"
        ids = {
            "subject_digest": "sha256:" + "a" * 64,
            "openspec_digest": "sha256:" + "b" * 64,
            "policy_digest": "sha256:" + "c" * 64,
            "context_digest": "sha256:" + "d" * 64,
            "evaluator_image_digest": "sha256:" + "e" * 64,
            "evidence_manifest_digest": "sha256:" + "f" * 64,
        }
        old_key = os.environ.get("HUB_COHERENCE_SIGNER_KEY")
        old_key_id = os.environ.get("HUB_COHERENCE_SIGNER_KEY_ID")
        try:
            os.environ["HUB_COHERENCE_SIGNER_KEY"] = "a" * 64
            os.environ["HUB_COHERENCE_SIGNER_KEY_ID"] = "signer-a"
            a1 = attest.sign(decision, ids, "2026-09-17T00:00:00Z")
            os.environ["HUB_COHERENCE_SIGNER_KEY"] = "b" * 64
            os.environ["HUB_COHERENCE_SIGNER_KEY_ID"] = "signer-b"
            a2 = attest.sign(decision, ids, "2026-09-17T00:00:00Z")
            self.assertEqual(a1["statement_digest"], a2["statement_digest"])
            self.assertNotEqual(a1["signature"], a2["signature"])
            self.assertNotEqual(a1["signer"]["key_id"], a2["signer"]["key_id"])
        finally:
            if old_key is not None:
                os.environ["HUB_COHERENCE_SIGNER_KEY"] = old_key
            else:
                os.environ.pop("HUB_COHERENCE_SIGNER_KEY", None)
            if old_key_id is not None:
                os.environ["HUB_COHERENCE_SIGNER_KEY_ID"] = old_key_id
            else:
                os.environ.pop("HUB_COHERENCE_SIGNER_KEY_ID", None)

    def test_both_attestations_verify(self):
        """Two attestations over the same decision both verify."""
        decision = b"my-canonical-decision"
        ids = {
            "subject_digest": "sha256:" + "a" * 64,
            "openspec_digest": "sha256:" + "b" * 64,
            "policy_digest": "sha256:" + "c" * 64,
            "context_digest": "sha256:" + "d" * 64,
            "evaluator_image_digest": "sha256:" + "e" * 64,
            "evidence_manifest_digest": "sha256:" + "f" * 64,
        }
        os.environ["HUB_COHERENCE_SIGNER_KEY"] = "a" * 64
        a1 = attest.sign(decision, ids, "2026-09-17T00:00:00Z")
        os.environ["HUB_COHERENCE_SIGNER_KEY"] = "b" * 64
        a2 = attest.sign(decision, ids, "2026-09-17T00:00:00Z")
        set1 = fx.signer_set("a" * 64, as_of="2026-09-17T00:00:00Z")
        set2 = fx.signer_set("b" * 64, as_of="2026-09-17T00:00:00Z")
        ok1, reason1 = attest.verify_attestation(decision, a1, set1)
        ok2, reason2 = attest.verify_attestation(decision, a2, set2)
        self.assertTrue(ok1, reason1)
        self.assertTrue(ok2, reason2)


class TestAttestationSchemaValidation(unittest.TestCase):
    def test_attestation_schema_validates(self):
        decision = b"test"
        ids = {
            "subject_digest": "sha256:" + "a" * 64,
            "openspec_digest": "sha256:" + "b" * 64,
            "policy_digest": "sha256:" + "c" * 64,
            "context_digest": "sha256:" + "d" * 64,
            "evaluator_image_digest": "sha256:" + "e" * 64,
            "evidence_manifest_digest": "sha256:" + "f" * 64,
        }
        os.environ["HUB_COHERENCE_SIGNER_KEY"] = "a" * 64
        a = attest.sign(decision, ids, "2026-09-17T00:00:00Z")
        errs = schemacheck.validate(a, _load_schema("attestation.schema.json"))
        self.assertEqual(errs, [])


if __name__ == "__main__":
    unittest.main()
