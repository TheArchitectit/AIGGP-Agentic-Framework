# // spec: coh-rt-06, coh-eval-04, coh-pol-01
"""Built-in evaluator allowlist, enforced at the planner (coh-rt-06):
repository-supplied or unknown evaluator references are rejected before any
evaluation, an overlay cannot smuggle one past central policy, and the
allowlist accepts every bundled built-in. Split out of test_hub_coherence.py
to keep that file under the 600-line test budget. All fixtures synthetic (R9).
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import evaluators, plan, policy


def _assertion(aid="a1", deps=None):
    return {
        "id": aid, "version": 1, "requirement_refs": ["r1"], "owner": "o",
        "requirement": "r", "subjects": [{"kind": "file", "path": "x"}],
        "evaluator": {"id": "devgate.builtin.identity-consistency",
                      "digest": "sha256:" + "a" * 64},
        "parameters": {}, "severity": "high", "dependencies": deps or [],
        "evidence": {"retention_days": 1},
    }


class TestPlannerEvaluatorAllowlist(unittest.TestCase):
    def test_planner_accepts_all_builtins(self):
        assertions = []
        for i, eid in enumerate(sorted(evaluators.BUILTINS)):
            b = _assertion(f"a{i}")
            b["evaluator"] = {"id": eid, "digest": "sha256:" + "a" * 64}
            assertions.append(b)
        planned = plan.plan(assertions, [])
        self.assertEqual(len(planned), len(evaluators.BUILTINS))

    def test_planner_rejects_repository_supplied_evaluator(self):
        # coh-rt-06: repository-supplied executable code MUST NOT run as an
        # evaluator; the planner rejects the reference before any evaluation.
        a = _assertion("a1")
        a["evaluator"] = {"id": "repo.evil", "digest": "sha256:" + "b" * 64}
        with self.assertRaises(plan.PlanError) as cm:
            plan.plan([a], [])
        self.assertIn("unapproved-evaluator:repo.evil", str(cm.exception))

    def test_overlay_swapped_evaluator_rejected_at_planning(self):
        # Layered defense: even when central policy carries no approved
        # evaluator list, an overlay-swapped non-builtin id cannot pass
        # through apply_overlay into execution.
        with tempfile.TemporaryDirectory() as td:
            pol = Path(td)
            (pol / "overlay.json").write_text(json.dumps({
                "assertions": [{"id": "a1",
                                "evaluator": {"id": "repo.evil", "digest": "sha256:" + "b" * 64}}],
            }))
            a = _assertion("a1")
            central = {"required_assertions": [], "approved_evaluators": []}
            swapped = policy.apply_overlay([a], json.loads(
                (pol / "overlay.json").read_text()), central)
            with self.assertRaises(plan.PlanError) as cm:
                plan.plan(swapped, [])
            self.assertIn("unapproved-evaluator:repo.evil", str(cm.exception))

    def test_planner_rejects_malformed_evaluator_shape(self):
        # Shape is checked before the allowlist lookup: a non-dict evaluator
        # or a missing/miss-typed id is invalid input (exit 30), never a
        # crash deeper in the evaluator runtime.
        for bad in ("not-a-dict", ["not-a-dict"],
                    {"digest": "sha256:" + "a" * 64},
                    {"id": ["not-a-str"], "digest": "sha256:" + "a" * 64}):
            a = _assertion("a1")
            a["evaluator"] = bad
            with self.assertRaises(plan.PlanError):
                plan.plan([a], [])


if __name__ == "__main__":
    unittest.main()
