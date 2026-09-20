# fw-* audit infrastructure: resource & economic governance tests.
"""Budgets must fail predictably and recoverably; runaway patterns must be
detectable before they consume the machine. The negative cases are the
point: a budget that cannot actually stop work is decoration.
"""
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import resource_limits as rl


class TestWallClockBudget(unittest.TestCase):
    def test_budget_passes_when_within_allowance(self):
        b = rl.WallClockBudget(10.0)
        b.check("unit of work")
        self.assertGreater(b.remaining(), 0.0)

    def test_budget_expires_controllably(self):
        b = rl.WallClockBudget(0.05)
        time.sleep(0.08)
        with self.assertRaises(rl.BudgetExceeded) as c:
            b.check("the expensive part")
        self.assertIn("wall-clock", str(c.exception))
        self.assertIn("the expensive part", str(c.exception))

    def test_zero_or_negative_budget_is_rejected(self):
        for bad in (0, -1):
            with self.assertRaises(ValueError):
                rl.WallClockBudget(bad)

    def test_exhaustion_is_recoverable_state_not_a_crash(self):
        """After BudgetExceeded, the budget object still answers queries —
        callers can report accurate state while unwinding."""
        b = rl.WallClockBudget(0.02)
        time.sleep(0.04)
        with self.assertRaises(rl.BudgetExceeded):
            b.check()
        self.assertGreaterEqual(b.elapsed(), 0.02)
        self.assertEqual(b.remaining(), 0.0)


class TestRunCapped(unittest.TestCase):
    def test_normal_command_measured(self):
        r = rl.run_capped([sys.executable, "-c", "print('hello')"],
                          timeout=30)
        self.assertEqual(r["exit"], 0)
        self.assertIn("hello", r["stdout"])
        self.assertFalse(r["truncated"])
        self.assertIsNone(r["stopped"])

    def test_runaway_output_is_truncated_not_absorbed(self):
        """A process spewing output forever must be capped — the harness
        survives with truncated output and a flag, not OOM."""
        bomb = "print('x' * 1000)\n" * 5000  # ~5MB
        r = rl.run_capped([sys.executable, "-c", bomb],
                          timeout=30, max_output=100_000)
        self.assertEqual(r["exit"], 0)
        self.assertTrue(r["truncated"])
        self.assertLessEqual(len(r["stdout"]), 100_000 + 200)

    def test_infinite_loop_is_stopped_by_timeout(self):
        """A hung child produces a CONTROLLED stop: exit=None, stopped flag,
        and the runner returns (no hang, no exception escape)."""
        r = rl.run_capped([sys.executable, "-c", "while True: pass"],
                          timeout=1.0)
        self.assertIsNone(r["exit"])
        self.assertEqual(r["stopped"], "timeout")
        self.assertIn("timed out", r["stderr"])

    def test_failing_child_exit_code_preserved(self):
        r = rl.run_capped([sys.executable, "-c", "raise SystemExit(7)"],
                          timeout=30)
        self.assertEqual(r["exit"], 7)


class TestRunawayDetector(unittest.TestCase):
    def test_repeated_identical_failure_detected(self):
        d = rl.RunawayDetector()
        for _ in range(3):
            d.record("AssertionError:identity-mismatch@a1")
        self.assertTrue(d.repeated_failure(min_repeat=3))

    def test_varied_failures_are_not_runaway(self):
        d = rl.RunawayDetector()
        for sig in ("err@a1", "err@a2", "err@a3"):
            d.record(sig)
        self.assertFalse(d.repeated_failure(min_repeat=3))

    def test_two_failures_below_threshold(self):
        d = rl.RunawayDetector()
        d.record("x"); d.record("x")
        self.assertFalse(d.repeated_failure(min_repeat=3))

    def test_no_progress_groove_detected(self):
        """A window of near-identical signatures means the loop is stuck —
        time to change strategy, checkpoint, or stop with accurate state."""
        d = rl.RunawayDetector(window=10)
        for _ in range(10):
            d.record("same-old")
        self.assertTrue(d.no_progress(variety_needed=2))

    def test_reset_clears_history(self):
        d = rl.RunawayDetector()
        for _ in range(5):
            d.record("x")
        d.reset()
        self.assertFalse(d.repeated_failure(min_repeat=2))


class TestBackoff(unittest.TestCase):
    def test_grows_exponentially_then_caps(self):
        waits = [rl.backoff(i) for i in range(12)]
        self.assertLess(waits[0], waits[3])
        self.assertLess(waits[3], waits[6])
        self.assertEqual(waits[-1], 30.0)
        self.assertEqual(waits[-2], 30.0)

    def test_negative_attempt_rejected(self):
        with self.assertRaises(ValueError):
            rl.backoff(-1)


class TestGovernedRetryLoop(unittest.TestCase):
    """The composition the governance module exists for: retries WITH a
    detector and a budget terminate in bounded time and accurate state."""

    def test_retry_storm_terminates(self):
        detector = rl.RunawayDetector()
        budget = rl.WallClockBudget(5.0)
        attempts = {"n": 0}
        outcome = None
        try:
            while True:
                budget.check("retry loop")
                attempts["n"] += 1
                detector.record("provider-500")
                if detector.repeated_failure(min_repeat=3):
                    outcome = "abandoned-after-repeated-identical-failures"
                    break
                time.sleep(rl.backoff(attempts["n"], base=0.001, cap=0.01))
        except rl.BudgetExceeded:
            outcome = "budget-exhausted"
        self.assertIsNotNone(outcome, "the loop must terminate")
        self.assertEqual(attempts["n"], 3)
        self.assertEqual(outcome, "abandoned-after-repeated-identical-failures")


class TestResourceAuditScript(unittest.TestCase):
    """The measurement CLI reports honest numbers for a known workload."""

    def test_audit_measures_a_sleep(self):
        script = Path(__file__).resolve().parent.parent / \
            "scripts" / "resource_audit.py"
        r = subprocess.run(
            [sys.executable, str(script), "--budget-seconds", "30",
             sys.executable, "-c", "import time; time.sleep(0.2)"],
            capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        import json
        rep = json.loads(r.stdout)
        self.assertGreaterEqual(rep["wall_sec"], 0.15)
        self.assertEqual(rep["exit"], 0)
        self.assertIsNone(rep["stopped"])

    def test_audit_reports_timeout_as_governance_event(self):
        script = Path(__file__).resolve().parent.parent / \
            "scripts" / "resource_audit.py"
        r = subprocess.run(
            [sys.executable, str(script), "--budget-seconds", "1",
             sys.executable, "-c", "while True: pass"],
            capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 30)
        import json
        rep = json.loads(r.stdout)
        self.assertIsNone(rep["exit"])
        self.assertIn("timeout", rep["stopped"])


if __name__ == "__main__":
    unittest.main()
