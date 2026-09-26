# // spec: coh-ctx-02, coh-pol-01, coh-pol-04
"""S6-A — the CLI consumes the core set it resolves (round-14 audit).

The unit battery (test_hub_coherence_modes.py) pins the ladder; this pins the
wiring. Mutation m8 proved units cannot see it: deleting the call site's
`core_classes=policy.enforced_core_classes(pol)` left all 507 tests green,
because the ladder's Q2 default silently stands in for whatever the bundle
names. Dead configuration is the exact defect class AIGGP-01 audits DevGate
for, so both directions of consumption are pinned here through the real CLI:

  * a bundle whose core set EXCLUDES identity-consistency must shelter
    baselined identity debt at Stage 3 (ADVISORY) — if the call site kept
    the ladder default instead, identity would unshelter and the run FAILs;
  * a bundle that says nothing gets the Q2 default — identity debt BLOCKS
    at Stage 3 — so the exclusion test cannot pass by ignoring the bundle
    AND the default both ways;
  * a malformed stages.enforced_core_classes is a policy refusal (exit 31),
    never a quiet fall back to the default (coh-pol-01: a central policy the
    service cannot honor is not policy).

All fixtures synthetic (R9); dual-runnable.
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
TRACE = "devgate.builtin.traceability-completeness"


def _run(req):
    return subprocess.run(
        [sys.executable, "-m", "hub.coherence", "--request", str(req)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO),
        env={**os.environ, **fx.cli_env()})


def _debt_world(td: Path, *, stage, stages=None):
    """One identity assertion violated (declared 'other-game' vs approved
    'widget'), baselined — the Stage-3 shelter question in one finding."""
    return fx.build_root(
        td / "world", declared_name="other-game", approved_name="widget",
        baseline=[fx.baseline_entry("product.identity", 1, "README.md",
                                    "identity-mismatch")],
        stage=stage, stages=stages)


class TestCoreSetReachesTheLadder(unittest.TestCase):
    def test_bundle_core_set_excluding_identity_shelters_at_stage_3(self):
        # The bundle names traceability as the ONLY core class, so the
        # baselined identity debt keeps its shelter: ADVISORY, exit 10.
        # If the CLI resolved nothing and the ladder default (which includes
        # identity) stood in, this run would FAIL — that is mutation m8.
        with tempfile.TemporaryDirectory() as td:
            req, out = _debt_world(Path(td), stage=3, stages={
                "max_advisory_age_days": 30,
                "enforced_core_classes": [TRACE]})
            p = _run(req)
            self.assertEqual(p.returncode, result.EXIT_ADVISORY,
                             f"bundle core set must reach the ladder; "
                             f"exit {p.returncode}: {p.stderr}")
            res = json.loads((out / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(res["decision"], "ADVISORY")
            self.assertTrue(all(f["enforcement"] == "ADVISORY"
                                for f in res["findings"]))

    def test_bundle_silent_gets_the_q2_default_blocking_at_stage_3(self):
        # The control pinning the other direction: no enforced_core_classes
        # key means the Q2 freeze, which includes identity-consistency, so
        # the same world must BLOCK. Without this, the exclusion test could
        # go green on a call site that passes an empty set always.
        with tempfile.TemporaryDirectory() as td:
            req, out = _debt_world(Path(td), stage=3)
            p = _run(req)
            self.assertEqual(p.returncode, result.EXIT_FAIL,
                             f"Q2 default core must unshelter identity debt "
                             f"at stage 3; exit {p.returncode}: {p.stderr}")
            res = json.loads((out / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(res["decision"], "FAIL")
            blocked = [f for f in res["findings"]
                       if f["enforcement"] == "BLOCK"]
            self.assertEqual([f["assertion_id"] for f in blocked],
                             ["product.identity"])

    def test_valid_core_set_does_not_perturb_a_clean_run(self):
        # Sanity in the remaining direction: a RESOLVED, valid core set must
        # not manufacture a block where nothing violates — a resolution bug
        # that treats any configured set as "shelter ends for all" flips this
        # clean (declared == approved) run from PASS to FAIL.
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(
                Path(td) / "world", stage=3,
                stages={"max_advisory_age_days": 30,
                        "enforced_core_classes": [TRACE]})
            p = _run(req)
            self.assertEqual(p.returncode, result.EXIT_PASS, p.stderr)


class TestMalformedCoreSet(unittest.TestCase):
    def test_non_array_core_classes_is_exit31(self):
        # build_root writes the bundle BEFORE digesting it, so this reaches
        # policy.resolve with a real digest and fails at the adoption step:
        # enforced_core_classes rejects a string where an array is required,
        # and __main__ maps PolicyError to exit 31.
        with tempfile.TemporaryDirectory() as td:
            req, out = _debt_world(Path(td), stage=3, stages={
                "max_advisory_age_days": 30,
                "enforced_core_classes": "identity"})
            p = _run(req)
            self.assertEqual(p.returncode, result.EXIT_POLICY,
                             f"expected exit 31, got {p.returncode}: {p.stderr}")
            self.assertNotIn("Traceback", p.stderr)
            env = json.loads((out / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(env["decision"], "ERROR")
            self.assertEqual(env["error"]["class"], "policy-resolution")

    def test_empty_core_classes_is_exit31(self):
        # The schema rejects minItems:1 too, but policy.resolve does not
        # schema-validate the bundle — the runtime guard is load-bearing.
        # An empty set would silently collapse Stage 3 into Stage 2.
        with tempfile.TemporaryDirectory() as td:
            req, _ = _debt_world(Path(td), stage=3, stages={
                "max_advisory_age_days": 30,
                "enforced_core_classes": []})
            p = _run(req)
            self.assertEqual(p.returncode, result.EXIT_POLICY, p.stderr)

    def test_non_string_member_is_exit31(self):
        with tempfile.TemporaryDirectory() as td:
            req, _ = _debt_world(Path(td), stage=3, stages={
                "max_advisory_age_days": 30,
                "enforced_core_classes": [TRACE, 7]})
            p = _run(req)
            self.assertEqual(p.returncode, result.EXIT_POLICY, p.stderr)


if __name__ == "__main__":
    unittest.main()
