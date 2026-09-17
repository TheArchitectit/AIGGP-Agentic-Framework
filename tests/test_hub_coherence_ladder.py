# // spec: coh-pol-03, coh-pol-04, coh-pol-06, coh-dec-04
"""S3 ladder demo — acceptance Fixture C, SYNTHETIC (R9: the LobsterWars
13-violation baseline is supplied narrative, not a captured fact; this models
the failure CLASS with 13 named synthetic findings).

Full ladder through the real CLI:
  Stage 1:            ADVISORY, all 13 visible
  Stage 2 unchanged:  ADVISORY (all named baseline debt)
  Stage 2 + new:      FAIL (the new fingerprint blocks, 13 stay advisory)
  expired exception:  FAIL (underlying violation enforces)
  wildcard exception: invalid policy (exit 31)
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import canon, context, issue, result
from tests.fixtures.coherence import fixtures as fx

REPO = Path(__file__).resolve().parent.parent
N = 13
AIDS = [f"debt.finding-{i:02d}" for i in range(N)]


def _assertions():
    """13 identity assertions — each yields one identity-mismatch finding
    when the subject declares the wrong product name."""
    return [fx.assertion(aid=a, subjects=[
        {"kind": "file", "path": "README.md"},
        {"kind": "artifact-metadata",
         "selector": "product.identity.name"}]) for a in AIDS]


def _baseline():
    return [fx.baseline_entry(a, 1, "README.md", "identity-mismatch")
            for a in AIDS]


def _run(req):
    return subprocess.run([sys.executable, "-m", "hub.coherence",
                           "--request", str(req)],
                          capture_output=True, text=True, cwd=str(REPO))


def _ladder_fixture(td: Path, *, stage, baseline=None, exceptions=None,
                    extra_assertion=None):
    """Build a violation-of-13 world; return (request_path, out_dir)."""
    assertions = _assertions()
    if extra_assertion:
        assertions.append(extra_assertion)
    req, out = fx.build_root(td / "world", declared_name="other-game",
                             approved_name="widget", assertions=assertions,
                             baseline=baseline, exceptions=exceptions,
                             stage=stage)
    return req, out


class TestLadderDemo(unittest.TestCase):
    def test_stage_one_advisory_with_all_thirteen_visible(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = _ladder_fixture(Path(td), stage=1)
            p = _run(req)
            res = json.loads((out / "result.json").read_text())
            self.assertEqual(p.returncode, result.EXIT_ADVISORY)
            self.assertEqual(res["assertion_summary"]["violated"], N)
            self.assertEqual({f["assertion_id"] for f in res["findings"]},
                             set(AIDS), "every finding must stay VISIBLE")
            self.assertTrue(all(f["enforcement"] == "ADVISORY"
                                for f in res["findings"]),
                            "outcomes stay VIOLATED, enforcement advisory only")
            # coh-eval-05: underlying truth preserved despite advisory.
            self.assertEqual(res["assertion_summary"]["violated"],
                             sum(1 for e in res["assertion_results"]
                                 if e["outcome"] == "VIOLATED"))

    def test_stage_two_named_debt_advisory(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = _ladder_fixture(Path(td), stage=2, baseline=_baseline())
            p = _run(req)
            res = json.loads((out / "result.json").read_text())
            self.assertEqual(p.returncode, result.EXIT_ADVISORY,
                             "all 13 are named baseline debt -> no regression")
            self.assertTrue(all(f["enforcement"] == "ADVISORY"
                                for f in res["findings"]))

    def test_stage_two_new_finding_blocks_while_debt_stays_advisory(self):
        new = fx.assertion(aid="debt.new-finding-14", subjects=[
            {"kind": "file", "path": "README.md"},
            {"kind": "artifact-metadata",
             "selector": "product.identity.name"}])
        with tempfile.TemporaryDirectory() as td:
            req, out = _ladder_fixture(Path(td), stage=2, baseline=_baseline(),
                                       extra_assertion=new)
            p = _run(req)
            res = json.loads((out / "result.json").read_text())
            self.assertEqual(p.returncode, result.EXIT_FAIL)
            self.assertEqual(res["decision"], "FAIL")
            blocked = [f for f in res["findings"] if f["enforcement"] == "BLOCK"]
            self.assertEqual([f["assertion_id"] for f in blocked],
                             ["debt.new-finding-14"])
            self.assertEqual(
                sum(1 for f in res["findings"]
                    if f["enforcement"] == "ADVISORY"), N,
                "the 13 named debts remain advisory")

    def test_expired_baseline_exception_blocks(self):
        """One debt item rides an exception; it expires; the underlying
        violation enforces (coh-pol-06: never rewrites the outcome)."""
        exc = [fx.exception_entry(AIDS[3], 1, "README.md", "identity-mismatch",
                                  expires_at="2026-09-01T00:00:00Z")]
        with tempfile.TemporaryDirectory() as td:
            req, out = _ladder_fixture(Path(td), stage=2, baseline=_baseline(),
                                       exceptions=exc)
            p = _run(req)
            res = json.loads((out / "result.json").read_text())
            self.assertEqual(p.returncode, result.EXIT_FAIL)
            blocked = [f for f in res["findings"]
                       if f["enforcement"] == "BLOCK"]
            self.assertEqual([f["assertion_id"] for f in blocked], [AIDS[3]])
            self.assertEqual(
                [e["outcome"] for e in res["assertion_results"]
                 if e["assertion_id"] == AIDS[3]], ["VIOLATED"],
                "expired exception does not rewrite the outcome")

    def test_live_exception_demotes_to_exception_advisory(self):
        exc = [fx.exception_entry(AIDS[5], 1, "README.md", "identity-mismatch",
                                  expires_at="2027-01-01T00:00:00Z")]
        with tempfile.TemporaryDirectory() as td:
            req, out = _ladder_fixture(Path(td), stage=2, baseline=_baseline(),
                                       exceptions=exc)
            p = _run(req)
            res = json.loads((out / "result.json").read_text())
            self.assertEqual(p.returncode, result.EXIT_ADVISORY)
            hit = [f for f in res["findings"] if f["assertion_id"] == AIDS[5]]
            self.assertEqual(hit[0]["enforcement"], "EXCEPTION-ADVISORY")
            self.assertIn("exception_id", hit[0])

    def test_wildcard_exception_is_invalid_policy(self):
        exc = [fx.exception_entry(AIDS[0], 1, "README.md", "identity-mismatch",
                                  expires_at="2027-01-01T00:00:00Z")]
        exc[0]["assertion_id"] = "*"
        with tempfile.TemporaryDirectory() as td:
            req, out = _ladder_fixture(Path(td), stage=2, baseline=_baseline(),
                                       exceptions=exc)
            p = _run(req)
            self.assertEqual(p.returncode, result.EXIT_POLICY)

    def test_ladder_through_issued_context(self):
        """The pilot path end-to-end: issue_context (binding the baseline set)
        -> stage 2 with all 13 baselined -> ADVISORY; then a set swap after
        issuance fails closed (coh-ctx-01)."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            req, out = _ladder_fixture(base, stage=2, baseline=_baseline())
            pol_dir = Path(json.loads(req.read_text())["policy"]["root"])
            ctx_dir = base / "issued-ctx"
            issue.issue_context(
                str(ctx_dir), str(pol_dir), repo="com.test.widget",
                registry_path=str(_registry_file(base)),
                evaluation_time="2026-09-17T00:00:00Z",
                baseline_set=_baseline())
            r = json.loads(req.read_text())
            r["context"] = {"root": str(ctx_dir),
                            "expected_digest":
                                context.load(str(ctx_dir))["context_digest"]}
            req.write_text(json.dumps(r))
            p = _run(req)
            self.assertEqual(p.returncode, result.EXIT_ADVISORY)
            # Baseline swap detection on the issued path.
            (pol_dir / "baseline.json").write_bytes(b"[]")
            p2 = _run(req)
            self.assertEqual(p2.returncode, result.EXIT_POLICY,
                             "set swap must fail closed (coh-ctx-01)")


    def test_unbound_sets_are_not_swap_protected(self):
        """Documented boundary (coh-ctx-01): swap detection only exists for
        sets BOUND into the context at issuance. An unbound policy set is
        re-read as-is — which is why pilots must bind them. Here: context
        without baseline_set, then baseline added -> violations become named
        debt and the decision flips to ADVISORY without any error."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            req, out = _ladder_fixture(base, stage=2)  # no baseline file at all
            pol_dir = Path(json.loads(req.read_text())["policy"]["root"])
            ctx_dir = base / "issued-ctx"
            issue.issue_context(
                str(ctx_dir), str(pol_dir), repo="com.test.widget",
                registry_path=str(_registry_file(base)),
                evaluation_time="2026-09-17T00:00:00Z")  # no baseline_set
            r = json.loads(req.read_text())
            r["context"] = {"root": str(ctx_dir),
                            "expected_digest":
                                context.load(str(ctx_dir))["context_digest"]}
            req.write_text(json.dumps(r))
            p1 = _run(req)
            self.assertEqual(p1.returncode, result.EXIT_FAIL)  # unbaselined
            # Bind nothing; now write a matching baseline and re-run.
            (pol_dir / "baseline.json").write_bytes(canon.canon(_baseline()))
            p2 = _run(req)
            self.assertEqual(p2.returncode, result.EXIT_ADVISORY,
                             "unbound set was re-read silently — pilots bind")


def _registry_file(td: Path) -> Path:
    rp = td / "stage-registry.json"
    rp.write_text(json.dumps({"com.test.widget": {
        "stage": 2, "owner": "portfolio-owner", "next_stage": 3}}))
    return rp


if __name__ == "__main__":
    unittest.main()
