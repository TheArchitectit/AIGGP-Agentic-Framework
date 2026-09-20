# // spec: coh-pol-03, coh-pol-04, coh-pol-05, coh-eval-05
"""Adoption-and-policy behavior: the fingerprinted ratchet, severity
escalation of adopted debt, recurrence after remediation, and the recorded
advisory-age enforcement gap. Split out of the frozen conformance suite
(which keeps the Fixture A-F sweeps) when it breached the 600-line test
budget. Dual-runnable. All fixtures synthetic (R9).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import result
from tests.fixtures.coherence import fixtures as fx

REPO = Path(__file__).resolve().parent.parent


def _run(req_path: Path, out_dir: Path):
    """Invoke the real CLI; return (exit_code, parsed result or None)."""
    r = subprocess.run([sys.executable, "-m", "hub.coherence", "--request", str(req_path)],
                       capture_output=True, text=True, cwd=str(REPO),
                       env={**os.environ, **fx.cli_env()})
    rp = out_dir / "result.json"
    parsed = json.loads(rp.read_text()) if rp.exists() else None
    return r.returncode, parsed


class TestRatchetRecurrenceAfterRemediation(unittest.TestCase):
    """coh-pol-05: removed baseline entry whose fingerprint reappears
    must block. Status != "open" drops it from baseline_fps, so the
    reappearing fingerprint hits else -> BLOCK. Already holds by
    construction; pinned here."""

    def test_recurrence_after_remediation_blocks(self):
        finding = {"assertion_id": "a1",
                    "finding_key": "a1|README.md|identity-mismatch",
                    "subject_locations": ["README.md"],
                    "violation_class": "identity-mismatch",
                    "expected": "widget", "observed": "gadget"}
        baseline_rem = [fx.baseline_entry("a1", 1, "README.md",
                                             "identity-mismatch",
                                             status="remediated")]
        baseline_op = [fx.baseline_entry("a1", 1, "README.md",
                                            "identity-mismatch",
                                            status="open")]
        planned = [{"id": "a1", "version": 1}]
        from hub.coherence import adoption
        out_rem = adoption.evaluate(
            [{"assertion_id": "a1", "version": 1, "outcome": "VIOLATED",
              "reason": None, "enforcement": "BLOCK"}],
            [finding], planned, baseline_rem, [], stage=2,
            evaluation_time="2026-09-17T00:00:00Z")
        self.assertEqual(out_rem["findings"][0]["enforcement"], "BLOCK")
        self.assertTrue(out_rem["blocked"])
        out_op = adoption.evaluate(
            [{"assertion_id": "a1", "version": 1, "outcome": "VIOLATED",
              "reason": None, "enforcement": "BLOCK"}],
            [finding], planned, baseline_op, [], stage=2,
            evaluation_time="2026-09-17T00:00:00Z")
        self.assertEqual(out_op["findings"][0]["enforcement"], "ADVISORY")
        self.assertFalse(out_op["blocked"])


class TestRatchetSeverityEscalation(unittest.TestCase):
    """coh-pol-05 scenario: severity escalation of baseline debt.

    GIVEN a baseline violation whose assertion severity is RAISED by central
    policy, WHEN the next Stage 2 evaluation runs, THEN the escalated item
    blocks per central policy or requires a newly approved, expiring
    exception — it does NOT silently inherit advisory treatment.

    The data needed is already in evaluate()'s arguments: `planned` carries
    each assertion's current severity and each baseline entry carries the
    severity recorded at adoption (baseline-entry.schema.json). The gap is
    that nothing compares them — shelter is granted purely on fingerprint
    membership. Central policy states the floor in `assertion_severity_floor`.
    """

    AID = "devgate.builtin.captured-fact-consistency"

    def _finding(self):
        return {"assertion_id": "a1",
                "finding_key": "a1|README.md|identity-mismatch",
                "subject_locations": ["README.md"],
                "violation_class": "identity-mismatch",
                "expected": "widget", "observed": "gadget"}

    def _planned(self, severity):
        return [{"id": "a1", "version": 1, "severity": severity,
                 "evaluator": {"id": self.AID, "digest": "sha256:" + "f" * 64}}]

    def _ledger(self):
        return [{"assertion_id": "a1", "version": 1, "outcome": "VIOLATED",
                 "reason": None, "enforcement": "BLOCK"}]

    def _baseline(self, severity):
        entry = fx.baseline_entry("a1", 1, "README.md", "identity-mismatch",
                                  status="open")
        entry["severity"] = severity
        return [entry]

    def _evaluate(self, *, adopted, current, floor=None):
        from hub.coherence import adoption
        return adoption.evaluate(
            self._ledger(), [self._finding()], self._planned(current),
            self._baseline(adopted), [], stage=2,
            evaluation_time="2026-09-17T00:00:00Z",
            severity_floor=floor if floor is not None else {"a1": current})

    def test_escalated_baseline_debt_blocks_instead_of_sheltering(self):
        # Adopted at 'low', central policy now says 'high' -> blocks.
        out = self._evaluate(adopted="low", current="high")
        self.assertEqual(out["findings"][0]["enforcement"], "BLOCK")
        self.assertTrue(out["blocked"])

    def test_unescalated_baseline_debt_keeps_its_shelter(self):
        # Direction control: no escalation -> the ratchet still shelters.
        # Without this, "always BLOCK" would pass the test above.
        out = self._evaluate(adopted="high", current="high")
        self.assertEqual(out["findings"][0]["enforcement"], "ADVISORY")
        self.assertFalse(out["blocked"])

    def test_severity_downgrade_does_not_escalate(self):
        # A floor BELOW what was adopted is not an escalation; central
        # policy raising nothing must not manufacture a block.
        out = self._evaluate(adopted="critical", current="low")
        self.assertEqual(out["findings"][0]["enforcement"], "ADVISORY")
        self.assertFalse(out["blocked"])

    def test_escalated_item_with_active_exception_is_exception_advisory(self):
        # The spec's alternative: "or requires a newly approved, expiring
        # exception". An escalated item covered by an unexpired exception
        # is EXCEPTION-ADVISORY, not BLOCK — the exception still governs.
        from hub.coherence import adoption
        exc = [fx.exception_entry("a1", 1, "README.md", "identity-mismatch",
                                  expires_at="2027-01-01T00:00:00Z")]
        out = adoption.evaluate(
            self._ledger(), [self._finding()], self._planned("high"),
            self._baseline("low"), exc, stage=2,
            evaluation_time="2026-09-17T00:00:00Z",
            severity_floor={"a1": "high"})
        self.assertEqual(out["findings"][0]["enforcement"],
                         "EXCEPTION-ADVISORY")
        self.assertFalse(out["blocked"])

    def test_no_floor_declared_leaves_the_ratchet_untouched(self):
        # Backwards compatibility, BOTH ways "no floor" arrives: an explicit
        # empty mapping, and no parameter at all (the pre-slice call shape).
        # Escalation is central policy, never inferred — and a floor that is
        # absent for this assertion must not be treated as a low floor that
        # everything escalates above.
        from hub.coherence import adoption
        for kwargs in ({"severity_floor": {}}, {"severity_floor": None}):
            with self.subTest(**kwargs):
                out = adoption.evaluate(
                    self._ledger(), [self._finding()], self._planned("high"),
                    self._baseline("low"), [], stage=2,
                    evaluation_time="2026-09-17T00:00:00Z", **kwargs)
                self.assertEqual(out["findings"][0]["enforcement"], "ADVISORY")
                self.assertFalse(out["blocked"])

    def test_floor_naming_another_assertion_does_not_escalate_this_one(self):
        # A floor map that has no entry for THIS assertion is silence, not a
        # zero floor. An implementation defaulting the missing lookup (e.g.
        # rank.get(floor, 99)) would escalate every unlisted assertion.
        out = self._evaluate(adopted="low", current="high",
                             floor={"some-other-assertion": "high"})
        self.assertEqual(out["findings"][0]["enforcement"], "ADVISORY")
        self.assertFalse(out["blocked"])


class TestFixtureC_Exceptions(unittest.TestCase):
    def test_expired_exception_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            assertions = [fx.assertion(aid="assertion-0")]
            exc = [fx.exception_entry("assertion-0", 1, "README.md", "identity-mismatch",
                                      expires_at="2026-09-01T00:00:00Z")]  # before eval time
            req, out = fx.build_root(Path(td), declared_name="other", approved_name="widget",
                                     assertions=assertions, exceptions=exc, stage=2)
            code, res = _run(req, out)
            self.assertEqual(res["decision"], "FAIL")
            self.assertEqual(res["findings"][0]["enforcement"], "BLOCK")

    def test_active_exception_is_exception_advisory(self):
        with tempfile.TemporaryDirectory() as td:
            assertions = [fx.assertion(aid="assertion-0")]
            exc = [fx.exception_entry("assertion-0", 1, "README.md", "identity-mismatch",
                                      expires_at="2027-01-01T00:00:00Z")]
            req, out = fx.build_root(Path(td), declared_name="other", approved_name="widget",
                                     assertions=assertions, exceptions=exc, stage=2)
            code, res = _run(req, out)
            self.assertEqual(res["decision"], "ADVISORY")
            f = res["findings"][0]
            self.assertEqual(f["enforcement"], "EXCEPTION-ADVISORY")
            self.assertIn("exception_id", f)
            self.assertEqual(f["outcome"], "VIOLATED", "exception must not rewrite outcome")

    def test_wildcard_exception_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            assertions = [fx.assertion(aid="assertion-0")]
            exc = [fx.exception_entry("assertion-0", 1, "README.md", "identity-mismatch",
                                      expires_at="2027-01-01T00:00:00Z")]
            exc[0]["assertion_id"] = "*"   # wildcard
            req, out = fx.build_root(Path(td), declared_name="other", approved_name="widget",
                                     assertions=assertions, exceptions=exc, stage=2)
            code, res = _run(req, out)
            self.assertEqual(code, result.EXIT_POLICY)
            self.assertEqual(res["decision"], "ERROR")


class TestAdvisoryAgeEscalation(unittest.TestCase):
    """coh-pol-03 enforcement: exceeding the advisory cap removes the shelter.

    Ratified in design.md round-16 as a top-level `advisory_escalation`
    policy object beside the severity floor — not a `stages` field, because
    the cap is a duration while the escalation is a policy. These tests
    replace the gap tests that pinned the enforcement half's ABSENCE; the
    reporting half's own tests stay where they were.

    The escalation is a BOOLEAN the caller resolves from the trusted
    evaluation_time, so the ladder itself never computes an age — there is
    one clock and one reading of it.
    """

    AID = "devgate.builtin.captured-fact-consistency"
    STALE = "2026-06-01T00:00:00Z"      # well past any cap, against FIXED_TIME
    FRESH = "2026-09-16T00:00:00Z"      # one day before FIXED_TIME

    def _ledger(self):
        return [{"assertion_id": self.AID, "outcome": "VIOLATED"}]

    def _finding(self):
        return {"assertion_id": self.AID, "subject_locations": ["README.md"],
                "violation_class": "captured-fact-mismatch",
                "finding_key": f"{self.AID}|README.md|captured-fact-mismatch"}

    def _planned(self):
        return [{"id": self.AID, "version": 1, "evaluator": {"id": "e1"}}]

    def _baseline(self):
        return [fx.baseline_entry(self.AID, 1, "README.md",
                                  "captured-fact-mismatch")]

    def _evaluate(self, **kw):
        from hub.coherence import adoption
        kw.setdefault("exceptions", [])
        return adoption.evaluate(
            self._ledger(), [self._finding()], self._planned(),
            self._baseline(), kw.pop("exceptions"), kw.pop("stage", 2),
            kw.pop("evaluation_time", fx.FIXED_TIME), **kw)

    def test_expired_advisory_blocks_existing_debt(self):
        """The scenario's "existing" half: debt already named in the
        baseline loses its shelter when the cap is exceeded."""
        out = self._evaluate(advisory_expired=True)
        f = out["findings"][0]
        self.assertEqual(f["enforcement"], "BLOCK")
        self.assertTrue(out["blocked"])
        self.assertEqual(f["reason"], "advisory-expired:existing-debt")

    def test_intact_advisory_still_shelters_the_same_debt(self):
        """Direction control: without the expiry verdict, the SAME inputs
        stay ADVISORY. Without this, a ladder that blocked everything would
        pass the test above."""
        out = self._evaluate(advisory_expired=False)
        f = out["findings"][0]
        self.assertEqual(f["enforcement"], "ADVISORY")
        self.assertFalse(out["blocked"])
        self.assertNotIn("reason", f)

    def test_expiry_does_not_block_below_the_ratchet(self):
        """Stage 0/1 never block, expired or not — the stage<2 arm wins, so
        an expired advisory REPORTS but cannot gate before a ratchet exists."""
        out = self._evaluate(stage=1, advisory_expired=True)
        self.assertEqual(out["findings"][0]["enforcement"], "ADVISORY")
        self.assertFalse(out["blocked"])

    def test_unexpired_exception_still_covers_expired_advisories(self):
        """A renewal IS an ordinary unexpired exception (coh-eval-05), so it
        survives the cap: an approved extension softens, expiring the cap
        does not override written control-plane approval."""
        ex = fx.exception_entry(self.AID, 1, "README.md",
                                "captured-fact-mismatch",
                                expires_at="2026-12-31T00:00:00Z")
        out = self._evaluate(advisory_expired=True, exceptions=[ex])
        f = out["findings"][0]
        self.assertEqual(f["enforcement"], "EXCEPTION-ADVISORY")
        self.assertFalse(out["blocked"])

    def test_expired_exception_blocks_alongside_the_expired_cap(self):
        ex = fx.exception_entry(self.AID, 1, "README.md",
                                "captured-fact-mismatch",
                                expires_at="2026-01-01T00:00:00Z")
        out = self._evaluate(advisory_expired=True, exceptions=[ex])
        self.assertEqual(out["findings"][0]["enforcement"], "BLOCK")
        self.assertTrue(out["blocked"])

    def test_no_repository_record_never_escalates(self):
        """A caller that supplies no record must not be blocked by the cap it
        never opted into. The enforcement path reads a missing start as
        SILENCE; inferring an expiry from an absent field would gate every
        run that predates the regime (and would report a violation nobody
        committed). Nothing else in the suite pins this, so it is the guard's
        only tripwire."""
        from hub.coherence import report
        for stage in (1, 2, 3, 4):
            with self.subTest(stage=stage):
                age = report.advisory_age({"stage": stage}, 30, fx.FIXED_TIME)
                self.assertFalse(age["expired"])
                self.assertIsNone(age["advisory_age_days"])
        age = report.advisory_age({}, 30, fx.FIXED_TIME)
        self.assertFalse(age["expired"], "an empty record must not escalate")

    def test_inventory_stage_does_not_measure_age(self):
        """Stage 0 has no shelter to lose, so the cap is not measured there —
        and a stale record at inventory reads as unexpired, not as a
        violation."""
        from hub.coherence import report
        age = report.advisory_age({"stage": 0, "advisory_started": self.STALE},
                                  30, fx.FIXED_TIME)
        self.assertFalse(age["expired"])

    def test_enforcement_path_measures_age_past_the_advisory_stage(self):
        """The reporting view returns `expired: False` for stage != 1 with
        "cap does not apply"; the enforcement view must NOT, or the cap is
        inert for exactly the repositories coh-pol-03 targets (design.md
        round-16). Both readings are pinned here so a future unification of
        the two cannot silently pick the inert one."""
        from hub.coherence import report
        rec = {"stage": 2, "advisory_started": self.STALE}
        self.assertFalse(report.advisory_status(rec, 30, fx.FIXED_TIME)["expired"])
        self.assertTrue(report.advisory_age(rec, 30, fx.FIXED_TIME)["expired"])

    def test_expired_regression_is_not_labelled_existing_debt(self):
        """The reason prefix must be honest. Two ways it could lie, both
        pinned here: a fingerprint that was never in the baseline blocked as
        a REGRESSION (labelling it "existing-debt" would misreport the fleet
        signal), and a baseline entry escalated by central policy blocked for
        a DIFFERENT reason than plain expiry (labelling it "existing-debt"
        would hide the escalation)."""
        from hub.coherence import adoption
        other = {
            "assertion_id": "new.assertion", "subject_locations": ["README.md"],
            "violation_class": "identity-mismatch",
            "finding_key": "new.assertion|README.md|identity-mismatch"}
        out2 = adoption.evaluate(
            [{"assertion_id": "new.assertion", "outcome": "VIOLATED"}], [other],
            [{"id": "new.assertion", "version": 1, "evaluator": {"id": "e1"}}],
            self._baseline(), [], 2, fx.FIXED_TIME, advisory_expired=True)
        self.assertEqual(out2["findings"][0]["enforcement"], "BLOCK")
        self.assertNotIn("reason", out2["findings"][0])

        # Escalated baseline entry: the severity floor raised it, so the
        # block is an ESCALATION that expiry merely coincides with.
        out3 = self._evaluate(advisory_expired=True,
                              severity_floor={self.AID: "critical"})
        self.assertEqual(out3["findings"][0]["enforcement"], "BLOCK")
        self.assertEqual(out3["findings"][0]["reason"],
                         "advisory-expired:severity-escalated")


class TestAdvisoryEscalationPolicyRefusal(unittest.TestCase):
    """The bundle must express the escalation, or the run refuses (exit 31).

    A bundle naming a dwell limit with no consequence for exceeding it is
    incomplete configuration; silence must not read as "cap declared,
    nothing happens". Same standing as a missing policy_binding.
    """

    def _bundle(self, **kw):
        b = {"api_version": "devgate.spec-coherence.policy/v1",
             "policy_version": "1", "bundle_epoch": 0,
             "required_assertions": [], "approved_evaluators": [],
             "approved_signers": [],
             "stages": {"max_advisory_age_days": 30}}
        b.update(kw)
        return b

    def _refusal(self, bundle):
        from hub.coherence import policy
        with self.assertRaises(policy.PolicyError) as cm:
            policy.check_advisory_escalation(bundle)
        return str(cm.exception)

    def test_cap_without_escalation_refuses(self):
        self.assertIn("advisory-escalation:", self._refusal(self._bundle()))

    def test_ratified_bundle_is_accepted(self):
        from hub.coherence import policy
        pol = self._bundle(advisory_escalation={
            "on_expiry": "block",
            "renewal": {"requires": "central-approval", "max_extension_days": 30}})
        self.assertEqual(policy.check_advisory_escalation(pol),
                         pol["advisory_escalation"])

    def test_bundle_with_no_stages_has_nothing_to_escalate(self):
        from hub.coherence import policy
        b = self._bundle()
        del b["stages"]
        self.assertEqual(policy.check_advisory_escalation(b), {})

    def test_invented_enum_value_refuses(self):
        b = self._bundle(advisory_escalation={"on_expiry": "warn"})
        self.assertIn("on_expiry", self._refusal(b))

    def test_repository_cannot_renew_its_own_advisory(self):
        b = self._bundle(advisory_escalation={
            "on_expiry": "block",
            "renewal": {"requires": "repo-owner", "max_extension_days": 30}})
        self.assertIn("renewal.requires", self._refusal(b))

    def test_non_positive_extension_refuses(self):
        for bad in (0, -1, True, "30"):
            with self.subTest(bad=bad):
                b = self._bundle(advisory_escalation={
                    "on_expiry": "block",
                    "renewal": {"requires": "central-approval",
                                "max_extension_days": bad}})
                self.assertIn("max_extension_days", self._refusal(b))

    def test_malformed_shapes_refuse_rather_than_crash(self):
        for bad in ("block", [], 7):
            with self.subTest(bad=bad):
                self.assertIn("advisory-escalation:",
                              self._refusal(self._bundle(advisory_escalation=bad)))

    def test_schema_requires_the_escalation_when_the_cap_is_declared(self):
        """The refusal is also structural, so a bundle that never reaches the
        runtime check is still rejected at admission."""
        from hub.coherence import schemacheck
        schema = schemacheck.load("policy-bundle.schema.json")
        errs = schemacheck.validate(self._bundle(), schema)
        self.assertTrue(any("advisory_escalation" in e for e in errs), errs)
        ok = self._bundle(advisory_escalation={"on_expiry": "block"})
        self.assertEqual(schemacheck.validate(ok, schema), [])


class TestAdvisoryEscalationEndToEnd(unittest.TestCase):
    """Driven through the real CLI: the verdict is read from the CONTEXT's
    evaluation_time and the repository record the caller supplied."""

    AID = "product.identity"

    def _request(self, td, *, started, expiry=None, stage=2):
        """The drift must be BASELINE-NAMED debt, or it blocks as a plain
        regression and the expiry is never what decides the outcome."""
        rec = {"owner": "o", "advisory_started": started}
        if expiry:
            rec["advisory_expiry"] = expiry
        baseline = [fx.baseline_entry(self.AID, 1, "README.md",
                                      "identity-mismatch")]
        return fx.build_root(Path(td), declared_name="other",
                             approved_name="widget",
                             assertions=[fx.assertion(aid=self.AID)],
                             baseline=baseline, stage=stage,
                             repository=rec)

    def test_overdue_advisory_blocks_through_the_cli(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = self._request(td, started="2026-06-01T00:00:00Z")
            code, res = _run(req, out)
            self.assertEqual(code, result.EXIT_FAIL)
            self.assertEqual(res["decision"], "FAIL")
            blocking = [f for f in res["findings"]
                        if f["enforcement"] == "BLOCK"]
            self.assertEqual(len(blocking), 1)
            self.assertEqual(blocking[0]["reason"],
                             "advisory-expired:existing-debt")

    def test_recent_advisory_does_not_block(self):
        """Direction control: inside the cap, the same fixture is advisory.
        Without this, the test above would pass on a service that blocked
        unconditionally."""
        with tempfile.TemporaryDirectory() as td:
            req, out = self._request(td, started="2026-09-16T00:00:00Z")
            code, res = _run(req, out)
            self.assertEqual(res["decision"], "ADVISORY")

    def test_recorded_expiry_is_honoured_over_the_computed_cap(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = self._request(td, started="2026-09-16T00:00:00Z",
                                     expiry="2026-09-17T00:00:00Z")
            _, res = _run(req, out)
            self.assertEqual(res["decision"], "FAIL")

    def test_cap_declared_without_escalation_refuses_through_the_cli(self):
        """Exit 31 with the prefix — the refusal is reachable end to end, not
        only by calling the checker directly."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), advisory_escalation=None)
            code, res = _run(req, out)
            self.assertEqual(code, result.EXIT_POLICY)
            self.assertEqual(res["decision"], "ERROR")
            self.assertIn("advisory-escalation:", res["error"]["reason"])


if __name__ == "__main__":
    unittest.main()
