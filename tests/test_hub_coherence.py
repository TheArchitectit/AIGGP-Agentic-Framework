# // spec: coh-id-01, coh-id-02, coh-dec-01, coh-dec-04, coh-eval-02, coh-assert-02
"""S2 thin-slice tests for the spec-coherence core. Dual-runnable: pytest + __main__.

Fixtures are synthetic (labeled per R9) and built in tmp dirs. No network, no
real repos, deterministic.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import canon, context, evaluate, manifest, package, plan, result
from hub.coherence import evaluators


def _mk_package(root: Path, approved_name="widget", with_assertions=True) -> Path:
    """Build a minimal valid package on disk with a real normative inventory."""
    pkg = root / "pkg"
    specs = pkg / "specs"
    specs.mkdir(parents=True)
    # A normative assertion file.
    assertion = {
        "id": "product.current-game-identity", "version": 1,
        "requirement_refs": ["prod-identity-01"], "owner": "portfolio-owner",
        "requirement": "docs and artifact metadata name the approved product",
        "subjects": [
            {"kind": "file", "path": "README.md"},
            {"kind": "artifact-metadata", "selector": "product.identity.name"},
        ],
        "evaluator": {"id": "devgate.builtin.identity-consistency",
                      "digest": "sha256:" + "a" * 64},
        "parameters": {"approved_value_ref": "package:product.identity.name",
                       "normalization": "trim-casefold"},
        "severity": "high", "dependencies": [],
        "finding_key": ["assertion_id", "subject_location", "violation_class"],
        "evidence": {"retention_days": 365},
    }
    (specs / "product-identity.json").write_text(json.dumps(assertion))
    # Normative inventory with real digests.
    inv_entries = []
    for f in sorted(specs.glob("*.json")):
        inv_entries.append({
            "path": str(f.relative_to(pkg)), "kind": "normative",
            "digest": canon.digest_bytes("file/v1", f.read_bytes()),
        })
    manifest = {
        "schema_version": "devgate.openspec.package/v1",
        "package_id": "com.test.widget",
        "package_version": "2026.09.17",
        "product": {"identity": {"name": approved_name}},
        "normative_inventory": inv_entries,
        "imports": [],
    }
    (pkg / "package.json").write_text(json.dumps(manifest))
    return pkg


def _mk_subject(root: Path, readme_text: str) -> Path:
    subj = root / "subject"
    subj.mkdir()
    (subj / "README.md").write_text(readme_text)
    return subj


def _mk_context(root: Path, stage=1, semantics="fresh-promotion") -> Path:
    cdir = root / "ctx"
    cdir.mkdir()
    ctx = {
        "api_version": "devgate.spec-coherence.context/v1",
        "context_id": "test-ctx",
        "evaluation_time": "2026-09-17T00:00:00Z",
        "stage": stage, "semantics": semantics,
        "baseline_set_digest": None, "exception_set_digest": None,
        "signer_set_digest": None,
        "capability_grants": [], "captured_facts": [],
        "execution_profile": "linux-amd64-v1",
        "supported_runners": ["linux-amd64-v1"],
        "issuance": {"issued_at": "2026-09-17T00:00:00Z", "issuer": "test-control-plane"},
    }
    (cdir / "context.json").write_text(json.dumps(ctx))
    return cdir


class TestCanon(unittest.TestCase):
    def test_canonical_json_sorted(self):
        b = canon.canon({"b": 1, "a": 2})
        self.assertEqual(b, b'{"a":2,"b":1}')

    def test_float_rejected(self):
        with self.assertRaises(canon.CanonError):
            canon.canon({"x": 1.5})

    def test_int64_bounds(self):
        with self.assertRaises(canon.CanonError):
            canon.canon({"x": 2 ** 63})

    def test_domain_separation(self):
        data = b"same bytes"
        a = canon.digest("file/v1", data)
        b = canon.digest("subject-manifest/v1", data)
        self.assertNotEqual(a, b)

    def test_raw_byte_lf_crlf_differ(self):
        self.assertNotEqual(
            canon.digest_bytes("file/v1", b"hello\n"),
            canon.digest_bytes("file/v1", b"hello\r\n"))


class TestManifest(unittest.TestCase):
    def test_build_and_digest_stable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _mk_subject(root, "# widget\n")
            m1 = manifest.build(str(root / "subject"))
            m2 = manifest.build(str(root / "subject"))
            self.assertEqual(m1["subject_digest"], m2["subject_digest"])
            self.assertEqual(len(m1["entries"]), 1)
            self.assertEqual(m1["entries"][0]["path"], "README.md")

    def test_missing_root(self):
        with self.assertRaises(manifest.SubjectError):
            manifest.build("/nonexistent-coherence-test")

    def test_verify_read_detects_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            fp = Path(td) / "f.txt"
            fp.write_text("a")
            d = canon.digest_bytes("file/v1", b"a")
            fp.write_text("b")
            with self.assertRaises(manifest.SubjectError):
                manifest.verify_read(fp, d)


class TestPackage(unittest.TestCase):
    def test_resolve_ok(self):
        with tempfile.TemporaryDirectory() as td:
            pkg = _mk_package(Path(td))
            out = package.resolve(str(pkg))
            self.assertIn("package_digest", out)
            self.assertEqual(out["package_id"], "com.test.widget")

    def test_missing_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(package.PackageError):
                package.resolve(td)

    def test_inventory_digest_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            pkg = _mk_package(Path(td))
            m = json.loads((pkg / "package.json").read_text())
            m["normative_inventory"][0]["digest"] = "sha256:" + "0" * 64
            (pkg / "package.json").write_text(json.dumps(m))
            with self.assertRaises(package.PackageError):
                package.resolve(str(pkg))


class TestContext(unittest.TestCase):
    def test_load_ok(self):
        with tempfile.TemporaryDirectory() as td:
            cdir = _mk_context(Path(td), stage=2)
            ctx = context.load(str(cdir))
            self.assertEqual(ctx["stage"], 2)
            self.assertIn("context_digest", ctx)

    def test_no_issuer_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            cdir = _mk_context(Path(td))
            ctx = json.loads((cdir / "context.json").read_text())
            ctx["issuance"] = {"issued_at": "2026-09-17T00:00:00Z"}
            (cdir / "context.json").write_text(json.dumps(ctx))
            with self.assertRaises(context.ContextError):
                context.load(str(cdir))

    def test_invalid_stage(self):
        with tempfile.TemporaryDirectory() as td:
            cdir = _mk_context(Path(td))
            ctx = json.loads((cdir / "context.json").read_text())
            ctx["stage"] = 9
            (cdir / "context.json").write_text(json.dumps(ctx))
            with self.assertRaises(context.ContextError):
                context.load(str(cdir))


class TestPlan(unittest.TestCase):
    def _assertion(self, aid="a1", deps=None):
        return {
            "id": aid, "version": 1, "requirement_refs": ["r1"], "owner": "o",
            "requirement": "r", "subjects": [{"kind": "file", "path": "x"}],
            "evaluator": {"id": "devgate.builtin.identity-consistency",
                          "digest": "sha256:" + "a" * 64},
            "parameters": {}, "severity": "high", "dependencies": deps or [],
            "evidence": {"retention_days": 1},
        }

    def test_plan_ok(self):
        planned = plan.plan([self._assertion("a1"), self._assertion("a2", ["a1"])], [])
        self.assertEqual([a["id"] for a in planned], ["a1", "a2"])

    def test_duplicate_id(self):
        with self.assertRaises(plan.PlanError):
            plan.plan([self._assertion("a1"), self._assertion("a1")], [])

    def test_cycle(self):
        with self.assertRaises(plan.PlanError):
            plan.plan([self._assertion("a1", ["a2"]), self._assertion("a2", ["a1"])], [])

    def test_central_required_omitted(self):
        with self.assertRaises(plan.PlanError):
            plan.plan([self._assertion("a1")], ["a2"])

    def test_missing_field(self):
        a = self._assertion("a1")
        del a["owner"]
        with self.assertRaises(plan.PlanError):
            plan.plan([a], [])


class TestEvaluate(unittest.TestCase):
    def test_identity_satisfied(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pkg = _mk_package(root, approved_name="widget")
            _mk_subject(root, "# product: widget\n")
            p = package.resolve(str(pkg))
            a = json.loads((pkg / "specs" / "product-identity.json").read_text())
            fs = evaluators.identity_consistency(a, p, str(root / "subject"))
            self.assertEqual(fs, [])

    def test_identity_unapproved_consistent(self):
        # README and artifact metadata agree on "other", but the package
        # approves "widget" -> VIOLATED (coh-assert-02): agreement is not
        # approval; identity assertions compare against the approved value.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pkg = _mk_package(root, approved_name="widget")
            _mk_subject(root, "# product: other\n")
            p = package.resolve(str(pkg))
            a = json.loads((pkg / "specs" / "product-identity.json").read_text())
            # Artifact metadata declares "other" (matches README, not the
            # approved "widget").
            a["subjects"][1]["selector"] = "product.identity.name"
            fs = evaluators.identity_consistency(a, p, str(root / "subject"))
            self.assertTrue(fs, "expected a violation: both fields declare 'other', approved is 'widget'")
            self.assertTrue(all(f["expected"] == "widget" for f in fs))

    def test_identity_empty_selector_unresolved(self):
        # README has no declared product line -> empty selector -> UNRESOLVED
        # (coh-assert-02), never VIOLATED and never SATISFIED.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pkg = _mk_package(root, approved_name="widget")
            _mk_subject(root, "# just a readme\n")
            p = package.resolve(str(pkg))
            a = json.loads((pkg / "specs" / "product-identity.json").read_text())
            with self.assertRaises(evaluators.Unresolved) as c:
                evaluators.identity_consistency(a, p, str(root / "subject"))
            self.assertIn("selector-empty", str(c.exception))

    def test_empty_selector_ledger_is_unresolved_not_violated(self):
        # End-to-end: the runtime maps Unresolved to an UNRESOLVED ledger entry.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pkg = _mk_package(root, approved_name="widget")
            _mk_subject(root, "# just a readme\n")
            p = package.resolve(str(pkg))
            a = json.loads((pkg / "specs" / "product-identity.json").read_text())
            out = evaluate.run([a], p, str(root / "subject"))
            e = out["ledger"][0]
            self.assertEqual(e["outcome"], "UNRESOLVED")
            self.assertIn("selector-empty", e["reason"])

    def test_artifact_metadata_empty_selector_unresolved(self):
        # Round-8 spec audit (finding 4): the artifact-metadata selector path
        # resolves empty the same way the file path does — UNRESOLVED with
        # the selector named, never VIOLATED, never SATISFIED (coh-assert-02).
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pkg = _mk_package(root, approved_name="widget")
            _mk_subject(root, "# product: widget\n")
            p = package.resolve(str(pkg))
            a = json.loads((pkg / "specs" / "product-identity.json").read_text())
            for sel in ("product.identity.missing", ""):
                a["subjects"] = [{"kind": "artifact-metadata", "selector": sel}]
                with self.assertRaises(evaluators.Unresolved) as c:
                    evaluators.identity_consistency(a, p, str(root / "subject"))
                self.assertIn("selector-empty", str(c.exception))

    def test_unapproved_evaluator_unresolved(self):
        a = {
            "id": "a1", "version": 1, "requirement_refs": ["r1"], "owner": "o",
            "requirement": "r", "subjects": [{"kind": "file", "path": "x"}],
            "evaluator": {"id": "unapproved.evil", "digest": "sha256:" + "b" * 64},
            "parameters": {}, "severity": "high", "dependencies": [],
            "evidence": {"retention_days": 1},
        }
        out = evaluate.run([a], {}, ".")
        self.assertEqual(out["ledger"][0]["outcome"], "UNRESOLVED")
        self.assertEqual(out["ledger"][0]["reason"], "unapproved-evaluator")

    def test_dependency_blocked(self):
        dep = {
            "id": "dep", "version": 1, "requirement_refs": ["r1"], "owner": "o",
            "requirement": "r", "subjects": [{"kind": "file", "path": "x"}],
            "evaluator": {"id": "unapproved.evil", "digest": "sha256:" + "b" * 64},
            "parameters": {}, "severity": "high", "dependencies": [],
            "evidence": {"retention_days": 1},
        }
        main = dict(dep, id="main", dependencies=["dep"],
                    evaluator={"id": "devgate.builtin.identity-consistency",
                               "digest": "sha256:" + "a" * 64})
        out = evaluate.run([dep, main], {}, ".")
        self.assertEqual(out["ledger"][0]["outcome"], "UNRESOLVED")
        self.assertEqual(out["ledger"][1]["reason"], "dependency-blocked")


class TestResult(unittest.TestCase):
    def test_matrix_enforced_violated(self):
        ledger = [{"outcome": "VIOLATED"}, {"outcome": "SATISFIED"}]
        d, code = result.decide(ledger, stage=2)
        self.assertEqual((d, code), ("FAIL", result.EXIT_FAIL))

    def test_matrix_advisory_violated(self):
        ledger = [{"outcome": "VIOLATED"}]
        d, code = result.decide(ledger, stage=1)
        self.assertEqual((d, code), ("ADVISORY", result.EXIT_ADVISORY))

    def test_matrix_error_dominates(self):
        ledger = [{"outcome": "VIOLATED"}]
        d, code = result.decide(ledger, stage=2, error_class="evaluator")
        self.assertEqual((d, code), ("ERROR", result.EXIT_EXECUTION))

    def test_matrix_pass(self):
        ledger = [{"outcome": "SATISFIED"}]
        d, code = result.decide(ledger, stage=4)
        self.assertEqual((d, code), ("PASS", result.EXIT_PASS))

    def test_unresolved_enforced_blocks(self):
        ledger = [{"outcome": "UNRESOLVED"}]
        d, code = result.decide(ledger, stage=2)
        self.assertEqual((d, code), ("FAIL", result.EXIT_FAIL))

    def test_findings_sorted(self):
        findings = [
            {"assertion_id": "b", "finding_key": "b|x|c", "subject_locations": ["x"], "outcome": "VIOLATED", "enforcement": "BLOCK", "severity": "high", "expected": "e", "observed": "o", "evidence_refs": []},
            {"assertion_id": "a", "finding_key": "a|y|c", "subject_locations": ["y"], "outcome": "VIOLATED", "enforcement": "BLOCK", "severity": "high", "expected": "e", "observed": "o", "evidence_refs": []},
        ]
        s = result._sort_findings(findings)
        self.assertEqual([f["assertion_id"] for f in s], ["a", "b"])

    def test_canonical_no_error_field_nonnull(self):
        res = {
            "api_version": "devgate.spec-coherence.result/v1", "decision": "PASS",
            "semantics": "fresh-promotion", "error": None,
        }
        b = result.to_canonical(res)
        self.assertIn(b'"error":null', b)


class TestEvidence(unittest.TestCase):
    def test_seal_and_verify(self):
        from hub.coherence import evidence
        with tempfile.TemporaryDirectory() as td:
            findings = [{
                "assertion_id": "a1", "finding_key": "a1|x|identity-mismatch",
                "outcome": "VIOLATED", "enforcement": "BLOCK", "severity": "high",
                "subject_locations": ["README.md"], "expected": "widget",
                "observed": "other", "evidence_refs": [],
            }]
            digest = evidence.seal(findings, td)
            self.assertTrue(evidence.verify(td, digest))

    def test_tamper_detected(self):
        from hub.coherence import evidence
        with tempfile.TemporaryDirectory() as td:
            findings = [{
                "assertion_id": "a1", "finding_key": "a1|x|identity-mismatch",
                "outcome": "VIOLATED", "enforcement": "BLOCK", "severity": "high",
                "subject_locations": ["README.md"], "expected": "widget",
                "observed": "other", "evidence_refs": [],
            }]
            digest = evidence.seal(findings, td)
            # Tamper with the sealed finding. Object names are content-derived
            # (one file per finding), so resolve the path from the manifest
            # rather than reconstructing it — a guessed name would silently
            # create a stray file and leave the real object untouched.
            manifest = json.loads((Path(td) / "evidence-manifest.json").read_text())
            p = Path(td) / manifest["objects"][0]["path"]
            self.assertTrue(p.is_file(), "manifest must point at a real object")
            p.write_text('{"tampered":true}')
            self.assertFalse(evidence.verify(td, digest))


class TestTraceabilityMarkerScan(unittest.TestCase):
    """Repo-marker half of traceability_completeness (coh-assert-04,
    coh-eval-04): parameters.marker_scan consumes the repo's `// spec:`
    convention, mirroring scripts/spec_traceability.py."""

    PKG = {"normative_requirements": {
        "r1": {"testable": True, "assertion_ids": ["trace.coverage"]},
        "r2": {"testable": True, "assertion_ids": ["trace.coverage"]},
        "r3": {"testable": False},
    }}

    @staticmethod
    def _assertion():
        return {
            "id": "trace.coverage", "version": 1,
            "requirement_refs": ["r1"], "owner": "o", "requirement": "r",
            "subjects": [{"kind": "file", "path": "src/app.py"}],
            "evaluator": {"id": "devgate.builtin.traceability-completeness",
                          "digest": "sha256:" + "c" * 64},
            "parameters": {"marker_scan": True}, "severity": "medium",
            "dependencies": [], "finding_key": ["a", "l", "v"],
            "evidence": {"retention_days": 1},
        }

    def test_multi_id_marker_line_covers_all(self):
        # One comma-separated marker line claims both ids; the trailing
        # comment stays out of the captured ids.
        with tempfile.TemporaryDirectory() as td:
            subj = Path(td) / "subject"
            (subj / "src").mkdir(parents=True)
            (subj / "src" / "app.py").write_text("// spec: r1, r2 -- why\n")
            fs = evaluators.traceability_completeness(
                self._assertion(), dict(self.PKG), str(subj))
            self.assertEqual(fs, [])

    def test_unmarked_requirement_reported_with_distinct_key(self):
        with tempfile.TemporaryDirectory() as td:
            subj = Path(td) / "subject"
            (subj / "src").mkdir(parents=True)
            (subj / "src" / "app.py").write_text("// spec: r1\n")
            fs = evaluators.traceability_completeness(
                self._assertion(), dict(self.PKG), str(subj))
            self.assertEqual(len(fs), 1)
            self.assertEqual(fs[0]["violation_class"], "unmarked-requirement")
            self.assertEqual(fs[0]["subject_locations"], ["r2"])
            self.assertIn("r2", fs[0]["finding_key"])

    def test_trailing_prose_cannot_fake_coverage(self):
        # The id grammar is comma-anchored: `-- why r2` after the marker
        # must not be read as covering r2.
        with tempfile.TemporaryDirectory() as td:
            subj = Path(td) / "subject"
            (subj / "src").mkdir(parents=True)
            (subj / "src" / "app.py").write_text("// spec: r1 -- why r2\n")
            fs = evaluators.traceability_completeness(
                self._assertion(), dict(self.PKG), str(subj))
            self.assertEqual([f["subject_locations"][0] for f in fs], ["r2"])

    def test_skip_dirs_do_not_cover(self):
        # node_modules/.git/etc. are skipped: a marker only in vendored
        # code does not count (same convention as spec_traceability.py).
        with tempfile.TemporaryDirectory() as td:
            subj = Path(td) / "subject"
            (subj / "node_modules").mkdir(parents=True)
            (subj / "node_modules" / "dep.py").write_text("// spec: r2\n")
            fs = evaluators.traceability_completeness(
                self._assertion(), dict(self.PKG), str(subj))
            # r2's only marker sits in a skipped dir, so both ids are
            # reported unmarked — vendored coverage does not count.
            self.assertEqual(sorted(f["subject_locations"][0] for f in fs),
                             ["r1", "r2"])

    def test_off_by_default(self):
        a = self._assertion()
        a["parameters"] = {}
        with tempfile.TemporaryDirectory() as td:
            subj = Path(td) / "subject"
            subj.mkdir()
            fs = evaluators.traceability_completeness(a, dict(self.PKG), str(subj))
            self.assertEqual(fs, [])

    def test_missing_subject_root_unresolved(self):
        # A missing tree would report every requirement unmarked; that is
        # an unresolvable input (coh-assert-02), never a violation.
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(evaluators.Unresolved) as c:
                evaluators.traceability_completeness(
                    self._assertion(), dict(self.PKG), str(Path(td) / "nope"))
            self.assertIn("subject-root-missing", str(c.exception))


class TestSubmodulePin(unittest.TestCase):
    """Submodule commit-pinning in the manifest (coh-id-02, round-1
    partial): the pinned commit is captured from gitdir metadata; an
    unresolvable pin is recorded `submodule-unresolved`, never a
    `submodule-pinned` claim without a named pin."""

    @staticmethod
    def _mk_gitlink(root: Path, gitdir_body: dict) -> Path:
        """A `.git` file pointing at a fake gitdir shaped by gitdir_body:
        keys are file names relative to the gitdir, values their content."""
        sub = root / "vendor"
        sub.mkdir(parents=True)
        (sub / ".git").write_text("gitdir: ../.git/modules/vendor\n")
        gd = root / ".git" / "modules" / "vendor"
        for name, content in gitdir_body.items():
            fp = gd / name
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content)
        return root

    SHA_A = "a" * 40
    SHA_B = "b" * 40

    def _vendor_outcome(self, root):
        m = manifest.build(str(root))
        return {e["path"]: e for e in m["entries"]}["vendor"]["policy_outcome"]

    def test_detached_head_captured(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._mk_gitlink(Path(td), {"HEAD": self.SHA_A + "\n"})
            self.assertEqual(self._vendor_outcome(root),
                             f"submodule-pinned:{self.SHA_A}")

    def test_loose_ref_captured(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._mk_gitlink(Path(td), {
                "HEAD": f"ref: refs/heads/main\n",
                "refs/heads/main": self.SHA_B + "\n"})
            self.assertEqual(self._vendor_outcome(root),
                             f"submodule-pinned:{self.SHA_B}")

    def test_packed_ref_captured(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._mk_gitlink(Path(td), {
                "HEAD": f"ref: refs/heads/main\n",
                "packed-refs": f"{self.SHA_A} refs/heads/main\n"})
            self.assertEqual(self._vendor_outcome(root),
                             f"submodule-pinned:{self.SHA_A}")

    def test_absolute_gitdir_captured(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "s"
            sub = root / "vendor"
            sub.mkdir(parents=True)
            gd = Path(td) / "elsewhere" / "gitdir"
            gd.mkdir(parents=True)
            (sub / ".git").write_text(f"gitdir: {gd}\n")
            (gd / "HEAD").write_text(self.SHA_A + "\n")
            self.assertEqual(self._vendor_outcome(root),
                             f"submodule-pinned:{self.SHA_A}")

    def test_unresolvable_pin_is_submodule_unresolved(self):
        # No gitdir at all: fail-honest unresolved, never a bare
        # submodule-pinned claim.
        with tempfile.TemporaryDirectory() as td:
            root = self._mk_gitlink(Path(td), {})
            self.assertEqual(self._vendor_outcome(root), "submodule-unresolved")

    def test_dangling_ref_is_unresolved(self):
        # HEAD points at a ref that neither loose nor packed-refs resolve.
        with tempfile.TemporaryDirectory() as td:
            root = self._mk_gitlink(Path(td), {"HEAD": "ref: refs/heads/gone\n"})
            self.assertEqual(self._vendor_outcome(root), "submodule-unresolved")

    def test_real_git_submodule_pin_matches_gitlink(self):
        # A REAL submodule (git submodule add): the manifest's captured pin
        # must equal the gitlink SHA git itself recorded in the index.
        import shutil
        import subprocess
        git = shutil.which("git")
        if git is None:
            self.skipTest("git not available")
        with tempfile.TemporaryDirectory() as td:
            upstream = Path(td) / "upstream"
            upstream.mkdir()
            (upstream / "seed.txt").write_text("seed\n")
            for args in (["init", "-q"], ["config", "user.email", "t@t"],
                         ["config", "user.name", "t"],
                         ["add", "-A"], ["commit", "-qm", "seed"]):
                subprocess.run([git, "-C", str(upstream)] + args, check=True)
            subject = Path(td) / "subject"
            subject.mkdir()
            (subject / "seed.txt").write_text("seed\n")
            for args in (["init", "-q"], ["config", "user.email", "t@t"],
                         ["config", "user.name", "t"],
                         ["add", "-A"], ["commit", "-qm", "seed"]):
                subprocess.run([git, "-C", str(subject)] + args, check=True)
            subprocess.run([git, "-C", str(subject), "-c",
                            "protocol.file.allow=always", "submodule", "add",
                            "-q", str(upstream), "vendor"], check=True)
            ls = subprocess.run(
                [git, "-C", str(subject), "ls-files", "-s", "vendor"],
                check=True, capture_output=True, text=True).stdout
            gitlink_sha = ls.split()[1]
            self.assertEqual(self._vendor_outcome(subject),
                             f"submodule-pinned:{gitlink_sha}")


if __name__ == "__main__":
    unittest.main()
