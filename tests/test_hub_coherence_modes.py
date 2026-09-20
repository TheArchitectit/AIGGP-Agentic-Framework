# // spec: coh-ctx-02, coh-pol-01, coh-pol-04, coh-eval-05
"""S6 Cycle A — the five modes ARE stages 0-4 (design.md, round-14).

Modes inventory/advisory/ratchet/enforced-core/enforced-full are names for
the authoritative adoption stage, one ordinal axis (coh-ctx-02: no input
ever carries an authoritative mode; the name is derived). Each stage
monotonically narrows the baseline shelter surface:

  0 inventory       all findings advisory (already shipped: stage < 2)
  1 advisory        named debt advisory + dwell cap (report.advisory_status)
  2 ratchet         unsheltered findings block (already shipped)
  3 enforced-core   baseline shelter STOPS APPLYING to the enforced-core
                    assertion classes; non-core named debt stays advisory
  4 enforced-full   baseline shelters nothing

Exceptions survive every stage (coh-eval-05 — a control-plane approval is
never silently overridden by a stage); expired exceptions block exactly as
before. The enforced-core set is central policy (the bundle's
`stages.enforced_core_classes`), defaulting to the Q2 freeze: the three
built-in evaluator classes. Core membership is matched by evaluator ID.

Dual-runnable (see __main__). All fixtures synthetic (R9).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import adoption, context, policy, report
from tests.fixtures.coherence import fixtures as fx


def _eval_row(aid="a1", version=1):
    return {"id": aid, "version": version,
            "evaluator": {"id": "devgate.builtin.identity-consistency",
                          "digest": "sha256:" + "a" * 64}}


def _finding(loc="b.md", vclass="identity-mismatch", aid="a1"):
    return {"assertion_id": aid, "finding_key": f"{aid}|{loc}|{vclass}",
            "subject_locations": [loc], "violation_class": vclass,
            "expected": "widget", "observed": "gadget"}


def _entry(loc="b.md", vclass="identity-mismatch", aid="a1", status="open"):
    return {"fingerprint": {"assertion_id": aid, "assertion_version": 1,
                            "subject_location": loc, "violation_key": vclass},
            "status": status}


def _ledger_row(aid="a1", outcome="VIOLATED"):
    return {"assertion_id": aid, "version": 1, "outcome": outcome,
            "reason": None, "enforcement": "BLOCK"}


def _evaluate(stage, planned=None, findings=None, baseline=None,
              exceptions=None, **kw):
    return adoption.evaluate(
        [_ledger_row()], findings if findings is not None else [_finding()],
        planned or [_eval_row()],
        baseline or [], exceptions or [], stage,
        "2026-09-17T00:00:00Z", **kw)


ID = "devgate.builtin.identity-consistency"
TRACE = "devgate.builtin.traceability-completeness"
CLAIM = "devgate.builtin.release-claim-consistency"
FACT = "devgate.builtin.captured-fact-consistency"


class TestModeLabels(unittest.TestCase):
    def test_the_five_names_are_stages_zero_to_four(self):
        self.assertEqual([context.mode_for_stage(s) for s in range(5)],
                         ["inventory", "advisory", "ratchet",
                          "enforced-core", "enforced-full"])

    def test_an_unauthoritative_stage_has_no_mode_name(self):
        # A name for an invalid stage would invent authority the stage
        # record does not carry.
        for bad in (5, -1, None, "2"):
            self.assertIsNone(context.mode_for_stage(bad))


class TestStage3CoreShelter(unittest.TestCase):
    def test_core_class_named_debt_loses_its_shelter_at_stage_3(self):
        out = _evaluate(3, baseline=[_entry()])
        self.assertEqual(out["findings"][0]["enforcement"], "BLOCK")
        self.assertTrue(out["blocked"])

    def test_non_core_named_debt_stays_advisory_at_stage_3(self):
        planned = [{"id": "a1", "version": 1,
                    "evaluator": {"id": FACT, "digest": "sha256:" + "f" * 64}}]
        out = _evaluate(3, planned=planned, baseline=[_entry()])
        self.assertEqual(out["findings"][0]["enforcement"], "ADVISORY")
        self.assertFalse(out["blocked"])

    def test_stage_2_core_debt_is_still_sheltered(self):
        # The ratchet is the ratchet: the mode change must not leak a stage
        # earlier than the design says (a guard that masks stage ordering).
        out = _evaluate(2, baseline=[_entry()])
        self.assertEqual(out["findings"][0]["enforcement"], "ADVISORY")
        self.assertFalse(out["blocked"])

    def test_active_exception_survives_stage_3(self):
        from tests.fixtures.coherence import fixtures as fx
        exc = [fx.exception_entry("a1", 1, "b.md", "identity-mismatch",
                                  expires_at="2027-01-01T00:00:00Z")]
        out = _evaluate(3, baseline=[_entry()], exceptions=exc)
        self.assertEqual(out["findings"][0]["enforcement"],
                         "EXCEPTION-ADVISORY")
        self.assertFalse(out["blocked"])

    def test_expired_exception_still_blocks_at_stage_3(self):
        from tests.fixtures.coherence import fixtures as fx
        exc = [fx.exception_entry("a1", 1, "b.md", "identity-mismatch",
                                  expires_at="2026-01-01T00:00:00Z")]
        out = _evaluate(3, baseline=[_entry()], exceptions=exc)
        self.assertEqual(out["findings"][0]["enforcement"], "BLOCK")
        self.assertTrue(out["blocked"])

    def test_explicit_core_set_overrides_the_default(self):
        planned = [{"id": "a1", "version": 1,
                    "evaluator": {"id": FACT, "digest": "sha256:" + "f" * 64}}]
        out = _evaluate(3, planned=planned, baseline=[_entry()],
                        core_classes={FACT})
        self.assertEqual(out["findings"][0]["enforcement"], "BLOCK")


class TestStage4FullShelterLoss(unittest.TestCase):
    def test_non_core_named_debt_blocks_at_stage_4(self):
        planned = [{"id": "a1", "version": 1,
                    "evaluator": {"id": FACT, "digest": "sha256:" + "f" * 64}}]
        out = _evaluate(4, planned=planned, baseline=[_entry()])
        self.assertEqual(out["findings"][0]["enforcement"], "BLOCK")
        self.assertTrue(out["blocked"])

    def test_active_exception_still_survives_stage_4(self):
        from tests.fixtures.coherence import fixtures as fx
        exc = [fx.exception_entry("a1", 1, "b.md", "identity-mismatch",
                                  expires_at="2027-01-01T00:00:00Z")]
        out = _evaluate(4, baseline=[_entry()], exceptions=exc)
        self.assertEqual(out["findings"][0]["enforcement"],
                         "EXCEPTION-ADVISORY")


class TestUnresolvedInvariant(unittest.TestCase):
    def test_unresolved_core_row_still_blocks_at_stage_3(self):
        # Already true at stage 2 (coh-eval-02); the mode work must not
        # accidentally route UNRESOLVED through the shelter logic.
        ledger = [{"assertion_id": "a1", "version": 1, "outcome": "UNRESOLVED",
                   "reason": "captured-fact-missing:f1", "enforcement": "BLOCK"}]
        out = adoption.evaluate(ledger, [], [_eval_row()], [_entry()], [],
                                3, "2026-09-17T00:00:00Z")
        self.assertEqual(out["ledger"][0]["enforcement"], "BLOCK")
        self.assertTrue(out["blocked"])


class TestPolicyCoreClasses(unittest.TestCase):
    def test_bundle_without_the_key_gets_the_q2_freeze(self):
        self.assertEqual(policy.enforced_core_classes({}),
                         {ID, TRACE, CLAIM})
        self.assertEqual(
            policy.enforced_core_classes({"stages":
                                          {"max_advisory_age_days": 30}}),
            {ID, TRACE, CLAIM})

    def test_bundle_list_becomes_the_set(self):
        b = {"stages": {"enforced_core_classes": [FACT]}}
        self.assertEqual(policy.enforced_core_classes(b), {FACT})

    def test_non_string_members_are_a_policy_error(self):
        for bad in ({"stages": {"enforced_core_classes": "x"}},
                    {"stages": {"enforced_core_classes": [ID, 7]}},
                    {"stages": {"enforced_core_classes": []}}):
            with self.assertRaises(policy.PolicyError):
                policy.enforced_core_classes(bad)


class TestSchemaAdmission(unittest.TestCase):
    def _validate(self, stages):
        from hub.coherence import schemacheck
        bundle = {"api_version": "devgate.spec-coherence.policy/v1",
                  "policy_version": "1", "bundle_epoch": 1,
                  "required_assertions": [],
                  "approved_evaluators": [], "approved_signers": [],
                  "stages": stages}
        # round-16: declaring `stages` owes an escalation policy, so a bundle
        # built to probe the core-set field must carry one — otherwise every
        # probe here returns the same dependentRequired error and the field
        # under test is masked.
        if stages is not None:
            bundle["advisory_escalation"] = {"on_expiry": "block"}
        return schemacheck.validate(bundle,
                                    schemacheck.load("policy-bundle.schema.json"))

    def test_valid_core_set_admits(self):
        self.assertEqual(self._validate(
            {"max_advisory_age_days": 30,
             "enforced_core_classes": [ID, FACT]}), [])

    def test_empty_core_set_is_rejected(self):
        # An empty core set silently collapses stage 3 into stage 2 — a
        # no-op mode reads like a mistake, not a decision. The default
        # (key absent) is how a bundle keeps the Q2 freeze.
        self.assertTrue(self._validate(
            {"max_advisory_age_days": 30, "enforced_core_classes": []}))

    def test_non_string_core_member_is_rejected(self):
        self.assertTrue(self._validate(
            {"max_advisory_age_days": 30, "enforced_core_classes": [7]}))


class TestReportModeLabel(unittest.TestCase):
    def test_summary_carries_the_mode_derived_from_the_context_stage(self):
        s = report.summarize(
            {"decision": "FAIL"},
            {"context_digest": "d", "semantics": "fresh-promotion",
             "evaluation_time": "2026-09-17T00:00:00Z", "stage": 3},
            {"stage": 3, "owner": "o"}, 30)
        self.assertEqual(s["mode"], "enforced-core")


if __name__ == "__main__":
    unittest.main()
