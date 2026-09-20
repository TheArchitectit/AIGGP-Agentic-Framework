# fw-* audit infrastructure: Evidence & Proof Architecture tests.
"""Evidence integrity: the claim lifecycle can distinguish attempted ->
executed -> completed -> tested -> observed -> verified, refuses to promote
agent claims into proof, goes stale when the world changes, and fails closed
against every tamper vector tried so far.

The negative half of each case is the point: anything that SHOULD be
rejected is asserted to be rejected. A verification system whose refusals
are untested is a rubber stamp.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import canon, evidence, verification as V


def _seal_bundle(td: Path):
    findings = [{
        "assertion_id": "a1", "finding_key": "a1|x|identity-mismatch",
        "outcome": "VIOLATED", "enforcement": "BLOCK", "severity": "high",
        "subject_locations": ["README.md"], "expected": "widget",
        "observed": "other", "evidence_refs": [],
    }]
    return evidence.seal(findings, str(td))


class TestStateLadder(unittest.TestCase):
    def test_ladder_walk_forward(self):
        c = V.new_claim("c1", "requirement text")
        for expected in (V.PLANNED, V.ATTEMPTED, V.EXECUTED, V.COMPLETED,
                         V.TESTED, V.OBSERVED):
            V.transition(c, expected, reason="progress")
            self.assertEqual(c["state"], expected)
        self.assertNotEqual(c["state"], V.VERIFIED)  # not without independent check

    def test_skip_is_rejected(self):
        c = V.new_claim("c1", "r")
        with self.assertRaises(V.VerificationError):
            V.transition(c, V.TESTED)  # REQUESTED -> TESTED skips the ladder

    def test_self_certification_is_rejected(self):
        """The actor cannot declare its own work VERIFIED — ever."""
        c = V.new_claim("c1", "r")
        V.transition(c, V.PLANNED)
        V.transition(c, V.ATTEMPTED)
        V.transition(c, V.EXECUTED)
        V.transition(c, V.COMPLETED)
        with self.assertRaises(V.VerificationError):
            V.transition(c, V.VERIFIED)
        self.assertEqual(c["state"], V.COMPLETED)

    def test_agent_message_alone_cannot_reach_verified(self):
        """End-to-end shape of the classic failure: the agent says 'done and
        tested'. Recording that as COMPLETED+TESTED requires the ladder, and
        VERIFIED is unreachable through the public transition API — only the
        verify_independently path may set it. (Whether a given verifier
        callable is truly independent is a caller-side property; the module
        enforces that the self-service API does not exist.)"""
        c = V.new_claim("c1", "r", actor="agent")
        V.transition(c, V.ATTEMPTED, reason="agent reports work done")
        V.transition(c, V.EXECUTED, reason="agent ran to a stop")
        V.transition(c, V.COMPLETED, reason="agent reports completion")
        with self.assertRaises(V.VerificationError):
            V.transition(c, V.VERIFIED,
                         reason="agent says its own tests pass")
        self.assertNotEqual(c["state"], V.VERIFIED)

    def test_unknown_cannot_be_promoted(self):
        c = V.new_claim("c1", "r")
        V.transition(c, V.UNKNOWN, reason="lost track")
        with self.assertRaises(V.VerificationError):
            V.transition(c, V.VERIFIED)
        with self.assertRaises(V.VerificationError):
            V.transition(c, V.COMPLETED)  # no sideways resurrection either

    def test_incomplete_work_reports_failed(self):
        c = V.new_claim("c1", "r")
        V.transition(c, V.ATTEMPTED)
        V.transition(c, V.FAILED, reason="tests failed")
        self.assertEqual(V.revalidate(c, {}), V.FAILED)

    def test_reported_completion_still_walks_the_ladder(self):
        """'Agent says done' from ATTEMPTED must pass through EXECUTED: an
        actor cannot jump straight to COMPLETED without a recorded run."""
        c = V.new_claim("c1", "r", actor="agent")
        V.transition(c, V.ATTEMPTED, reason="agent started")
        with self.assertRaises(V.VerificationError):
            V.transition(c, V.COMPLETED, reason="agent reports done")


class TestIndependentVerification(unittest.TestCase):
    def _worked_claim(self):
        c = V.new_claim("c1", "r")
        for s in (V.PLANNED, V.ATTEMPTED, V.EXECUTED, V.COMPLETED, V.TESTED,
                  V.OBSERVED):
            V.transition(c, s)
        return c

    def test_passing_independent_check_verifies(self):
        calls = []

        def verifier(claim):
            calls.append(claim["claim_id"])
            return True, {"executed": ["pytest -q"], "seen": "420 passed"}

        c = self._worked_claim()
        V.verify_independently(c, verifier)
        self.assertEqual(c["state"], V.VERIFIED)
        self.assertEqual(calls, ["c1"])
        self.assertTrue(c["independent_verification"]["ok"])
        self.assertEqual(c["independent_verification"]["observation"]["seen"],
                         "420 passed")

    def test_failing_independent_check_records_failure(self):
        c = self._worked_claim()
        V.verify_independently(
            c, lambda claim: (False, {"seen": "2 failed"}))
        self.assertEqual(c["state"], V.FAILED)
        self.assertFalse(c["independent_verification"]["ok"])
        # The negative observation is retained, not swallowed:
        self.assertEqual(c["independent_verification"]["observation"]["seen"],
                         "2 failed")

    def test_exception_in_verifier_propagates(self):
        """A verifier that crashes must not be mistaken for a pass OR a
        silently-swallowed fail."""
        def boom(claim):
            raise RuntimeError("verifier exploded")
        c = self._worked_claim()
        with self.assertRaises(RuntimeError):
            V.verify_independently(c, boom)
        self.assertNotEqual(c["state"], V.VERIFIED)
        self.assertNotEqual(c["state"], V.FAILED)

    def test_refutation_of_verified_claim_is_legal(self):
        """New evidence may refute an earlier VERIFIED claim (VERIFIED ->
        FAILED), but never via a quiet edit — the transition is logged."""
        c = self._worked_claim()
        V.verify_independently(c, lambda claim: (True, {}))
        self.assertEqual(c["state"], V.VERIFIED)
        V.transition(c, V.FAILED, reason="independent re-check refutes")
        self.assertEqual(c["state"], V.FAILED)
        self.assertEqual(c["transitions"][-1]["to"], V.FAILED)


class TestStaleness(unittest.TestCase):
    def _verified_claim(self):
        c = V.new_claim("c1", "r", subject_digest="sha256:" + "a" * 64)
        for s in (V.PLANNED, V.ATTEMPTED, V.EXECUTED, V.COMPLETED, V.TESTED,
                  V.OBSERVED):
            V.transition(c, s)
        V.verify_independently(c, lambda claim: (True, {}))
        V.bind(c, "code", "sha256:" + "b" * 64)
        V.bind(c, "config", "sha256:" + "c" * 64)
        return c

    def test_fresh_digests_keep_state(self):
        c = self._verified_claim()
        now = {"code": "sha256:" + "b" * 64, "config": "sha256:" + "c" * 64}
        self.assertEqual(V.staleness(c, now), [])
        self.assertEqual(V.revalidate(c, now), V.VERIFIED)

    def test_changed_code_demotes_to_unknown(self):
        """The core stale-evidence rule: modify the code after verification
        and the claim no longer counts as verified — it is UNKNOWN."""
        c = self._verified_claim()
        now = {"code": "sha256:" + "d" * 64, "config": "sha256:" + "c" * 64}
        self.assertEqual(V.staleness(c, now), ["code"])
        self.assertEqual(V.revalidate(c, now), V.UNKNOWN)

    def test_config_drift_alone_is_enough(self):
        c = self._verified_claim()
        now = {"code": "sha256:" + "b" * 64, "config": "sha256:" + "z" * 64}
        self.assertEqual(V.revalidate(c, now), V.UNKNOWN)

    def test_unobserved_anchor_is_stale(self):
        """A bound role missing from the observed world is drift, not OK."""
        c = self._verified_claim()
        self.assertEqual(V.staleness(c, {"code": "sha256:" + "b" * 64}),
                         ["config"])

    def test_history_is_not_rewritten(self):
        """revalidate reports reality; it never rewrites the record. The
        claim still says what was verified, against what digests."""
        c = self._verified_claim()
        V.revalidate(c, {"code": "sha256:" + "d" * 64})
        self.assertEqual(c["state"], V.VERIFIED)  # record intact
        self.assertEqual(c["bound_digests"]["code"], "sha256:" + "b" * 64)


class TestClaimSealing(unittest.TestCase):
    def test_claim_digest_is_stable_and_tamper_evident(self):
        c = V.new_claim("c1", "r")
        d1 = V.digest_claim(c)
        d2 = V.digest_claim(c)
        self.assertEqual(d1, d2)
        c2 = V.new_claim("c1", "r")
        c2["actor"] = "someone-else"  # any edit changes the digest
        self.assertNotEqual(d1, V.digest_claim(c2))

    def test_claim_round_trips_through_canonical_json(self):
        c = V.new_claim("c1", "r", actor="agent")
        V.transition(c, V.ATTEMPTED, reason="work")
        V.bind(c, "code", "sha256:" + "a" * 64)
        V.attach_evidence(c, "evidence/findings/a1.json")
        restored = json.loads(canon.canon(c))
        self.assertEqual(V.digest_claim(restored), V.digest_claim(c))


class TestEvidenceBundlePlusClaim(unittest.TestCase):
    """The full loop: findings sealed, claim bound to the bundle digest,
    bundle tamper rejected, validator contract holds."""

    def test_bundle_tamper_invalidates_bound_claim(self):
        """fw-ev-05: a claim anchored to the manifest digest alone does NOT
        detect tamper of an inner evidence file (the manifest is unchanged) —
        that is why claims anchor to the whole-tree commitment, and why the
        bundle itself must still be re-verified (digest equality of an index
        is not content integrity of the indexed files)."""
        with tempfile.TemporaryDirectory() as td:
            digest = _seal_bundle(Path(td))
            commitment = V.content_commitment(td)
            c = V.new_claim("c1", "r")
            for s in (V.ATTEMPTED, V.EXECUTED, V.COMPLETED, V.TESTED,
                      V.OBSERVED):
                V.transition(c, s)
            V.bind(c, "evidence-manifest", digest)
            V.bind(c, "evidence-tree", commitment)
            now = {"evidence-manifest": digest,
                   "evidence-tree": V.content_commitment(td)}
            self.assertEqual(V.revalidate(c, now), V.OBSERVED)
            # Digest-string anchors alone cannot see inner tamper:
            p = Path(td) / "evidence" / "findings" / "a1.json"
            p.write_text('{"tampered":true}')
            self.assertFalse(evidence.verify(td, digest))
            # ...but re-observing the tree DOES — the claim goes stale:
            now_after = {"evidence-manifest": digest,
                         "evidence-tree": V.content_commitment(td)}
            self.assertEqual(V.revalidate(c, now_after), V.UNKNOWN)

    def test_summarize_never_averages_into_success(self):
        claims = []
        for i in range(3):
            c = V.new_claim(f"c{i}", "r")
            for s in (V.ATTEMPTED, V.EXECUTED, V.COMPLETED):
                V.transition(c, s)
            claims.append(c)
        vc = V.new_claim("v", "r")
        for s in (V.ATTEMPTED, V.EXECUTED, V.COMPLETED, V.TESTED, V.OBSERVED):
            V.transition(vc, s)
        V.verify_independently(vc, lambda claim: (True, {}))
        claims.append(vc)
        summary = V.summarize(claims)
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["verified"], 1)
        self.assertEqual(summary["unverified"], 3)


if __name__ == "__main__":
    unittest.main()
