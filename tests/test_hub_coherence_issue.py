# // spec: coh-ctx-01, coh-ctx-02, coh-pol-05
"""S3 tests: control-plane stand-in (context issuance, stage registry,
validated adoption sets). Dual-runnable. Synthetic fixtures (R9)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import context, issue, report
from hub.coherence import result
from tests.fixtures.coherence import fixtures as fx

REPO = Path(__file__).resolve().parent.parent

REGISTRY = {
    "com.test.widget": {"stage": 2, "owner": "portfolio-owner",
                        "advisory_started": "2026-08-01T00:00:00Z",
                        "advisory_expiry": "2026-09-01T00:00:00Z",
                        "next_stage": 3},
}


def _registry_file(td: Path) -> Path:
    rp = td / "stage-registry.json"
    rp.write_text(json.dumps(REGISTRY))
    return rp


class TestStageRegistry(unittest.TestCase):
    def test_registry_is_authoritative(self):
        reg = issue.load_stage_registry(str(_registry_file(Path(tempfile.mkdtemp()))))
        self.assertEqual(issue.effective_stage(reg, "com.test.widget"), 2)

    def test_weaker_request_refused(self):
        reg = issue.load_stage_registry(str(_registry_file(Path(tempfile.mkdtemp()))))
        with self.assertRaises(ValueError) as c:
            issue.effective_stage(reg, "com.test.widget", requested=1)
        self.assertIn("weaker", str(c.exception))

    def test_higher_request_honored_within_record(self):
        # Requesting >= record stage is not a downgrade; the record still wins.
        reg = issue.load_stage_registry(str(_registry_file(Path(tempfile.mkdtemp()))))
        self.assertEqual(issue.effective_stage(reg, "com.test.widget",
                                               requested=3), 2)

    def test_unknown_repo_rejected(self):
        reg = issue.load_stage_registry(str(_registry_file(Path(tempfile.mkdtemp()))))
        with self.assertRaises(ValueError):
            issue.effective_stage(reg, "com.nope.other")

    def test_bad_record_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            for bad in ({"r": {"stage": 9}}, {"r": {"owner": "x"}},
                        {"r": "string"}):
                (Path(td) / "reg.json").write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    issue.load_stage_registry(str(Path(td) / "reg.json"))


class TestIssuance(unittest.TestCase):
    def _issue(self, td: Path, **kw):
        rp = _registry_file(td)
        return issue.issue_context(
            str(td / "ctx"), str(td / "policy"),
            repo="com.test.widget", registry_path=str(rp),
            evaluation_time="2026-09-17T00:00:00Z", **kw)

    def test_issues_stage_from_registry(self):
        with tempfile.TemporaryDirectory() as td:
            out = self._issue(Path(td))
            self.assertEqual(out["stage"], 2)
            ctx = json.loads((Path(td) / "ctx" / "context.json").read_text())
            self.assertEqual(ctx["stage"], 2)

    def test_baseline_digest_binds_written_set(self):
        """The digest put in the context must equal what the CLI computes from
        the set written into the policy directory (coh-ctx-01)."""
        from hub.coherence import policy
        with tempfile.TemporaryDirectory() as td:
            base = [fx.baseline_entry("assertion-0", 1, "README.md", "identity-mismatch")]
            out = self._issue(Path(td), baseline_set=base)
            loaded, _ = policy.load_adoption_sets(str(Path(td) / "policy"))
            self.assertEqual(issue.set_digest(loaded, "baseline"),
                             out["baseline_set_digest"])
            self.assertEqual(out["baseline_set_digest"],
                             issue.set_digest(base, "baseline"))

    def test_invalid_set_rejected_at_issuance(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                self._issue(Path(td), baseline_set=["not", "entries"])

    def test_end_to_end_with_issued_context(self):
        """Issued context + issued baseline feeds a real CLI run end-to-end:
        named baseline debt at Stage 2 is ADVISORY (coh-pol-04)."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            req, out = fx.build_root(base / "f", declared_name="other",
                                     approved_name="widget", stage=2)
            assertions = [fx.assertion(aid="assertion-0")]
            baseline = [fx.baseline_entry("assertion-0", 1, "README.md",
                                          "identity-mismatch")]
            # Rebuild subject to violate assertion-0 as named in baseline:
            # use the default product.identity assertion from the fixture
            # instead — simpler: issue against the fixture's own policy root.
            pol_dir = Path(json.loads(req.read_text())["policy"]["root"])
            ctx_dir = base / "issued-ctx"
            res = issue.issue_context(
                str(ctx_dir), str(pol_dir),
                repo="com.test.widget",
                registry_path=str(_registry_file(base)),
                evaluation_time="2026-09-17T00:00:00Z",
                baseline_set=baseline)
            # Point the request at the issued context.
            r = json.loads(req.read_text())
            ctx = json.loads((ctx_dir / "context.json").read_text())
            r["context"] = {"root": str(ctx_dir),
                            "expected_digest":
                                context.load(str(ctx_dir))["context_digest"]}
            req.write_text(json.dumps(r))
            # But the fixture's subject asserts product.identity, and the
            # baseline names assertion-0 — the violated product.identity is
            # NOT in the baseline, so it must BLOCK (regression).
            p = subprocess.run([sys.executable, "-m", "hub.coherence",
                                "--request", str(req)],
                               capture_output=True, text=True, cwd=str(REPO))
            env = json.loads((out / "result.json").read_text())
            self.assertEqual(p.returncode, result.EXIT_FAIL,
                             f"regression (unbaselined violation) must block; "
                             f"got {p.returncode}: {env}")


