# // spec: coh-pol-03, coh-pol-06
"""S3 tests: advisory-age and exception-expiry reporting. Dual-runnable."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import report

REF = "2026-09-17T00:00:00Z"


class TestAdvisoryAge(unittest.TestCase):
    def test_within_cap(self):
        rec = {"stage": 1, "owner": "o", "advisory_started": "2026-09-01T00:00:00Z",
               "advisory_expiry": "2026-09-30T00:00:00Z"}
        out = report.advisory_status(rec, 30, REF)
        self.assertFalse(out["expired"])
        self.assertEqual(out["advisory_age_days"], 16)

    def test_expiry_reached(self):
        rec = {"stage": 1, "owner": "o", "advisory_started": "2026-08-01T00:00:00Z",
               "advisory_expiry": "2026-09-01T00:00:00Z"}
        out = report.advisory_status(rec, 30, REF)
        self.assertTrue(out["expired"])
        self.assertIn("expiry reached", out["notes"][0])

    def test_cap_exceeded_without_expiry(self):
        rec = {"stage": 1, "owner": "o", "advisory_started": "2026-06-01T00:00:00Z"}
        out = report.advisory_status(rec, 30, REF)
        self.assertTrue(out["expired"])
        self.assertIn("exceeds the central cap", out["notes"][0])

    def test_missing_start_is_violation(self):
        rec = {"stage": 1, "owner": "o"}
        out = report.advisory_status(rec, 30, REF)
        self.assertTrue(out["expired"])
        self.assertIn("without a recorded start", out["notes"][0])

    def test_non_advisory_stage_not_capped(self):
        rec = {"stage": 2, "owner": "o", "advisory_started": "2025-01-01T00:00:00Z"}
        out = report.advisory_status(rec, 30, REF)
        self.assertFalse(out["expired"])


class TestExceptionExpiry(unittest.TestCase):
    def test_remaining_life_and_expired_flags(self):
        exc = [{"exception_id": "e1", "assertion_id": "a", "owner": "o",
                "expires_at": "2026-09-27T00:00:00Z"},
               {"exception_id": "e2", "assertion_id": "a", "owner": "o",
                "expires_at": "2026-09-01T00:00:00Z"}]
        rows = report.exception_status(exc, REF)
        self.assertEqual(rows[0]["days_remaining"], 10)
        self.assertFalse(rows[0]["expired"])
        self.assertTrue(rows[1]["expired"])

    def test_unparseable_expires_reported_not_raised(self):
        rows = report.exception_status(
            [{"exception_id": "e", "expires_at": "garbage"}], REF)
        self.assertIn("unparseable", rows[0]["error"])


class TestSummarize(unittest.TestCase):
    def test_age_is_derived_from_context_not_clock(self):
        result = {"decision": "ADVISORY", "subject_digest": "sha256:" + "a" * 64}
        context = {"context_digest": "sha256:" + "b" * 64,
                   "semantics": "fresh-promotion",
                   "evaluation_time": "2026-09-17T00:00:00Z"}
        rec = {"stage": 1, "owner": "o", "advisory_started": "2026-09-07T00:00:00Z",
               "advisory_expiry": "2026-09-20T00:00:00Z"}
        s1 = report.summarize(result, context, rec, 30)
        s2 = report.summarize(result, context, rec, 30)
        self.assertEqual(s1, s2, "reports must be reproducible for sealed inputs")
        self.assertEqual(s1["advisory"]["advisory_age_days"], 10)
        self.assertTrue(s1["promotion_authorizing"])

    def test_replay_results_flagged_non_authorizing(self):
        s = report.summarize({"decision": "PASS"},
                             {"context_digest": "d", "semantics": "replay",
                              "evaluation_time": "2026-09-17T00:00:00Z"},
                             {"stage": 1, "owner": "o"}, 30)
        self.assertFalse(s["promotion_authorizing"])


if __name__ == "__main__":
    unittest.main()
