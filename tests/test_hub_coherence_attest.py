# // spec: coh-ev-01, coh-ev-05, coh-pol-02
"""S5/S6 core: detached attestation (produce, verify, substitute, revoke),
policy anti-rollback, and the decision claims the pipeline emits.

Every negative case encodes a frozen rejection: a signature over different
bytes, an unknown or revoked signer, a key swap, a rolled-back policy
bundle — each must fail with its stable reason, never pass.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import attest, canon
from tests.fixtures.coherence import fixtures as fx

KEY_HEX = "aa" * 32
KEY_HEX_2 = "bb" * 32
IDENTITY = "cp-signer-1"
BOUND = {
    "subject_digest": "sha256:" + "a" * 64,
    "openspec_digest": "sha256:" + "b" * 64,
    "policy_digest": "sha256:" + "c" * 64,
    "context_digest": "sha256:" + "d" * 64,
    "evaluator_image_digest": "sha256:" + "9" * 64,
    "evidence_manifest_digest": "sha256:" + "e" * 64,
}


def _keys_env(identity=IDENTITY, key=KEY_HEX):
    return {attest.SIGNER_KEYS_ENV: json.dumps({identity: key})}


class TestAttestProduce(unittest.TestCase):
    def setUp(self):
        self.payload = canon.canon({"decision": "PASS", "n": 1})

    def test_unconfigured_signing_refuses_not_fabricates(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(attest.AttestationError):
                attest.attest(self.payload, BOUND, IDENTITY)

    def test_produced_attestation_verifies(self):
        with mock.patch.dict(os.environ, _keys_env(), clear=True):
            att = attest.attest(self.payload, BOUND, IDENTITY,
                                issued_at="2026-09-20T00:00:00Z")
            signer_set = [{"key_id": attest.key_id_for(bytes.fromhex(KEY_HEX)),
                           "identity": IDENTITY}]
            ok, reason = attest.verify(att, self.payload,
                                       {k: v for k, v in BOUND.items()},
                                       signer_set)
        self.assertTrue(ok, reason)
        self.assertIsNone(reason)

    def test_acyclic_order_re_signing_leaves_decision_unchanged(self):
        """coh-ev-01 scenario: two attestations (different keys) over the
        same decision — the decision bytes are identical and both verify."""
        with mock.patch.dict(os.environ, _keys_env(), clear=True):
            att1 = attest.attest(self.payload, BOUND, IDENTITY)
        with mock.patch.dict(os.environ, _keys_env(key=KEY_HEX_2), clear=True):
            att2 = attest.attest(self.payload, BOUND, IDENTITY)
        self.assertNotEqual(att1["signature"], att2["signature"])
        for att, key in ((att1, KEY_HEX), (att2, KEY_HEX_2)):
            with mock.patch.dict(os.environ, _keys_env(key=key), clear=True):
                signer_set = [
                    {"key_id": attest.key_id_for(bytes.fromhex(key)),
                     "identity": IDENTITY}]
                ok, reason = attest.verify(
                    att, self.payload, dict(BOUND), signer_set)
                self.assertTrue(ok, reason)


class TestAttestVerifyNegative(unittest.TestCase):
    """Substitution, revocation, key swap, window — each fails closed."""

    def _att(self, payload=None):
        payload = payload if payload is not None else \
            canon.canon({"decision": "PASS"})
        with mock.patch.dict(os.environ, _keys_env(), clear=True):
            return attest.attest(payload, BOUND, IDENTITY), payload

    def _signer_set(self, **overrides):
        entry = {"key_id": attest.key_id_for(bytes.fromhex(KEY_HEX)),
                 "identity": IDENTITY}
        entry.update(overrides)
        return [entry]

    def test_statement_substitution_detected(self):
        att, payload = self._att()
        forged = canon.canon({"decision": "FAIL"})
        ok, reason = attest.verify(att, forged, dict(BOUND),
                                   self._signer_set())
        self.assertFalse(ok)
        self.assertEqual(reason, "statement-substitution")

    def test_bound_input_substitution_detected(self):
        """A decision over DIFFERENT inputs (e.g. swapped context) does not
        inherit the attestation even though the signature is valid."""
        att, payload = self._att()
        with mock.patch.dict(os.environ, _keys_env(), clear=True):
            drifted = dict(BOUND, context_digest="sha256:" + "8" * 64)
            ok, reason = attest.verify(att, payload, drifted,
                                       self._signer_set())
        self.assertFalse(ok)
        self.assertEqual(reason, "bound-input-substitution:context_digest")

    def test_unknown_signer_rejected(self):
        att, payload = self._att()
        with mock.patch.dict(os.environ, _keys_env(), clear=True):
            ok, reason = attest.verify(att, payload, dict(BOUND),
                                       [{"key_id": "whatever",
                                         "identity": "someone-else"}])
        self.assertFalse(ok)
        # The reason names the ATTESTATION's signer — the identity
        # that failed set membership — not the set member.
        self.assertEqual(reason, f"unknown-signer:{IDENTITY}")

    def test_revoked_signer_rejected_even_with_valid_signature(self):
        """Revocation is authoritative over signature validity."""
        att, payload = self._att()
        ok, reason = attest.verify(
            att, payload, dict(BOUND),
            self._signer_set(revoked=True))
        self.assertFalse(ok)
        self.assertEqual(reason, f"revoked-signer:{IDENTITY}")

    def test_key_rotation_detected(self):
        """Same identity, rotated key material: the recorded key_id no
        longer matches — reject rather than guess."""
        att, payload = self._att()
        with mock.patch.dict(os.environ, _keys_env(key=KEY_HEX_2), clear=True):
            ok, reason = attest.verify(att, payload, dict(BOUND),
                                       self._signer_set())
        self.assertFalse(ok)
        self.assertEqual(reason, "key-mismatch")

    def test_validity_window_enforced_against_reference_time(self):
        att, payload = self._att()
        # Signer valid FROM 2026-10-01; reference (context evaluation_time)
        # 2026-09-20 is before the window.
        ok, reason = attest.verify(
            att, payload, dict(BOUND),
            self._signer_set(valid_from="2026-10-01T00:00:00Z"),
            reference_time="2026-09-20T00:00:00Z")
        self.assertFalse(ok)
        self.assertEqual(reason, "signer-outside-validity-window:valid_from")

    def test_verifier_without_key_fails_closed(self):
        att, payload = self._att()
        with mock.patch.dict(os.environ, {}, clear=True):
            ok, reason = attest.verify(att, payload, dict(BOUND),
                                       self._signer_set())
        self.assertFalse(ok)
        self.assertEqual(reason, "verifier-has-no-key-for-signer")

    def test_tampered_bound_block_rejected(self):
        att, payload = self._att()
        with mock.patch.dict(os.environ, _keys_env(), clear=True):
            att["bound"]["policy_digest"] = "sha256:" + "f" * 64
            ok, reason = attest.verify(att, payload, dict(BOUND),
                                       self._signer_set())
        self.assertFalse(ok)
        self.assertEqual(reason, "signature-mismatch")


class TestSignerSetDigest(unittest.TestCase):
    def test_set_digest_binds_and_detects_swap(self):
        s1 = [{"key_id": "k1", "identity": "a"}]
        s2 = [{"key_id": "k1", "identity": "a"},
              {"key_id": "k2", "identity": "b"}]
        d1 = attest.signer_set_digest(s1)
        self.assertEqual(d1, attest.signer_set_digest(
            json.loads(canon.canon(s1))))
        self.assertNotEqual(d1, attest.signer_set_digest(s2))


class TestAntiRollback(unittest.TestCase):
    """coh-pol-02: bundles below the control-plane epoch floor are
    trusted-but-obsolete and rejected."""

    def test_bundle_at_floor_passes(self):
        attest.check_anti_rollback(3, 3)

    def test_bundle_above_floor_passes(self):
        attest.check_anti_rollback(5, 3)

    def test_bundle_below_floor_rejected(self):
        with self.assertRaises(attest.AttestationError) as c:
            attest.check_anti_rollback(2, 3)
        self.assertIn("policy rollback", str(c.exception))

    def test_older_bundle_without_epoch_rejected_when_floor_exists(self):
        with self.assertRaises(attest.AttestationError) as c:
            attest.check_anti_rollback(None, 3)
        self.assertIn("no epoch", str(c.exception))

    def test_no_floor_disables_enforcement(self):
        """Grandfathered/older contexts carry no floor: no enforcement."""
        attest.check_anti_rollback(None, None)
        attest.check_anti_rollback(0, None)

    def test_invalid_floor_rejected(self):
        with self.assertRaises(attest.AttestationError):
            attest.check_anti_rollback(1, -1)


class TestExecutionIdentity(unittest.TestCase):
    def test_absent_is_none(self):
        from hub.coherence import profiles
        self.assertIsNone(profiles.execution_identity({}))

    def test_valid_digest_accepted(self):
        from hub.coherence import profiles
        d = "sha256:" + "a" * 64
        self.assertEqual(profiles.execution_identity(
            {"DEVGATE_IMAGE_DIGEST": d}), d)

    def test_malformed_digest_is_error_not_null(self):
        from hub.coherence import profiles
        with self.assertRaises(profiles.ProfileRegistryError):
            profiles.execution_identity({"DEVGATE_IMAGE_DIGEST": "latest"})


class TestPipelineEmitsAttestationAndClaim(unittest.TestCase):
    """End-to-end through the real CLI: signing configured → attestation.json
    + decision.claim.json land beside result.json; the claim stops at
    OBSERVED (a producer cannot self-certify); --verify accepts the honest
    bundle and rejects a substituted one."""

    def _run_pipeline(self, td: Path, extra_env=None):
        req, out = fx.build_root(td, stage=2)
        env = {k: v for k, v in os.environ.items()
               if k not in (attest.SIGNER_KEYS_ENV,
                            attest.SIGNER_IDENTITY_ENV)}
        env.update(extra_env or {})
        import subprocess
        r = subprocess.run(
            [sys.executable, "-m", "hub.coherence", "--request", str(req)],
            capture_output=True, text=True, timeout=120, env=env)
        return r, Path(out)

    def test_unconfigured_signing_leaves_no_attestation(self):
        with tempfile.TemporaryDirectory() as td:
            r, out = self._run_pipeline(Path(td))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertFalse((out / "attestation.json").exists())

    def _pipeline_env(self, extra=None):
        env = {k: v for k, v in os.environ.items()
               if k not in (attest.SIGNER_KEYS_ENV,
                            attest.SIGNER_IDENTITY_ENV)}
        env.update(extra or {})
        return env

    def test_configured_signing_emits_verifiable_attestation(self):
        import subprocess
        key_id = attest.key_id_for(bytes.fromhex(KEY_HEX))
        signer_set = [{"key_id": key_id, "identity": IDENTITY}]
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            req, out = fx.build_root(tdp, stage=2)
            # The control plane approves the signer: patch the bundle, keep
            # the request's expected digest honest (identity, not authority).
            r = json.loads(req.read_text())
            polroot = Path(r["policy"]["root"])
            bundle = json.loads((polroot / "policy.json").read_text())
            bundle["approved_signers"] = signer_set
            (polroot / "policy.json").write_text(json.dumps(bundle))
            r["policy"]["expected_digest"] = canon.digest_obj(
                "policy/v1", bundle)
            req.write_text(json.dumps(r))
            signers_fp = tdp / "signers.json"
            signers_fp.write_text(json.dumps(signer_set))

            env = self._pipeline_env({
                attest.SIGNER_KEYS_ENV: json.dumps({IDENTITY: KEY_HEX}),
                attest.SIGNER_IDENTITY_ENV: IDENTITY,
                # Simulate the launcher's digest-pinned identity injection.
                "DEVGATE_IMAGE_DIGEST": "sha256:" + "9" * 64,
            })
            run = subprocess.run(
                [sys.executable, "-m", "hub.coherence", "--request",
                 str(req)],
                capture_output=True, text=True, timeout=120, env=env)
            self.assertEqual(run.returncode, 0, run.stderr)
            att_fp = out / "attestation.json"
            self.assertTrue(att_fp.exists(),
                            "configured signing must emit an attestation")
            # The decision payload carries no attestation material
            # (coh-ev-01): result.json's schema has no such field.
            self.assertNotIn("attestation", run.stdout)

            # Offline verification accepts the honest bundle...
            verify = subprocess.run(
                [sys.executable, "-m", "hub.coherence", "--verify",
                 str(out), "--signers", str(signers_fp)],
                capture_output=True, text=True, timeout=120, env=env)
            self.assertEqual(verify.returncode, 0, verify.stdout)
            self.assertIn("attestation OK", verify.stdout)

            # ...and rejects a substituted decision (statement swap under a
            # valid attestation).
            result_fp = out / "result.json"
            original = result_fp.read_bytes()
            forged = json.loads(original)
            forged["decision"] = "FAIL" if forged["decision"] != "FAIL" \
                else "PASS"
            result_fp.write_bytes(canon.canon(forged))
            verify2 = subprocess.run(
                [sys.executable, "-m", "hub.coherence", "--verify",
                 str(out), "--signers", str(signers_fp)],
                capture_output=True, text=True, timeout=120, env=env)
            self.assertEqual(verify2.returncode, 1)
            self.assertIn("statement-substitution", verify2.stdout)
            result_fp.write_bytes(original)

    def test_configured_but_unauthorized_signer_fails_closed(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), stage=2)
            # build_root's policy has approved_signers: [] — a configured
            # signer that policy does not approve must be a loud policy
            # error, never silent non-signing on a promotion run.
            run = subprocess.run(
                [sys.executable, "-m", "hub.coherence", "--request",
                 str(req)],
                capture_output=True, text=True, timeout=120,
                env=self._pipeline_env({
                    attest.SIGNER_KEYS_ENV: json.dumps({IDENTITY: KEY_HEX}),
                    attest.SIGNER_IDENTITY_ENV: IDENTITY,
                }))
            self.assertEqual(run.returncode, 31, run.stderr)
            envelope = json.loads((Path(out) / "result.json").read_text())
            self.assertEqual(envelope["decision"], "ERROR")
            self.assertIn("approved signer set",
                          envelope["error"]["reason"])

    def test_claim_stops_at_observed_and_validates(self):
        from hub.coherence import verification as V
        with tempfile.TemporaryDirectory() as td:
            r, out = self._run_pipeline(Path(td))
            self.assertEqual(r.returncode, 0, r.stderr)
            claim_fp = out / "decision.claim.json"
            digest_fp = out / "decision.claim.json.digest"
            self.assertTrue(claim_fp.exists())
            self.assertTrue(digest_fp.exists())
            claim = json.loads(claim_fp.read_text())
            self.assertEqual(claim["state"], V.OBSERVED)
            self.assertNotEqual(claim["state"], V.VERIFIED)
            self.assertEqual(digest_fp.read_text().strip(),
                             V.digest_claim(claim))
            # Digest-bound staleness: change a bound input → claim UNKNOWN.
            now = {role: digest for role, digest in claim["bound_digests"].items()}
            self.assertEqual(V.revalidate(claim, now), V.OBSERVED)
            now["subject"] = "sha256:" + "0" * 64
            self.assertEqual(V.revalidate(claim, now), V.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
