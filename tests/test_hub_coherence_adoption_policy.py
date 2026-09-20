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


class TestAdvisoryAgeEnforcementGap(unittest.TestCase):
    """coh-pol-03 ENFORCEMENT GAP (recorded, not yet implemented).

    The requirement: at maximum advisory age with no approved renewal, new
    AND existing required violations block per the central escalation
    policy. What actually ships today is the REPORTING half only —
    report.advisory_status() computes `expired` from advisory_started /
    advisory_expiry / max_advisory_age_days and surfaces it in the summary,
    but the ENFORCEMENT half is absent: adoption.evaluate() never receives
    the age data (nor the repo record it lives on) and never consults it, so
    an expired advisory does not by itself change any finding's enforcement.

    The remaining blocker is a genuine design question, not an oversight:
    the bundle's `stages` object carries `max_advisory_age_days` (a
    duration) but no field expressing WHAT the escalation should be — the
    spec's phrase "per the central escalation policy" has nothing to
    resolve against. Inventing that field is a control-plane policy
    decision, so it is escalated rather than guessed (same standing as the
    anti-rollback model, which was ratified before it was coded).

    These tests pin the CURRENT state so the gap cannot silently close
    unnoticed — and so that closing it flips them loudly.
    """

    def test_advisory_age_is_reported_but_not_enforced(self):
        # Reporting half: expiry is computed correctly from the trusted
        # evaluation_time.
        from hub.coherence import report
        record = {"stage": 1, "owner": "o",
                  "advisory_started": "2026-06-01T00:00:00Z",
                  "advisory_expiry": "2026-07-01T00:00:00Z"}
        status = report.advisory_status(record, 30, "2026-09-17T00:00:00Z")
        self.assertTrue(status["expired"])
        self.assertIn("coh-pol-03", status["notes"][0])
        # Enforcement half: evaluate() has no channel for age data at all.
        import inspect
        from hub.coherence import adoption
        params = set(inspect.signature(adoption.evaluate).parameters)
        self.assertFalse(
            params & {"max_advisory_age_days", "advisory_expiry",
                      "repo_record", "advisory_expired"},
            "adoption.evaluate gained an advisory-age channel; the "
            "coh-pol-03 enforcement half is being implemented and this "
            "gap test must be replaced by a behavioral spec test")

    def test_bundle_cannot_express_the_escalation(self):
        # The design blocker, pinned: a duration exists, a policy does not.
        import json
        from pathlib import Path
        repo = Path(__file__).resolve().parent.parent
        schema = json.loads((repo / "openspec" / "changes"
                             / "devgate-spec-coherence-service" / "schemas"
                             / "policy-bundle.schema.json").read_text())
        stages_props = schema["properties"]["stages"]["properties"]
        self.assertIn("max_advisory_age_days", stages_props)
        self.assertEqual(
            [k for k in stages_props if "escalat" in k.lower()], [],
            "the bundle now expresses an escalation policy; resolve its "
            "semantics and implement coh-pol-03's enforcement half")

if __name__ == "__main__":
    unittest.main()
