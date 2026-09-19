# // spec: coh-eval-03, coh-eval-05
"""C2 — multi-finding ledger accuracy (round-9 disposition, S5 Cycle C2).

The engine emits zero-or-many findings per assertion (design.md section 8),
and `adoption.evaluate` mirrored each VIOLATED ledger row from
`by_aid = {f["assertion_id"]: f for f in findings}` — a dict comprehension
that keeps whichever finding was inserted LAST. Two findings of one assertion
(one baselined ADVISORY, one regression BLOCK) therefore rendered a row whose
`enforcement` depended on evaluator iteration order: sometimes correct,
sometimes silently ADVISORY on a row that hides a blocking finding.

Blocking itself was never wrong — the ladder computes `blocked` per finding
(round-9: "not fail-open") — so this is a report-accuracy defect: the ledger
is the human/CI-facing artifact, and a FAIL decision paired with a ledger row
reading ADVISORY tells the reader the run blocked on findings it does not
show. Fix: the row mirrors the STRICTEST enforcement across all of its
assertion's findings, and when softer siblings are collapsed away the row's
`reason` names them, so the single displayed row is honest about what it
represents. Decision output is invariant across every case here (the matrix
gates on `blocked`, not the row's display) — each test asserts exactly that.

Dual-runnable (see __main__ below). All fixtures synthetic (R9).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import adoption, result
from tests.fixtures.coherence import fixtures as fx


def _finding(loc, vclass="identity-mismatch", aid="a1"):
    """A finding as evaluators._mk emits it, pre-ladder (no enforcement yet —
    adoption.evaluate assigns it from the baseline/exception ladder)."""
    return {"assertion_id": aid, "finding_key": f"{aid}|{loc}|{vclass}",
            "subject_locations": [loc], "violation_class": vclass,
            "expected": "widget", "observed": "gadget"}


def _entry(loc, vclass="identity-mismatch", aid="a1"):
    """Open baseline entry naming one finding's fingerprint (coh-pol-04)."""
    return {"fingerprint": {"assertion_id": aid, "assertion_version": 1,
                            "subject_location": loc, "violation_key": vclass},
            "status": "open"}


def _row(aid="a1"):
    """The ledger row evaluate.run builds for a VIOLATED assertion (pre-
    adoption enforcement is provisional; adoption overwrites it)."""
    return {"assertion_id": aid, "version": 1, "outcome": "VIOLATED",
            "reason": None, "enforcement": "BLOCK"}


def _evaluate(findings, baseline, stage=2):
    return adoption.evaluate([_row()], findings, [{"id": "a1", "version": 1}],
                             baseline, [], stage=stage,
                             evaluation_time="2026-09-17T00:00:00Z")


class TestStrictestMirror(unittest.TestCase):
    def test_block_row_survives_when_regression_is_inserted_last(self):
        # Order [baselined-ADVISORY, regression-BLOCK]: pre-fix the dict kept
        # the BLOCK (accidentally correct). Must stay BLOCK after the fix.
        out = _evaluate([_finding("a.md"), _finding("b.md")],
                        [_entry("a.md")])
        self.assertEqual(out["ledger"][0]["enforcement"], "BLOCK")

    def test_block_row_survives_when_regression_is_inserted_first(self):
        """The collapse, pinned: with the regression FIRST and the baselined
        debt last, insertion order used to render an ADVISORY row over a run
        that is blocking. The row must mirror the strictest finding."""
        out = _evaluate([_finding("b.md"), _finding("a.md")],
                        [_entry("a.md")])
        self.assertEqual(out["ledger"][0]["enforcement"], "BLOCK",
                         "a blocking finding must never be hidden behind an "
                         "ADVISORY sibling in the displayed row")
        self.assertTrue(out["blocked"])

    def test_display_and_decision_agree_in_both_orders(self):
        """The defect was order-dependent display; the decision was always
        FAIL. After the fix both orders render identically, and the decision
        is unchanged either way — the fix is display-accuracy, not matrix."""
        renders = []
        for order in ([_finding("a.md"), _finding("b.md")],
                      [_finding("b.md"), _finding("a.md")]):
            out = _evaluate(order, [_entry("a.md")])
            row = out["ledger"][0]
            decision, code = result.decide(out["ledger"], stage=2,
                                           blocked=out["blocked"])
            self.assertEqual((decision, code), ("FAIL", result.EXIT_FAIL))
            renders.append((row["enforcement"], row["reason"], decision))
        self.assertEqual(renders[0], renders[1],
                         "ledger rendering must not depend on finding order")


