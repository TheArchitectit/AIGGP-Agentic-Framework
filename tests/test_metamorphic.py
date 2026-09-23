# fw-* audit infrastructure: differential & metamorphic testing.
"""Where expected outputs are hard to enumerate, invariants and metamorphic
relations must hold instead. These tests attack the framework's own modules
with transformations that should never change observable meaning:

  - serialization round-trips preserve digests (canon, claims, registry);
  - key order, whitespace and insertion order are invisible to digests;
  - idempotent operations (registry save, claim transitions, token verify)
    are stable under repetition;
  - deterministic pipelines (planning, result sorting, canonical JSON)
    produce byte-identical output for semantically identical input.

Each relation is documented with the defect class it guards against: a
violated relation here is not a test bug, it is a found correctness hole.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import canon, evidence, plan, policy, result, verification as V
from hub.coherence import evaluators


# --- fixtures ----------------------------------------------------------------

def _sample_claim():
    c = V.new_claim("c1", "ship the widget", actor="agent")
    V.transition(c, V.ATTEMPTED, reason="work started")
    V.transition(c, V.EXECUTED)
    V.transition(c, V.COMPLETED)
    V.bind(c, "code", "sha256:" + "a" * 64)
    V.attach_evidence(c, "evidence/findings/a1.json")
    return c


class TestCanonInvariants(unittest.TestCase):
    """canon is the trust root for every digest in the system."""

    SAMPLE = {
        "z": 1, "a": {"d": [1, 2, {"x": None}], "b": "text"},
        "m": True, "nested": {"deep": {"deeper": [False, None, "s"]}},
    }

    def test_key_order_is_invisible(self):
        reordered = {
            "a": {"b": "text", "d": [1, 2, {"x": None}]},
            "m": True, "z": 1, "nested": {"deep": {"deeper": [False, None, "s"]}},
        }
        self.assertEqual(canon.canon(self.SAMPLE), canon.canon(reordered))

    def test_digest_is_deterministic_across_reinvocations(self):
        d1 = canon.digest_obj("file/v1", self.SAMPLE)
        for _ in range(5):
            self.assertEqual(d1, canon.digest_obj("file/v1", self.SAMPLE))

    def test_json_round_trip_preserves_digest(self):
        """Serialize -> parse -> canonicalize is a fixed point."""
        raw = canon.canon(self.SAMPLE)
        parsed = json.loads(raw)
        self.assertEqual(raw, canon.canon(parsed))
        self.assertEqual(canon.digest_obj("file/v1", self.SAMPLE),
                         canon.digest_obj("file/v1", parsed))

    def test_role_separation_prevents_digest_confusion(self):
        """The same payload under different role tags must digest
        differently — a digest is evidence about a KIND of thing."""
        payload = b"identical bytes"
        digests = {canon.digest_bytes(tag, payload)
                   for tag in ("file/v1", "policy/v1", "context/v1")}
        self.assertEqual(len(digests), 3)

    def test_byte_change_is_always_visible(self):
        base = canon.digest_obj("file/v1", self.SAMPLE)
        for tampered in ({"z": 2}, {"a": "text"}, {"extra": 1}):
            mutated = dict(self.SAMPLE)
            mutated.update(tampered)
            self.assertNotEqual(base, canon.digest_obj("file/v1", mutated))

    def test_metamorphic_nested_array_splitting_changes_nothing(self):
        """[1, 2] vs [1, 2] constructed differently — list identity never
        leaks into canonical bytes."""
        a = canon.canon({"list": [1, 2]})
        b = canon.canon({"list": json.loads("[1, 2]")})
        self.assertEqual(a, b)


class TestClaimRoundTrip(unittest.TestCase):
    def test_claim_json_round_trip_preserves_semantics(self):
        """A claim serialized and restored must behave identically: state,
        staleness and digest are functions of content, not instance."""
        c = _sample_claim()
        restored = json.loads(canon.canon(c))
        now = {"code": "sha256:" + "a" * 64}
        self.assertEqual(V.revalidate(c, now), V.revalidate(restored, now))
        drifted = {"code": "sha256:" + "f" * 64}
        self.assertEqual(V.revalidate(c, drifted),
                         V.revalidate(restored, drifted))
        self.assertEqual(V.digest_claim(c), V.digest_claim(restored))

    def test_transition_log_is_append_only_under_successive_ops(self):
        """Transitions only grow; no operation truncates history."""
        c = _sample_claim()
        history = [t["to"] for t in c["transitions"]]
        V.verify_independently(c, lambda claim: (True, {}))
        after = [t["to"] for t in c["transitions"]]
        self.assertEqual(after[:len(history)], history)
        self.assertGreater(len(after), len(history))

    def test_idempotent_revalidation(self):
        c = _sample_claim()
        now = {"code": "sha256:" + "a" * 64}
        first = V.revalidate(c, now)
        for _ in range(10):
            self.assertEqual(first, V.revalidate(c, now))


class TestRegistryPersistence(unittest.TestCase):
    """hub.registry: save -> load round trips must be lossless, and repeated
    saves are idempotent (identical bytes) — a torn or shifting registry
    file would poison fleet state.

    (Kept to the coherence-side primitives here; the hub suite covers the
    registry class itself. This file asserts the JSONL-level invariants of
    append-only failure-registry entries instead.)
    """

    def test_failure_registry_line_round_trip(self):
        entry = {
            "failure_id": "FAIL-x", "timestamp": "2026-09-20T00:00:00Z",
            "category": "runtime", "severity": "high",
            "error_message": "boom", "root_cause": "why",
            "affected_files": ["a.py"], "fix_commit": "",
            "regression_pattern": "boom\\(", "prevention_rule": "never",
            "status": "resolved", "updated_at": "2026-09-20T00:00:00Z",
        }
        line = json.dumps(entry, ensure_ascii=False)
        restored = json.loads(line)
        self.assertEqual(entry, restored)
        self.assertNotIn("\n", line)

    def test_registry_entry_field_order_is_invisible(self):
        """Field order must not change what consumers extract."""
        e1 = {"a": 1, "b": 2}
        e2 = {"b": 2, "a": 1}
        self.assertEqual(canon.canon(e1), canon.canon(e2))


class TestPolicyOverlayMetamorphics(unittest.TestCase):
    """Overlay application: order and redundancy should not matter."""

    CENTRAL = {
        "api_version": "devgate.spec-coherence.policy/v1",
        "policy_version": "1", "min_bundle_epoch": 0,
        "required_assertions": [], "approved_evaluators": [],
        "approved_signers": [], "stages": {"max_advisory_age_days": 30},
    }
    ASSERTIONS = [
        {"id": "a1", "version": 1, "requirement_refs": ["r"], "owner": "o",
         "requirement": "r", "severity": "high", "dependencies": []},
        {"id": "a2", "version": 1, "requirement_refs": ["r"], "owner": "o",
         "requirement": "r", "severity": "medium", "dependencies": []},
    ]

    def test_disjoint_overlays_commute(self):
        """Raising a1 and raising a2 in either order yields the same tree."""
        ov_a = {"assertions": [{"id": "a1", "severity": "critical"}]}
        ov_b = {"assertions": [{"id": "a2", "severity": "high"}]}
        ab = policy.apply_overlay(
            policy.apply_overlay(self.ASSERTIONS, ov_a, self.CENTRAL),
            ov_b, self.CENTRAL)
        ba = policy.apply_overlay(
            policy.apply_overlay(self.ASSERTIONS, ov_b, self.CENTRAL),
            ov_a, self.CENTRAL)
        self.assertEqual(canon.canon(ab), canon.canon(ba))

    def test_noop_overlay_is_identity(self):
        out = policy.apply_overlay(self.ASSERTIONS, {}, self.CENTRAL)
        self.assertEqual(canon.canon(out), canon.canon(self.ASSERTIONS))

    def test_repeated_noop_overlay_is_idempotent(self):
        once = policy.apply_overlay(self.ASSERTIONS, {}, self.CENTRAL)
        twice = policy.apply_overlay(once, {}, self.CENTRAL)
        self.assertEqual(canon.canon(once), canon.canon(twice))

    def test_weakening_attempt_changes_nothing_but_raises(self):
        """A rejected overlay never leaves a half-applied mutation behind:
        the exception path must be side-effect free (rollback by
        construction)."""
        hostile = {"assertions": [
            {"id": "a1", "severity": "critical"},   # legal raise first
            {"id": "a1", "disabled": True},          # then the attack
        ]}
        central = dict(self.CENTRAL, required_assertions=["a1"])
        before = canon.canon(self.ASSERTIONS)
        with self.assertRaises(policy.OverlayError):
            policy.apply_overlay(self.ASSERTIONS, hostile, central)
        self.assertEqual(before, canon.canon(self.ASSERTIONS))


class TestPipelineDeterminism(unittest.TestCase):
    """Same input -> byte-identical canonical output, always."""

    def _pipeline_inputs(self):
        pkg = {"product": {"identity": {"name": "widget"}},
               "normative_requirements": {"r1": {"testable": True,
                                                 "assertion_ids": ["t1"]}}}
        assertion = {
            "id": "t1", "version": 1, "requirement_refs": ["r1"],
            "owner": "o", "requirement": "r",
            "subjects": [{"kind": "artifact-metadata",
                          "selector": "product.identity.name"}],
            "evaluator": {"id": "devgate.builtin.identity-consistency",
                          "digest": "sha256:" + "a" * 64},
            "parameters": {"approved_value_ref": "package:product.identity.name",
                           "normalization": "trim-casefold"},
            "severity": "high", "dependencies": [],
            "finding_key": ["assertion_id", "subject_location",
                            "violation_class"],
            "evidence": {"retention_days": 1},
        }
        return pkg, [assertion]

    def test_plan_is_deterministic(self):
        pkg, assertions = self._pipeline_inputs()
        p1 = plan.plan(assertions, [], requirements=pkg["normative_requirements"])
        p2 = plan.plan(list(reversed(assertions)), [],
                       requirements=pkg["normative_requirements"])
        self.assertEqual(canon.canon([a["id"] for a in p1]),
                         canon.canon([a["id"] for a in p2]))

    def test_evaluated_ledger_is_deterministic(self):
        pkg, assertions = self._pipeline_inputs()
        p1 = plan.plan(assertions, [], requirements=pkg["normative_requirements"])
        p2 = plan.plan(assertions, [], requirements=pkg["normative_requirements"])
        r1 = canon.canon(evaluate_run(p1, pkg))
        r2 = canon.canon(evaluate_run(p2, pkg))
        self.assertEqual(r1, r2)

    def test_result_sort_is_total(self):
        """Findings differing only in tie-breakers still sort stably:
        the sort key must be a total order or equal elements may flip."""
        findings = [
            {"assertion_id": "a", "subject_locations": ["x"],
             "finding_key": "a|x|v"},
            {"assertion_id": "a", "subject_locations": ["y"],
             "finding_key": "a|y|v"},
        ]
        s1 = result._sort_findings(list(reversed(findings)))
        self.assertEqual(canon.canon(s1),
                         canon.canon(result._sort_findings(findings)))

    def test_repeated_operations_are_idempotent(self):
        """Evaluate twice, seal twice: same inputs, same digests."""
        pkg, assertions = self._pipeline_inputs()
        planned = plan.plan(assertions, [],
                            requirements=pkg["normative_requirements"])
        out1 = evaluate_run(planned, pkg)
        out2 = evaluate_run(planned, pkg)
        self.assertEqual(canon.canon(out1), canon.canon(out2))


def evaluate_run(planned, pkg):
    from hub.coherence import evaluate
    return evaluate.run(planned, pkg, subject_root="/nonexistent-subject")


class TestEvidenceSealMetamorphics(unittest.TestCase):
    def test_seal_is_deterministic(self):
        """Same findings -> same manifest digest (sealing adds no time,
        host, or randomness)."""
        findings = [{
            "assertion_id": "a1", "finding_key": "a1|x|identity-mismatch",
            "outcome": "VIOLATED", "enforcement": "BLOCK", "severity": "high",
            "subject_locations": ["README.md"], "expected": "widget",
            "observed": "other", "evidence_refs": [],
        }]
        with tempfile.TemporaryDirectory() as t1, \
                tempfile.TemporaryDirectory() as t2:
            d1 = evidence.seal(json.loads(json.dumps(findings)), t1)
            d2 = evidence.seal(json.loads(json.dumps(findings)), t2)
            self.assertEqual(d1, d2)

    def test_verify_is_idempotent(self):
        findings = [{
            "assertion_id": "a1", "finding_key": "a1|x|identity-mismatch",
            "outcome": "VIOLATED", "enforcement": "BLOCK", "severity": "high",
            "subject_locations": ["README.md"], "expected": "w",
            "observed": "o", "evidence_refs": [],
        }]
        with tempfile.TemporaryDirectory() as td:
            d = evidence.seal(findings, td)
            for _ in range(5):
                self.assertTrue(evidence.verify(td, d))


class TestStatefulLifecycle(unittest.TestCase):
    """Sequences of operations, not isolated calls: create -> modify ->
    reload, execute -> fail -> retry, verify -> refute."""

    def test_claim_full_lifecycle(self):
        c = V.new_claim("life", "r")
        V.bind(c, "code", "sha256:" + "a" * 64)
        for s in (V.ATTEMPTED, V.EXECUTED, V.COMPLETED, V.TESTED, V.OBSERVED):
            V.transition(c, s)
        V.verify_independently(c, lambda claim: (True, {}))
        # ... later, the world moves on:
        self.assertEqual(V.revalidate(c, {"code": "sha256:" + "b" * 64}),
                         V.UNKNOWN)
        # recovery = a NEW claim, not editing the old one
        c2 = V.new_claim("life-2", "r")
        self.assertNotEqual(V.digest_claim(c), V.digest_claim(c2))

    def test_execute_fail_retry_succeed(self):
        c = V.new_claim("retry", "r")
        V.transition(c, V.ATTEMPTED)
        V.transition(c, V.FAILED, reason="first try failed")
        c2 = V.new_claim("retry-2", "r")
        for s in (V.ATTEMPTED, V.EXECUTED, V.COMPLETED, V.TESTED, V.OBSERVED):
            V.transition(c2, s)
        V.verify_independently(c2, lambda claim: (True, {}))
        self.assertEqual(c["state"], V.FAILED)
        self.assertEqual(c2["state"], V.VERIFIED)

    def test_registry_shape_survives_mutation_cycle(self):
        """log_failure-style entries appended repeatedly stay valid JSONL
        under the newline-repair rule (a writer that omitted the trailing
        newline must not corrupt the next entry)."""
        entries = [{"failure_id": f"FAIL-{i}", "n": i} for i in range(3)]
        blob = ""
        for e in entries:
            if blob and not blob.endswith("\n"):
                blob += "\n"
            blob += json.dumps(e) + "\n"
        restored = [json.loads(l) for l in blob.splitlines()]
        self.assertEqual(entries, restored)


if __name__ == "__main__":
    unittest.main()
