# // spec: coh-dec-01, coh-dec-04, coh-eval-02
"""Decision-matrix class semantics (round-8 spec audit): evaluator crash and
dependency-blocked required assertions are ERROR-execution per the frozen
matrix — they dominate every FAIL-class condition in the same run (tie-break
2) and are never converted to advisory. UNRESOLVED from a COMPLETED evaluation
stays FAIL-class. All fixtures synthetic (R9)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import evaluate, evaluators, package, result, schemacheck
from tests.fixtures.coherence import fixtures as fx

REPO = Path(__file__).resolve().parent.parent
SCHEMA = (REPO / "openspec/changes/devgate-spec-coherence-service"
          / "schemas/error-envelope.schema.json")


def _run(req_path: Path, out_dir: Path):
    """Invoke the real CLI; return (exit_code, parsed result or None)."""
    r = subprocess.run([sys.executable, "-m", "hub.coherence", "--request", str(req_path)],
                       capture_output=True, text=True, cwd=str(REPO))
    rp = out_dir / "result.json"
    parsed = json.loads(rp.read_text()) if rp.exists() else None
    return r.returncode, parsed


class TestErrorExecutionSignals(unittest.TestCase):
    """evaluate.run reports the first ERROR-execution condition separately
    from the ledger rows (which stay recorded UNRESOLVED)."""

    def test_evaluator_crash_signals_execution_error(self):
        def boom(assertion, pkg, subject_root, facts):
            raise RuntimeError("synthetic crash (R9)")

        with mock.patch.dict(evaluators.BUILTINS,
                              {"devgate.builtin.boom": boom}):
            a = fx.assertion(aid="crasher", evaluator={
                "id": "devgate.builtin.boom", "digest": "sha256:" + "a" * 64})
            out = evaluate.run([a], {}, ".")
        self.assertEqual(out["error"],
                         {"class": "execution",
                          "reason": "evaluator-crash:RuntimeError:crasher"})
        row = out["ledger"][0]
        self.assertEqual(row["outcome"], "UNRESOLVED")
        self.assertEqual(row["reason"], "evaluator-crash:RuntimeError")
        self.assertEqual(row["enforcement"], "BLOCK")

    def test_dependency_blocked_signals_execution_error(self):
        # The dependency ends UNRESOLVED by a COMPLETED evaluation (a missing
        # captured fact — FAIL-class), and the blocked dependent is the
        # ERROR-execution condition (frozen matrix).
        dep = fx.assertion(aid="dep", subjects=[{"kind": "captured-fact",
                                                 "fact_id": "fact.absent"}],
                           evaluator={"id": "devgate.builtin.captured-fact-consistency",
                                      "digest": "sha256:" + "a" * 64})
        main = fx.assertion(aid="main", deps=["dep"])
        out = evaluate.run([dep, main], {}, ".", captured_facts={})
        self.assertEqual(out["ledger"][0]["reason"],
                         "captured-fact-missing:fact.absent")
        self.assertEqual(out["error"],
                         {"class": "execution", "reason": "dependency-blocked:main"})

    def test_completed_unresolved_stays_fail_class(self):
        # The matrix's FAIL class is "UNRESOLVED (evaluation completed
        # cleanly)": a missing captured fact alongside an enforced VIOLATED
        # assertion is FAIL/20 — only ERROR-execution conditions dominate.
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), declared_name="other",
                                     approved_name="widget", stage=3)
            r = json.loads(req.read_text())
            pkg = package.resolve(r["openspec"]["root"])
            a_fact = fx.assertion(aid="fact.missing", subjects=[
                {"kind": "captured-fact", "fact_id": "fact.absent"}],
                evaluator={"id": "devgate.builtin.captured-fact-consistency",
                           "digest": "sha256:" + "a" * 64})
            ev = evaluate.run([a_fact, fx.assertion()], pkg,
                              r["subject"]["root"], captured_facts={})
        self.assertIsNone(ev["error"])
        decision, code = result.decide(ev["ledger"], 3)
        self.assertEqual((decision, code), ("FAIL", result.EXIT_FAIL))


class TestCrashDecisionMatrix(unittest.TestCase):
    """coh-dec-01 scenario: one required evaluator crashed and another
    produced an enforced VIOLATED finding — a single deterministic decision
    (ERROR/32) with both condition classes visible in the result."""

    def _mixed_run(self, base, name):
        crasher = fx.assertion(aid="crasher")
        # identity_consistency reads assertion["parameters"] first: a
        # parameters-less assertion is a real (KeyError) evaluator crash.
        del crasher["parameters"]
        req, out = fx.build_root(base / name, declared_name="other",
                                 approved_name="widget", stage=3,
                                 assertions=[crasher, fx.assertion()])
        return _run(req, out)

    def test_simultaneous_crash_and_violation_is_error32(self):
        with tempfile.TemporaryDirectory() as td:
            code, res = self._mixed_run(Path(td), "run")
        self.assertEqual(code, result.EXIT_EXECUTION)
        self.assertEqual(res["decision"], "ERROR")
        self.assertEqual(res["error"]["class"], "execution")
        self.assertEqual(res["error"]["reason"],
                         "evaluator-crash:KeyError:crasher")
        # Both condition classes stay visible (tie-break 2).
        by_id = {r["assertion_id"]: r for r in res["assertion_results"]}
        self.assertEqual(by_id["crasher"]["outcome"], "UNRESOLVED")
        self.assertEqual(by_id["product.identity"]["outcome"], "VIOLATED")

    def test_crash_envelope_validates_against_frozen_schema(self):
        with tempfile.TemporaryDirectory() as td:
            _, res = self._mixed_run(Path(td), "run")
        schema = json.loads(SCHEMA.read_text())
        self.assertEqual(schemacheck.validate(res, schema), [])

    def test_repeated_crash_runs_yield_the_same_decision(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            code1, res1 = self._mixed_run(base, "first")
            code2, res2 = self._mixed_run(base, "second")
        self.assertEqual((code1, code2), (32, 32))
        self.assertEqual(res1, res2, "same inputs, same canonical result")


if __name__ == "__main__":
    unittest.main()
