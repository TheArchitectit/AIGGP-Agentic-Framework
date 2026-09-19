# // spec: coh-pol-04, coh-pol-05, coh-pol-06, coh-dec-04, coh-eval-02, coh-ctx-03
"""Frozen S2 conformance suite: Fixtures A-F, full exit-code sweep, error
envelopes. Dual-runnable. All fixtures synthetic (R9).
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import result
from tests.fixtures.coherence import fixtures as fx

REPO = Path(__file__).resolve().parent.parent
ZERO_DIGEST = "sha256:" + "0" * 64


def _run(req_path: Path, out_dir: Path):
    """Invoke the real CLI; return (exit_code, parsed result or None)."""
    r = subprocess.run([sys.executable, "-m", "hub.coherence", "--request", str(req_path)],
                       capture_output=True, text=True, cwd=str(REPO))
    rp = out_dir / "result.json"
    parsed = json.loads(rp.read_text()) if rp.exists() else None
    return r.returncode, parsed


class TestFixtureA(unittest.TestCase):
    """Coherent minimal repository -> PASS, byte-identical across replays."""

    def test_coherent_pass_and_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), declared_name="widget",
                                     approved_name="widget", stage=1)
            code, res = _run(req, out)
            self.assertEqual(code, result.EXIT_PASS)
            self.assertEqual(res["decision"], "PASS")
            self.assertEqual(res["assertion_summary"]["violated"], 0)
            # 100x replay: canonical bytes identical.
            first = (out / "result.json").read_bytes()
            for _ in range(99):
                _run(req, out)
                self.assertEqual((out / "result.json").read_bytes(), first,
                                 "canonical result bytes must be replay-identical")


class TestFixtureB(unittest.TestCase):
    """Identity drift -> VIOLATED with exact locations and approved-value compare."""

    def test_identity_drift_violated(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), declared_name="otherball",
                                     approved_name="widget", stage=1)
            code, res = _run(req, out)
            self.assertEqual(code, result.EXIT_ADVISORY)  # stage 1: visible, non-blocking
            self.assertEqual(res["decision"], "ADVISORY")
            self.assertEqual(res["assertion_summary"]["violated"], 1)
            f = res["findings"][0]
            self.assertEqual(f["assertion_id"], "product.identity")
            self.assertIn("README.md", f["subject_locations"])
            # Approved-value comparison, not mere agreement (coh-assert-02).
            self.assertEqual(f["expected"], "widget")
            self.assertIn("otherball", f["observed"])


class TestFixtureC_Ratchet(unittest.TestCase):
    """Fingerprinted baseline ratchet, not numeric allowance."""

    def _baseline_4(self):
        return [fx.baseline_entry(f"assertion-{i}", 1, "README.md", "identity-mismatch")
                for i in range(4)]

    def test_named_baseline_debt_is_advisory_at_stage2(self):
        with tempfile.TemporaryDirectory() as td:
            assertions = [fx.assertion(aid=f"assertion-{i}") for i in range(4)]
            baseline = self._baseline_4()
            req, out = fx.build_root(Path(td), declared_name="other", approved_name="widget",
                                     assertions=assertions, baseline=baseline, stage=2)
            code, res = _run(req, out)
            self.assertEqual(res["decision"], "ADVISORY")
            self.assertTrue(all(f["enforcement"] == "ADVISORY" for f in res["findings"]))

    def test_four_baseline_plus_one_new_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            assertions = [fx.assertion(aid=f"assertion-{i}") for i in range(5)]
            baseline = self._baseline_4()   # only 4 are named debt
            req, out = fx.build_root(Path(td), declared_name="other", approved_name="widget",
                                     assertions=assertions, baseline=baseline, stage=2)
            code, res = _run(req, out)
            self.assertEqual(code, result.EXIT_FAIL)
            self.assertEqual(res["decision"], "FAIL")
            blocking = [f for f in res["findings"] if f["enforcement"] == "BLOCK"]
            self.assertEqual(len(blocking), 1)
            self.assertEqual(blocking[0]["assertion_id"], "assertion-4")

    def test_one_fixed_one_new_at_constant_count_blocks(self):
        """Baseline of 4, one remediated (status=remediated) + a different new
        violation: total stays 4, but the new fingerprint must block."""
        with tempfile.TemporaryDirectory() as td:
            assertions = [fx.assertion(aid=f"assertion-{i}") for i in range(4)]
            baseline = self._baseline_4()
            baseline[0] = fx.baseline_entry("assertion-0", 1, "README.md",
                                            "identity-mismatch", status="remediated")
            req, out = fx.build_root(Path(td), declared_name="other", approved_name="widget",
                                     assertions=assertions, baseline=baseline, stage=2)
            code, res = _run(req, out)
            self.assertEqual(res["decision"], "FAIL",
                             "numeric-count equality must not be a pass condition")
            blocking = [f for f in res["findings"] if f["enforcement"] == "BLOCK"]
            self.assertEqual([b["assertion_id"] for b in blocking], ["assertion-0"])


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


class TestFixtureD_Bypass(unittest.TestCase):
    """Repository cannot weaken central policy or pick an unapproved evaluator."""

    def test_unapproved_evaluator_rejected_at_planning(self):
        # coh-rt-06 scenario: the reference is rejected when the PLANNER
        # resolves evaluators — a repo-supplied evaluator never runs, and the
        # package itself is invalid input (exit 30), not an evaluated failure.
        with tempfile.TemporaryDirectory() as td:
            a = fx.assertion(aid="a1", evaluator={"id": "repo.evil", "digest": "sha256:" + "b" * 64})
            req, out = fx.build_root(Path(td), declared_name="widget", approved_name="widget",
                                     assertions=[a], stage=1)
            code, res = _run(req, out)
            self.assertEqual(code, result.EXIT_INVALID_INPUT)
            self.assertEqual(res["decision"], "ERROR")
            self.assertEqual(res["error"]["class"], "invalid-input")
            self.assertIn("unapproved-evaluator:repo.evil", res["error"]["reason"])
            # Same rejection at an enforced stage: planning precedes evaluation.
            req2, out2 = fx.build_root(Path(td) / "s2", declared_name="widget",
                                       approved_name="widget", assertions=[a], stage=3)
            code2, res2 = _run(req2, out2)
            self.assertEqual(code2, result.EXIT_INVALID_INPUT)
            self.assertEqual(res2["decision"], "ERROR")

    def test_centrally_required_assertion_cannot_be_omitted(self):
        from hub.coherence import plan
        with self.assertRaises(plan.PlanError):
            plan.plan([fx.assertion(aid="a1")], ["a2"])

    def test_policy_digest_mismatch_is_error(self):
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), policy_digest_ok=False)
            code, res = _run(req, out)
            self.assertEqual(code, result.EXIT_POLICY)
            self.assertEqual(res["decision"], "ERROR")


class TestSubjectManifestPolicy(unittest.TestCase):
    """Submodule, exclusion, and symlink policy — all explicit in the manifest
    (coh-id-02). Round-1 carry-forward, implemented after round 2."""

    def test_excluded_dirs_are_recorded_not_silently_skipped(self):
        from hub.coherence import manifest
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "s"
            (root / "node_modules").mkdir(parents=True)
            (root / "node_modules" / "dep.js").write_text("x")
            (root / "src").mkdir()
            (root / "src" / "main.py").write_text("y")
            m = manifest.build(str(root))
            by_path = {e["path"]: e for e in m["entries"]}
            self.assertIn("node_modules", by_path)
            self.assertEqual(by_path["node_modules"]["kind"], "excluded")
            self.assertIsNone(by_path["node_modules"]["digest"])
            self.assertNotIn("node_modules/dep.js", by_path,
                             "excluded content must not be digested")
            self.assertEqual(by_path["src/main.py"]["kind"], "file")

    def test_submodule_recorded_and_not_descended(self):
        from hub.coherence import manifest
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "s"
            sub = root / "vendor-lib"
            sub.mkdir(parents=True)
            (sub / ".git").write_text("gitdir: ../.git/modules/vendor-lib")
            (sub / "lib.py").write_text("z")
            m = manifest.build(str(root))
            by_path = {e["path"]: e for e in m["entries"]}
            self.assertIn("vendor-lib", by_path)
            self.assertEqual(by_path["vendor-lib"]["kind"], "submodule")
            # The fixture's gitdir does not exist, so the pin cannot be
            # resolved: fail-honest `submodule-unresolved`, never a
            # `submodule-pinned` claim without a named pin.
            self.assertEqual(by_path["vendor-lib"]["policy_outcome"],
                             "submodule-unresolved")
            self.assertIsNone(by_path["vendor-lib"]["digest"])
            self.assertNotIn("vendor-lib/lib.py", by_path,
                             "submodule content must not be digested")

    def test_default_excludes_can_be_overridden(self):
        from hub.coherence import manifest
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "s"
            (root / "build").mkdir(parents=True)
            (root / "build" / "out.bin").write_text("b")
            m = manifest.build(str(root), excludes=())
            paths = [e["path"] for e in m["entries"]]
            self.assertIn("build/out.bin", paths,
                          "with excludes=() the directory is walked normally")


class TestPlanningTraceability(unittest.TestCase):
    """coh-assert-04 planning-time structural check (round-1 carry-forward)."""

    def test_unknown_requirement_reference_rejected(self):
        from hub.coherence import plan
        a = fx.assertion(aid="a1")
        a["requirement_refs"] = ["does-not-exist"]
        with self.assertRaises(plan.PlanError) as c:
            plan.plan([a], [], requirements={"real-req": {"testable": False}})
        self.assertIn("unknown requirement", str(c.exception))

    def test_orphan_testable_requirement_rejected(self):
        from hub.coherence import plan
        a = fx.assertion(aid="a1")
        a["requirement_refs"] = ["r1"]
        with self.assertRaises(plan.PlanError) as c:
            plan.plan([a], [], requirements={"r1": {"testable": False},
                                             "r2": {"testable": True}})
        self.assertIn("no assertion", str(c.exception))

    def test_traceable_package_passes(self):
        from hub.coherence import plan
        a = fx.assertion(aid="a1")
        a["requirement_refs"] = ["r1"]
        out = plan.plan([a], [], requirements={"r1": {"testable": True}})
        self.assertEqual(len(out), 1)

    def test_no_requirements_supplied_skips_the_check(self):
        from hub.coherence import plan
        with self.assertRaises(plan.PlanError):
            plan.plan([fx.assertion(aid="a1")], [], requirements={"other": {"testable": True}})
        # Without a registry the structural check is not run.
        self.assertEqual(len(plan.plan([fx.assertion(aid="a1")], [])), 1)


class TestOverlayCannotWeaken(unittest.TestCase):
    """coh-pol-01: a repository overlay may strengthen, never weaken. These are
    the frozen Fixture D cases (audit round 1 found the overlay mechanism was
    entirely absent — plan.plan protected against omission, but nothing could
    express an overlay at all)."""

    def _central(self):
        return {
            "api_version": "devgate.spec-coherence.policy/v1",
            "policy_version": "1", "min_bundle_epoch": 0,
            "required_assertions": ["a1"],
            "assertion_severity_floor": {"a1": "high"},
            "approved_evaluators": [{"id": "devgate.builtin.identity-consistency",
                                     "digest": "sha256:" + "a" * 64}],
            "approved_signers": [], "stages": {"max_advisory_age_days": 30},
        }

    def _assertions(self):
        return [fx.assertion(aid="a1"), fx.assertion(aid="a2")]

    def test_disable_centrally_required_assertion_rejected(self):
        from hub.coherence import policy
        with self.assertRaises(policy.OverlayError) as c:
            policy.apply_overlay(self._assertions(),
                                 {"assertions": [{"id": "a1", "disabled": True}]},
                                 self._central())
        self.assertIn("disables centrally required", str(c.exception))

    def test_lower_severity_rejected(self):
        from hub.coherence import policy
        with self.assertRaises(policy.OverlayError) as c:
            policy.apply_overlay(self._assertions(),
                                 {"assertions": [{"id": "a1", "severity": "low"}]},
                                 self._central())
        self.assertIn("below central floor", str(c.exception))

    def test_unapproved_evaluator_rejected(self):
        from hub.coherence import policy
        with self.assertRaises(policy.OverlayError) as c:
            policy.apply_overlay(
                self._assertions(),
                {"assertions": [{"id": "a1", "evaluator": {"id": "repo.evil",
                                                           "digest": "sha256:" + "b" * 64}}]},
                self._central())
        self.assertIn("unapproved evaluator", str(c.exception))

    def test_raising_severity_allowed(self):
        from hub.coherence import policy
        out = policy.apply_overlay(self._assertions(),
                                   {"assertions": [{"id": "a2", "severity": "critical"}]},
                                   self._central())
        a2 = next(a for a in out if a["id"] == "a2")
        self.assertEqual(a2["severity"], "critical")

    def test_capability_grant_rejected(self):
        from hub.coherence import policy
        with self.assertRaises(policy.OverlayError) as c:
            policy.apply_overlay(self._assertions(), {"network": "egress"}, self._central())
        self.assertIn("control-plane policy", str(c.exception))

    def test_overlay_bypass_end_to_end_is_error(self):
        """A real overlay file attempting a bypass must yield ERROR, never PASS."""
        with tempfile.TemporaryDirectory() as td:
            req, out = fx.build_root(Path(td), stage=1)
            polroot = json.loads(req.read_text())["policy"]["root"]
            # Central policy requires a2; overlay tries to disable it.
            bundle = json.loads((Path(polroot) / "policy.json").read_text())
            bundle["required_assertions"] = ["a1"]
            bundle["assertion_severity_floor"] = {"a1": "high"}
            from hub.coherence import canon as C
            (Path(polroot) / "policy.json").write_text(json.dumps(bundle))
            r = json.loads(req.read_text())
            r["policy"]["expected_digest"] = C.digest_obj("policy/v1", bundle)
            req.write_text(json.dumps(r))
            (Path(polroot) / "overlay.json").write_text(json.dumps(
                {"assertions": [{"id": "a1", "disabled": True}]}))
            code, res = _run(req, out)
            self.assertEqual(code, result.EXIT_POLICY)
            self.assertEqual(res["decision"], "ERROR")
            self.assertNotIn(res["decision"], ("PASS", "ADVISORY"))


class TestFixtureE_Nondeterminism(unittest.TestCase):
    """Undeclared inputs (time, traversal order) cannot produce inconsistent passes."""

    def test_unordered_traversal_is_stable(self):
        from hub.coherence import manifest
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "s"
            root.mkdir()
            for n in ["z.txt", "a.txt", "m.txt", "b.txt"]:
                (root / n).write_text(n)
            d1 = manifest.build(str(root))["subject_digest"]
            d2 = manifest.build(str(root))["subject_digest"]
            self.assertEqual(d1, d2)
            # Ordering must be sorted, not incidental directory order: the
            # digest must be independent of creation order.
            root2 = Path(td) / "s2"
            root2.mkdir()
            for n in ["m.txt", "b.txt", "z.txt", "a.txt"]:   # different creation order
                (root2 / n).write_text(n)
            self.assertEqual(_digest_of(root2), _digest_of(root))

    def test_traversal_guard_layers_each_isolated(self):
        """_check_safe has three independent layers. Assert on the message so
        deleting any single layer is caught (a bare assertRaises passes as long
        as one redundant layer survives — which is how the guard went
        unguarded in the audit)."""
        from hub.coherence import manifest
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "s"
            root.mkdir()
            (root / "ok.txt").write_text("x")
            # Layer 1: absolute path.
            with self.assertRaises(manifest.SubjectError) as c1:
                manifest._check_safe("/etc/passwd", root)
            self.assertIn("absolute path", str(c1.exception))
            # Layer 2: traversal / empty segment.
            with self.assertRaises(manifest.SubjectError) as c2:
                manifest._check_safe("../escape.txt", root)
            self.assertIn("traversal", str(c2.exception))
            # Layer 3: containment — a path that passes layers 1-2 but resolves
            # outside the root via a symlinked directory. This is the real
            # security boundary and was previously untested.
            outside = Path(td) / "outside"
            outside.mkdir()
            (outside / "secret.txt").write_text("s")
            (root / "link").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(manifest.SubjectError) as c3:
                manifest._check_safe("link/secret.txt", root)
            self.assertIn("escapes root", str(c3.exception))

    def test_symlinked_directory_never_enters_manifest(self):
        """An escaping symlink must not contribute a digest.

        Round-2 audit finding 4: as originally written this passed with
        `_check_safe` fully disabled, because `os.walk(followlinks=False)`
        never descends — it asserted the stdlib, not our guard. This version
        asserts the guard's own contribution: the symlinked entry must be
        recorded (as a symlink) and the walk must be explicitly non-following.
        """
        from hub.coherence import manifest
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "s"
            root.mkdir()
            (root / "ok.txt").write_text("x")
            outside = Path(td) / "outside"
            outside.mkdir()
            (outside / "secret.txt").write_text("s")
            (root / "link").symlink_to(outside, target_is_directory=True)
            m = manifest.build(str(root))
            paths = [e["path"] for e in m["entries"]]
            self.assertNotIn("link/secret.txt", paths,
                             "content outside the root must never be digested")
            # The manifest must be explicit about the symlink rather than
            # silently omitting it, and must distinguish escape classification.
            link_entries = [e for e in m["entries"] if e["path"].startswith("link")]
            for e in link_entries:
                self.assertEqual(e["kind"], "symlink")
                self.assertIn(e["policy_outcome"], ("symlink-forbidden", "symlink-escape"))
                self.assertIsNone(e["digest"], "a symlink must never carry a file digest")

    def test_escaping_symlink_is_classified_as_escape(self):
        """An escaping symlink must be classified `symlink-escape`, not merely
        `symlink-forbidden` — the distinction is the security signal."""
        from hub.coherence import manifest
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "s"
            root.mkdir()
            (root / "ok.txt").write_text("x")
            outside = Path(td) / "outside"
            outside.mkdir()
            (outside / "secret.txt").write_text("s")
            (root / "escape").symlink_to(outside, target_is_directory=True)
            # A non-escaping symlink inside the root for contrast.
            (root / "target.txt").write_text("t")
            (root / "inside").symlink_to(root / "target.txt")
            m = manifest.build(str(root))
            by_path = {e["path"]: e for e in m["entries"]}
            self.assertEqual(by_path["escape"]["policy_outcome"], "symlink-escape")
            self.assertEqual(by_path["inside"]["policy_outcome"], "symlink-forbidden")
            for p in ("escape", "inside"):
                self.assertEqual(by_path[p]["kind"], "symlink")
                self.assertIsNone(by_path[p]["digest"])

    def test_case_collision_rejected(self):
        """Deleting the collision guard must break this test (coh-id-02)."""
        from hub.coherence import manifest
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "s"
            root.mkdir()
            (root / "Alpha.txt").write_text("a")
            with self.assertRaises(manifest.SubjectError):
                # Force a collision on the casefolded key.
                manifest._check_collision({"alpha.txt": "Alpha.txt"}, "ALPHA.txt")

    def test_evaluator_reading_time_is_not_deterministic_pass(self):
        """The slice denies undeclared inputs by construction: built-ins receive
        only (assertion, package, subject_root) and no clock. A registry of
        non-built-ins resolves to UNRESOLVED, so time-reading evaluators can
        never pass (coh-eval-01 scenario)."""
        from hub.coherence import evaluate
        a = fx.assertion(aid="time-reader",
                         evaluator={"id": "devgate.time-dependent", "digest": "sha256:" + "c" * 64})
        out = evaluate.run([a], {}, ".")
        self.assertEqual(out["ledger"][0]["outcome"], "UNRESOLVED")


def _digest_of(root: Path) -> str:
    from hub.coherence import manifest
    return manifest.build(str(root))["subject_digest"]


class TestFixtureF_EvidenceTamper(unittest.TestCase):
    def test_tamper_after_seal_fails_verification(self):
        from hub.coherence import evidence
        with tempfile.TemporaryDirectory() as td:
            findings = [{
                "assertion_id": "a1", "finding_key": "a1|x|identity-mismatch",
                "outcome": "VIOLATED", "enforcement": "BLOCK", "severity": "high",
                "subject_locations": ["README.md"], "expected": "widget",
                "observed": "other", "evidence_refs": [],
            }]
            digest = evidence.seal(findings, td)
            (Path(td) / "evidence" / "findings" / "a1.json").write_text('{"tampered":1}')
            self.assertFalse(evidence.verify(td, digest))

    def test_manifest_tamper_fails_verification(self):
        from hub.coherence import evidence
        with tempfile.TemporaryDirectory() as td:
            findings = [{
                "assertion_id": "a1", "finding_key": "a1|x|identity-mismatch",
                "outcome": "VIOLATED", "enforcement": "BLOCK", "severity": "high",
                "subject_locations": ["README.md"], "expected": "widget",
                "observed": "other", "evidence_refs": [],
            }]
            digest = evidence.seal(findings, td)
            mp = Path(td) / "evidence-manifest.json"
            m = json.loads(mp.read_text())
            m["objects"][0]["digest"] = "sha256:" + "0" * 64
            mp.write_text(json.dumps(m))
            self.assertFalse(evidence.verify(td, digest))




if __name__ == "__main__":
    unittest.main()
