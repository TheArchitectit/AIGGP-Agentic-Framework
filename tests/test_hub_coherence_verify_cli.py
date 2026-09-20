# // spec: coh-ev-05
"""End-to-end verification-CLI tests (S5 audit): the consumer tool
`python -m hub.coherence --verify-run <dir> --signer-set <doc>` exercises
attest.verify()'s full nine-step fail-closed chain. attest.verify_attestation
(unit-tested in test_hub_coherence_attestation.py) is NOT what the CLI calls,
and the audit found verify() had no coverage beyond malformed input.

Each tamper test re-signs with the fixture key so it isolates one link of the
chain: the statement-digest and bound-digest checks must each independently
reject a tamper, not merely mask one another. All fixtures synthetic (R9).
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

from hub.coherence import attest, canon
from tests.fixtures.coherence import fixtures as fx

REPO = Path(__file__).resolve().parent.parent


class TestVerificationCLI(unittest.TestCase):
    """The consumer verification CLI (attest.verify + verify_run_cli).

    These exercise the full nine-step fail-closed chain end to end. Unit
    tests above cover verify_attestation, which the CLI never calls — the
    S5 audit found verify() itself had no coverage beyond malformed input.
    """

    def _sealed_run(self, td, *, stage=2):
        req, out = fx.build_root(Path(td) / "f", declared_name="widget",
                                 approved_name="widget", stage=stage)
        r = subprocess.run(
            [sys.executable, "-m", "hub.coherence", "--request", str(req)],
            capture_output=True, text=True, cwd=str(REPO),
            env={**os.environ, **fx.cli_env()})
        self.assertEqual(r.returncode, 0, r.stderr)
        return out

    def _signer_set_path(self, td):
        ss = fx.signer_set("a" * 64, key_id="signer-1",
                           identity="pilot-signer", as_of=fx.FIXED_TIME)
        p = Path(td) / "signer-set.json"
        p.write_text(json.dumps(ss))
        return p

    def _verify(self, out, ssp):
        return subprocess.run(
            [sys.executable, "-m", "hub.coherence",
             "--verify-run", str(out), "--signer-set", str(ssp)],
            capture_output=True, text=True, cwd=str(REPO))

    def test_intact_run_verifies_exit0(self):
        """Happy path: --verify-run on a sealed Stage 2 run returns 0.

        Before the S5 audit fix this path was unreachable — --request was
        argparse-required, so every --verify-run invocation died in argparse.
        """
        with tempfile.TemporaryDirectory() as td:
            out = self._sealed_run(td)
            r = self._verify(out, self._signer_set_path(td))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("verification ok", r.stdout)

    def test_substituted_decision_is_detected(self):
        """coh-ev-05 result-substituted scenario through the CLI: replacing
        result.json after sealing must fail verification (exit 1)."""
        with tempfile.TemporaryDirectory() as td:
            out = self._sealed_run(td)
            ssp = self._signer_set_path(td)
            self.assertEqual(self._verify(out, ssp).returncode, 0)
            # Swap in a different decision, leaving the attestation intact.
            (out / "result.json").write_bytes(b'{"decision": "PASS"}')
            r = self._verify(out, ssp)
            self.assertEqual(r.returncode, 1, "substitution must fail closed")
            self.assertIn("mismatch", r.stderr)

    def test_bound_digest_tamper_is_detected(self):
        """verify()'s bound-digest loop (step 8) is independently load-bearing.

        Editing result.json alone trips step 7 first, so a CLI-level test
        cannot reach step 8. Here the attestation's bound value is edited AND
        re-signed with the known test key, leaving the result untouched: the
        signature and statement digest both verify, so only the bound-digest
        comparison stands between the tamper and a false PASS. Deleting that
        loop (audit mutation f) must make this test fail.
        """
        with tempfile.TemporaryDirectory() as td:
            out = self._sealed_run(td)
            ap = out / "attestation.json"
            att = json.loads(ap.read_text())
            att["bound"]["subject_digest"] = "sha256:" + "9" * 64
            unsigned = dict(att)
            unsigned.pop("signature")
            att["signature"] = attest.SIGNATURE_PREFIX + hmac.new(
                bytes.fromhex("a" * 64),
                canon.canon(unsigned), hashlib.sha256).hexdigest()
            ap.write_text(json.dumps(att))
            # The result is untouched, so step 7 (statement digest) cannot
            # fire — only the bound-digest loop can reject this.
            res_digest = json.loads(
                (out / "result.json").read_text())["subject_digest"]
            self.assertNotEqual(res_digest, att["bound"]["subject_digest"])
            r = self._verify(out, self._signer_set_path(td))
            self.assertEqual(r.returncode, 1,
                             "bound mismatch must fail closed")
            self.assertIn("bound-digest-mismatch", r.stderr)

    def test_statement_digest_check_is_independently_load_bearing(self):
        """verify()'s statement-digest check (step 7) is not merely masked by
        the bound loop (step 8).

        Any edit to result.json changes both checks at once, so a test that
        only swaps the file proves nothing about step 7 by itself. Here the
        attestation's statement_digest is rewritten and re-signed while every
        bound value still agrees with the result: step 8 cannot fire, so only
        step 7 can reject it. Removing step 7 (audit mutation e) must fail
        this test.
        """
        with tempfile.TemporaryDirectory() as td:
            out = self._sealed_run(td)
            ap = out / "attestation.json"
            att = json.loads(ap.read_text())
            res = json.loads((out / "result.json").read_text())
            # Every bound value still matches the result: step 8 is inert.
            for key in ("subject_digest", "openspec_digest", "policy_digest",
                        "context_digest", "evaluator_image_digest"):
                self.assertEqual(res[key], att["bound"][key])
            att["statement_digest"] = canon.digest_bytes(
                "decision/v1", b"a different decision entirely")
            unsigned = dict(att)
            unsigned.pop("signature")
            att["signature"] = attest.SIGNATURE_PREFIX + hmac.new(
                bytes.fromhex("a" * 64),
                canon.canon(unsigned), hashlib.sha256).hexdigest()
            ap.write_text(json.dumps(att))
            r = self._verify(out, self._signer_set_path(td))
            self.assertEqual(r.returncode, 1,
                             "statement-digest mismatch must fail closed")
            self.assertIn("decision-digest-mismatch", r.stderr)

    def test_evidence_tamper_is_detected(self):
        """coh-ev-05 tamper scenario: editing a sealed evidence object makes
        verification fail (evidence.verify catches the object digest).

        Needs a violating run so an evidence object actually exists: a
        declared/approved name mismatch yields a VIOLATED finding.
        """
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td) / "f", declared_name="other",
                                     approved_name="widget", stage=2)
            r = subprocess.run(
                [sys.executable, "-m", "hub.coherence",
                 "--request", str(req)],
                capture_output=True, text=True, cwd=str(REPO),
                env={**os.environ, **fx.cli_env()})
            ssp = self._signer_set_path(td)
            self.assertEqual(self._verify(out, ssp).returncode, 0)
            findings = list((out / "evidence" / "findings").glob("*.json"))
            self.assertTrue(findings, "violating run must seal evidence")
            findings[0].write_bytes(b'{"tampered": true}')
            r = self._verify(out, ssp)
            self.assertEqual(r.returncode, 1, "tamper must fail closed")

    def test_revoked_signer_fails_verification(self):
        """coh-ev-05 revoked-signer scenario through the CLI."""
        with tempfile.TemporaryDirectory() as td:
            out = self._sealed_run(td)
            ss = fx.signer_set("a" * 64, key_id="signer-1",
                               identity="pilot-signer", as_of=fx.FIXED_TIME,
                               revoked=True)
            p = Path(td) / "revoked.json"
            p.write_text(json.dumps(ss))
            r = self._verify(out, p)
            self.assertEqual(r.returncode, 1)
            self.assertIn("revoked", r.stderr)

    def test_missing_artifacts_exit2(self):
        """Missing run artifacts -> exit 2."""
        r = subprocess.run(
            [sys.executable, "-m", "hub.coherence",
             "--verify-run", "/tmp/nonexistent_run_dir",
             "--signer-set", str(REPO / "openspec" / "changes"
                                  "devgate-spec-coherence-service"
                                  "schemas" / "signer-set.schema.json")],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(r.returncode, 2)

    def test_malformed_signer_set_exit2(self):
        """Malformed signer set -> exit 2."""
        r = subprocess.run(
            [sys.executable, "-m", "hub.coherence",
             "--verify-run", str(Path(tempfile.mkdtemp())),
             "--signer-set", str(REPO / "openspec" / "changes"
                                  "devgate-spec-coherence-service"
                                  "schemas" / "attestation.schema.json")],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(r.returncode, 2)

    def test_verify_run_requires_signer_set(self):
        """--verify-run without --signer-set exits 2 with a clear message."""
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run(
                [sys.executable, "-m", "hub.coherence",
                 "--verify-run", str(Path(td))],
                capture_output=True, text=True, cwd=str(REPO))
            self.assertEqual(r.returncode, 2)
            self.assertIn("--signer-set is required", r.stderr)


class TestPromotionBinding(unittest.TestCase):
    """coh-pol-07 scenario 2: an attestation for D1 must not promote D2.

    `verify()` compares the bound subject digest against the digest INSIDE
    the run — that proves internal consistency and nothing more. It has no
    way to express "this attestation is being presented for candidate D2",
    because the run directory does not know what it is being used for. The
    candidate is supplied by the CALLER (the promotion path), which is what
    verify_promotion adds.
    """

    def _sealed_run(self, td, *, declared_name, approved_name):
        # Each run gets its own fixture dir: two runs in one dir would collide
        # on the shared subject/ tree and throw FileExistsError.
        req, out = fx.build_root(Path(td) / f"f-{declared_name}",
                                 declared_name=declared_name,
                                 approved_name=approved_name, stage=2)
        r = subprocess.run(
            [sys.executable, "-m", "hub.coherence", "--request", str(req)],
            capture_output=True, text=True, cwd=str(REPO),
            env={**os.environ, **fx.cli_env()})
        self.assertEqual(r.returncode, 0, r.stderr)
        return out

    def _signer_set(self):
        return fx.signer_set("a" * 64, key_id="signer-1",
                             identity="pilot-signer", as_of=fx.FIXED_TIME)

    def test_bound_candidate_verifies(self):
        """Control: verifying a run against its OWN subject digest passes."""
        with tempfile.TemporaryDirectory() as td:
            out = self._sealed_run(td, declared_name="widget",
                                   approved_name="widget")
            bound = json.loads((out / "attestation.json").read_text())["bound"]
            ok, reason = attest.verify_promotion(
                str(out), self._signer_set(), bound["subject_digest"])
            self.assertTrue(ok, reason)

    def test_attestation_for_another_candidate_is_refused(self):
        """The coh-pol-07 scenario: a valid PASS attestation for D1 presented
        for D2 is refused, and the reason names the candidate binding."""
        with tempfile.TemporaryDirectory() as td:
            d1 = self._sealed_run(td, declared_name="widget",
                                  approved_name="widget")
            d2 = self._sealed_run(td, declared_name="other",
                                  approved_name="other")
            d1_bound = json.loads(
                (d1 / "attestation.json").read_text())["bound"]
            d2_bound = json.loads(
                (d2 / "attestation.json").read_text())["bound"]
            self.assertNotEqual(d1_bound["subject_digest"],
                                d2_bound["subject_digest"],
                                "fixture defect: the two runs must differ")

            # D1's run is intact and verifies on its own terms...
            self.assertTrue(attest.verify(str(d1), self._signer_set())[0])
            # ...but it does NOT authorize promoting D2.
            ok, reason = attest.verify_promotion(
                str(d1), self._signer_set(), d2_bound["subject_digest"])
            self.assertFalse(ok, "an attestation for D1 must not promote D2")
            self.assertIn("candidate-digest-mismatch", reason)

    def test_verify_failures_still_propagate(self):
        """The binding check must not mask an already-failing run.

        A tampered run refused for being tampered must say so, not report a
        candidate mismatch — otherwise a broken seal would be misreported as
        a benign wrong-candidate rejection.
        """
        with tempfile.TemporaryDirectory() as td:
            out = self._sealed_run(td, declared_name="widget",
                                   approved_name="widget")
            bound = json.loads(
                (out / "attestation.json").read_text())["bound"]
            (out / "result.json").write_bytes(b'{"decision": "PASS"}')
            ok, reason = attest.verify_promotion(
                str(out), self._signer_set(), bound["subject_digest"])
            self.assertFalse(ok)
            self.assertNotIn("candidate-digest-mismatch", reason)


if __name__ == "__main__":
    unittest.main()