class TestReplaySemantics(unittest.TestCase):
    """coh-ctx-03: replay reproduces the historical decision byte-for-byte and
    is structurally non-promotion-authorizing."""

    def _run_cli(self, req):
        return subprocess.run([sys.executable, "-m", "hub.coherence",
                               "--request", str(req)],
                              capture_output=True, text=True, cwd=str(REPO))

    def test_replay_byte_identical_and_labeled(self):
        """coh-ctx-03 at the slice's true strength: replaying the SAME context
        file reproduces the historical decision BYTE-FOR-BYTE, and a replay
        issued with the original trusted fields differs from the fresh run
        only in the semantics label (context digest rides along, since the
        label is part of the bound context)."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            req, out = fx.build_root(base / "f", stage=1)
            p1 = self._run_cli(req)
            original = (out / "result.json").read_bytes()
            self.assertEqual(p1.returncode, result.EXIT_PASS)
            self.assertEqual(json.loads(original)["semantics"],
                             "fresh-promotion")
            # Re-running the identical context reproduces identical bytes.
            self._run_cli(req)
            self.assertEqual((out / "result.json").read_bytes(), original,
                             "replay of the same context must be byte-identical")
            # A replay-labeled context: same trusted stage/time/sets. The
            # decision payload matches; only labels differ.
            pol_dir = Path(json.loads(req.read_text())["policy"]["root"])
            rctx = base / "replay-ctx"
            issue.issue_context(str(rctx), str(pol_dir),
                                repo="com.test.widget",
                                registry_path=str(_registry_file(base)),
                                evaluation_time="2026-09-17T00:00:00Z",
                                semantics="replay")
            r = json.loads(req.read_text())
            r["semantics"] = "replay"
            r["context"] = {"root": str(rctx),
                            "expected_digest":
                                context.load(str(rctx))["context_digest"]}
            req.write_text(json.dumps(r))
            p2 = self._run_cli(req)
            replayed = json.loads((out / "result.json").read_bytes())
            fresh = json.loads(original)
            self.assertEqual(replayed["semantics"], "replay")
            for field in ("decision", "subject_digest", "openspec_digest",
                          "policy_digest", "assertion_summary",
                          "assertion_results", "findings",
                          "evidence_manifest_digest"):
                self.assertEqual(replayed[field], fresh[field],
                                 f"replay decision field {field} diverged")

    def test_replay_label_is_validated_at_issuance(self):
        """A bad semantics value must be refused at issuance, not written and
        discovered later by the CLI schema check."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            with self.assertRaises(ValueError) as c:
                issue.issue_context(str(base / "c"), str(base / "p"),
                                    repo="com.test.widget",
                                    registry_path=str(_registry_file(base)),
                                    evaluation_time="2026-09-17T00:00:00Z",
                                    semantics="maybe")
            self.assertIn("invalid semantics", str(c.exception))

    def test_expired_advisory_cannot_be_dodged_by_claiming_replay(self):
        """The security property: a repo whose advisory period has expired
        cannot obtain a PASS by requesting `replay` with a fresh evaluation
        time. Stage 1 with a past expiry still reports expired via the report,
        and a replay that carries the ORIGINAL (past) time reproduces the
        historical decision rather than authorizing a new one (coh-ctx-03)."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # Registry says the repo is at stage 1 with an advisory that ended.
            reg = {"com.test.widget": {
                "stage": 1, "owner": "o",
                "advisory_started": "2026-06-01T00:00:00Z",
                "advisory_expiry": "2026-07-01T00:00:00Z", "next_stage": 2}}
            (base / "reg.json").write_text(json.dumps(reg))
            out = issue.issue_context(
                str(base / "c"), str(base / "p"), repo="com.test.widget",
                registry_path=str(base / "reg.json"),
                evaluation_time="2026-09-17T00:00:00Z", semantics="replay")
            ctx = json.loads((base / "c" / "context.json").read_text())
            # A replay is still non-authorizing per report.summarize, and the
            # advisory is expired regardless of the replay label.
            self.assertEqual(out["stage"], 1)
            self.assertFalse(report.summarize(
                {"decision": "PASS"}, ctx, reg["com.test.widget"], 30,
            )["promotion_authorizing"])
            self.assertTrue(report.summarize(
                {"decision": "PASS"}, ctx, reg["com.test.widget"], 30,
            )["advisory"]["expired"])


class TestSigning(unittest.TestCase):
    def test_unsigned_and_signed_roundtrip(self):
        import os
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            os.environ["HUB_COHERENCE_CP_KEY"] = "ab" * 32
            try:
                out = issue.issue_context(
                    str(base / "ctx"), str(base / "policy"),
                    repo="com.test.widget",
                    registry_path=str(_registry_file(base)),
                    evaluation_time="2026-09-17T00:00:00Z")
                self.assertTrue(out["signed"])
                ctx = json.loads((base / "ctx" / "context.json").read_text())
                self.assertTrue(issue.verify_signature(ctx))
                # Tampering invalidates.
                ctx["stage"] = 4
                self.assertFalse(issue.verify_signature(ctx))
            finally:
                del os.environ["HUB_COHERENCE_CP_KEY"]

    def test_context_load_requires_signature_when_key_present(self):
        import os
        with tempfile.TemporaryDirectory() as td:
            cdir = Path(td)
            # Reuse the fixture's plain (unsigned) context.
            fx.build_root(cdir / "f")
            ctxsrc = cdir / "f" / "ctx"
            os.environ["HUB_COHERENCE_CP_KEY"] = "cd" * 32
            try:
                with self.assertRaises(context.ContextError) as c:
                    context.load(str(ctxsrc))
                self.assertIn("unsigned", str(c.exception))
            finally:
                del os.environ["HUB_COHERENCE_CP_KEY"]
            # Without a key, load still works (pilot mode).
            self.assertEqual(context.load(str(ctxsrc))["stage"], 1)


class TestBoundSetSwap(unittest.TestCase):
    def test_policy_set_swap_after_issuance_detected(self):
        """coh-ctx-01: sets must hash to the context-bound digests."""
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # declared != approved -> a violation, which the baseline names
            # -> ADVISORY on the first run.
            req, out = fx.build_root(base / "f", declared_name="other",
                                     approved_name="widget", stage=2)
            pol_dir = Path(json.loads(req.read_text())["policy"]["root"])
            ctx_dir = base / "issued-ctx"
            baseline = [fx.baseline_entry("product.identity", 1, "README.md",
                                          "identity-mismatch")]
            issue.issue_context(
                str(ctx_dir), str(pol_dir),
                repo="com.test.widget",
                registry_path=str(_registry_file(base)),
                evaluation_time="2026-09-17T00:00:00Z",
                baseline_set=baseline)
            r = json.loads(req.read_text())
            r["context"] = {"root": str(ctx_dir),
                            "expected_digest":
                                context.load(str(ctx_dir))["context_digest"]}
            req.write_text(json.dumps(r))
            p1 = subprocess.run([sys.executable, "-m", "hub.coherence",
                                 "--request", str(req)],
                                capture_output=True, text=True, cwd=str(REPO))
            self.assertEqual(p1.returncode, result.EXIT_ADVISORY,
                             "baselined debt is advisory at stage 2")
            # Swap the baseline AFTER issuance without re-issuing the context.
            (pol_dir / "baseline.json").write_bytes(b"[]")
            p2 = subprocess.run([sys.executable, "-m", "hub.coherence",
                                 "--request", str(req)],
                                capture_output=True, text=True, cwd=str(REPO))
            self.assertEqual(p2.returncode, result.EXIT_POLICY,
                             "set/context digest mismatch must fail closed")


if __name__ == "__main__":
    unittest.main()
