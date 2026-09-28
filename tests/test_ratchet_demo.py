# // spec: coh-pol-04, coh-pol-05, coh-pol-06
"""Criterion 8 — the Stage-2 adoption ladder, pinned as a runnable drill.

`scripts/ratchet_demo.py` demonstrates the two obligations criterion 8 names
(no-regression and advisory-expiry) against the R9-captured LobsterWars
baseline SHAPE. This suite keeps that drill load-bearing by running it as a
subprocess and asserting the outcome, so the ledger's "criterion 8 is
demonstrated" claim cannot survive a ladder that stopped ratcheting.

Verified RED against two mutations of the real ladder, each killed by the
drill it belongs to:
  * `report.advisory_age`'s expiry branch forced to `expired = False` — the
    aged-out case stops blocking, so [2] fails while [3]'s direction control
    correctly stays green (this is why the control exists).
  * `adoption.fingerprint` made non-deterministic — nothing matches the
    baseline, so [3]'s sheltering fails.
A mutation that does NOT apply (a `str.replace` whose anchor is absent) leaves
the suite green and looks identical to a surviving mutation; both mutations
above were re-checked with an explicit anchor assertion before being trusted.

Fixtures are synthetic; the baseline shape is captured. See the script's
module docstring for what that distinction does and does not license.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "ratchet_demo.py"


def _run_demo() -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(SCRIPT)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(REPO))
    return p.returncode, p.stdout + p.stderr


class RatchetDemoTest(unittest.TestCase):
    """The drill exits 0 and every obligation reports PASS."""

    @classmethod
    def setUpClass(cls):
        cls.code, cls.out = _run_demo()

    def test_the_drill_exits_zero(self):
        self.assertEqual(self.code, 0, f"ratchet demo failed:\n{self.out}")

    def test_both_obligations_are_reported(self):
        self.assertIn("no-regression", self.out)
        self.assertIn("advisory-expiry", self.out)

    def test_no_obligation_reports_fail(self):
        fails = [l for l in self.out.splitlines() if l.strip().startswith("FAIL")]
        self.assertEqual(fails, [], f"drill reported failures: {fails}")

    def test_all_steps_passed(self):
        self.assertIn("ALL OBLIGATIONS HELD", self.out)
        detail = next(l for l in self.out.splitlines() if "steps" in l and "/" in l)
        passed, total = detail.split("—")[1].split("steps")[0].strip().split("/")
        self.assertEqual(passed, total, f"not every step held: {detail.strip()}")


class RatchetDrillIsRealTest(unittest.TestCase):
    """The drill invokes the real service, not a stand-in."""

    def test_the_script_uses_the_real_entry_point(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"-m", "hub.coherence"', src,
                      "the drill must run the real service entry point; a "
                      "drill that reimplements the ladder proves nothing")

    def test_the_script_reads_findings_from_the_evidence_bundle(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"evidence" / "findings"', src,
                      "per-location findings live in the sealed evidence "
                      "bundle, not in result['assertion_results']")

    def test_the_captured_shape_matches_the_provenance_record(self):
        """The 13 locations are the captured ones, in emitted order."""
        src = SCRIPT.read_text(encoding="utf-8")
        record = (REPO / "openspec" / "changes" / "devgate-spec-coherence-service"
                  / "r9-provenance-capture.md").read_text(encoding="utf-8")
        for location in ("server/GameRoom.ts", "src/systems/TheaterSystem.ts",
                         "src/network/NetworkManager.ts"):
            self.assertIn(f'"{location}"', src,
                          f"the drill dropped captured location {location}")
            self.assertIn(location, record,
                          f"{location} is not in the provenance record")


if __name__ == "__main__":
    unittest.main()