class TestReasonNamesCollapsedSiblings(unittest.TestCase):
    def test_softer_siblings_are_named_in_the_reason(self):
        out = _evaluate([_finding("b.md"), _finding("a.md")], [_entry("a.md")])
        reason = out["ledger"][0]["reason"]
        self.assertIsNotNone(reason,
                             "a row collapsing a softer sibling must say so")
        self.assertIn("multi-finding:2", reason)
        self.assertIn("mirrors:BLOCK", reason)
        self.assertIn("softer:ADVISORYx1", reason)

    def test_uniform_findings_leave_the_reason_untouched(self):
        # Two BLOCK findings render a BLOCK row that hides nothing softer —
        # no reason needed, and inventing one would be noise in the report.
        out = _evaluate([_finding("a.md"), _finding("b.md")], [])
        self.assertEqual(out["ledger"][0]["enforcement"], "BLOCK")
        self.assertIsNone(out["ledger"][0]["reason"])

    def test_all_advisory_row_stays_advisory_without_a_reason(self):
        out = _evaluate([_finding("a.md"), _finding("b.md")],
                        [_entry("a.md"), _entry("b.md")])
        self.assertEqual(out["ledger"][0]["enforcement"], "ADVISORY")
        self.assertIsNone(out["ledger"][0]["reason"])
        self.assertFalse(out["blocked"])

    def test_exception_advisory_counts_as_stricter_than_advisory(self):
        # EXCEPTION-ADVISORY over plain ADVISORY hides a scoped exception —
        # the row must mirror it and name the plain-debt sibling.
        exc = [fx.exception_entry("a1", 1, "b.md", "identity-mismatch",
                                  expires_at="2027-01-01T00:00:00Z")]
        out = adoption.evaluate([_row()],
                                [_finding("b.md"), _finding("a.md")],
                                [{"id": "a1", "version": 1}],
                                [_entry("a.md")], exc, stage=2,
                                evaluation_time="2026-09-17T00:00:00Z")
        self.assertEqual(out["ledger"][0]["enforcement"], "EXCEPTION-ADVISORY")
        self.assertIn("softer:ADVISORYx1", out["ledger"][0]["reason"])
        self.assertFalse(out["blocked"])


class TestSingleFindingUnaffected(unittest.TestCase):
    def test_one_advisory_finding_still_does_not_block(self):
        # The pre-existing single-finding contract (schema suite): baseline-
        # named debt renders ADVISORY, not blocked — the fix must not turn
        # display strictness into a new blocking source.
        out = _evaluate([_finding("a.md")], [_entry("a.md")])
        self.assertEqual(out["ledger"][0]["enforcement"], "ADVISORY")
        self.assertFalse(out["blocked"])
        self.assertIsNone(out["ledger"][0]["reason"])

    def test_no_detail_path_is_untouched(self):
        out = _evaluate([], [])
        self.assertEqual(out["ledger"][0]["enforcement"], "BLOCK")
        self.assertEqual(out["ledger"][0]["reason"],
                         "violation-without-finding-detail")
        self.assertTrue(out["blocked"])


class TestCliLedgerRow(unittest.TestCase):
    """End-to-end through the real CLI: identity_consistency emits findings in
    subject order, so subjects [b.md, a.md] with a.md baselined puts the
    regression FIRST and the named debt LAST — the exact order that rendered
    an ADVISORY row over a FAILing run. The sealed result must show the row
    as BLOCK, name the collapsed sibling, and stay result.schema-valid."""

    def test_fail_run_row_reports_collapsed_advisory_sibling(self):
        import json
        import os
        import subprocess
        import tempfile
        from hub.coherence import result, schemacheck
        REPO = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as td:
            a = fx.assertion(
                subjects=[{"kind": "file", "path": "b.md"},
                          {"kind": "file", "path": "a.md"}])
            base = [fx.baseline_entry(a["id"], 1, "a.md", "identity-mismatch")]
            req, out = fx.build_root(
                Path(td), declared_name="widget", approved_name="gadget",
                assertions=[a], baseline=base, stage=2,
                subject_files={"a.md": "# product: widget\n",
                               "b.md": "# product: widget\n"})
            r = subprocess.run(
                [sys.executable, "-m", "hub.coherence", "--request", str(req)],
                capture_output=True, text=True, cwd=str(REPO),
                env={**os.environ, **fx.cli_env()})
            res = json.loads((out / "result.json").read_text())
            self.assertEqual(res["decision"], "FAIL", r.stderr)
            row = next(e for e in res["assertion_results"]
                       if e["outcome"] == "VIOLATED")
            self.assertEqual(row["enforcement"], "BLOCK",
                             "a FAILing row must not display ADVISORY")
            self.assertIn("multi-finding:2", row["reason"])
            self.assertIn("softer:ADVISORYx1", row["reason"])
            errs = schemacheck.validate(res, schemacheck.load("result.schema.json"))
            self.assertEqual(errs, [], f"ledger row violates result schema: {errs}")


if __name__ == "__main__":
    unittest.main()
