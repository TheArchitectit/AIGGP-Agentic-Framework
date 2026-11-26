#!/usr/bin/env python3
# spec: coh-sec-01
"""Gate-side path containment (coh-sec-01).

`coh-sec-01` says every path originating from repository-supplied content is
contained under its declared root before any read. The coherence service
enforces that (tests/test_hub_coherence_containment.py); the *gates* did not.
Each gate below takes paths out of a committed config file or out of scanned
content and handed them straight to `read_text` / `read_bytes` / `rglob`:

  * `check_manifest_join.py`  — `.guardrails/manifest-joins.json` paths
  * `spec-fleet-classify.py`  — the templates lock's `vendored_path`
  * `regression_corpus.py`    — the failure registry's `affected_files`
  * `findings_to_spec.py`     — `--capability` / a finding's `category`, which
                                becomes a directory it CREATES and APPENDS to

Every case below plants a HOST SECRET outside the fixture root and asserts two
things: the gate refuses (its own exit/fault vocabulary, with a reason naming
the path), and the secret never appears in the gate's output. The second half
is the point — a rejection that still echoed the bytes would not be
containment.

The shared primitive is `gate_common.contained_path`, tested here directly so
a regression in it fails one obvious test rather than five subtly different
ones.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
PYTHON = sys.executable

sys.path.insert(0, str(SCRIPTS))

from gate_common import contained_path  # noqa: E402

MARKER = "LEAKED-HOST-SECRET"


def _host_secret(tmp: Path) -> Path:
    """A file outside every fixture root, beside it (one level up)."""
    p = tmp / "host-secret.txt"
    p.write_text(f"# {MARKER}\n", encoding="utf-8")
    return p


class TestContainedPath(unittest.TestCase):
    """The primitive: reject invalid input, never touch the target."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.root = self.tmp / "root"
        (self.root / "inside").mkdir(parents=True)
        (self.root / "inside" / "ok.txt").write_text("fine", encoding="utf-8")
        _host_secret(self.tmp)

    def tearDown(self):
        self._td.cleanup()

    def test_contained_relative_path_accepted(self):
        p, err = contained_path(self.root, "inside/ok.txt")
        self.assertIsNone(err)
        self.assertEqual(p, (self.root / "inside" / "ok.txt").resolve())

    def test_absolute_rejected(self):
        p, err = contained_path(self.root, str(self.tmp / "host-secret.txt"))
        self.assertIsNone(p)
        self.assertIn("absolute", err)
        self.assertIn("host-secret.txt", err)

    def test_home_relative_rejected(self):
        p, err = contained_path(self.root, "~/host-secret.txt")
        self.assertIsNone(p)
        self.assertIn("absolute", err)

    def test_traversal_rejected(self):
        p, err = contained_path(self.root, "../host-secret.txt")
        self.assertIsNone(p)
        self.assertIn("traversal", err)
        self.assertIn("../host-secret.txt", err)

    def test_interior_traversal_rejected(self):
        # `inside/../../host-secret.txt` does not *start* with `..`; a
        # startswith check would pass it. Every segment is inspected.
        p, err = contained_path(self.root, "inside/../../host-secret.txt")
        self.assertIsNone(p)
        self.assertIn("traversal", err)

    def test_empty_segment_rejected(self):
        p, err = contained_path(self.root, "")
        self.assertIsNone(p)
        self.assertTrue(err, "the empty path must be refused with a reason")
        for rel in ("inside//ok.txt", "./inside/ok.txt"):
            with self.subTest(rel=rel):
                p, err = contained_path(self.root, rel)
                self.assertIsNone(p)
                self.assertIn("traversal", err)

    def test_nul_rejected(self):
        p, err = contained_path(self.root, "inside/ok.txt\x00../../host-secret.txt")
        self.assertIsNone(p)
        self.assertIn("NUL", err)

    def test_symlink_escape_rejected(self):
        (self.root / "link").symlink_to(self.tmp / "host-secret.txt")
        p, err = contained_path(self.root, "link")
        self.assertIsNone(p)
        self.assertIn("escapes", err)

    def test_symlinked_directory_escape_rejected(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "x.txt").write_text(MARKER, encoding="utf-8")
        (self.root / "dirlink").symlink_to(outside)
        p, err = contained_path(self.root, "dirlink/x.txt")
        self.assertIsNone(p)
        self.assertIn("escapes", err)

    def test_symlink_that_stays_inside_accepted(self):
        (self.root / "alias").symlink_to(self.root / "inside" / "ok.txt")
        p, err = contained_path(self.root, "alias")
        self.assertIsNone(err)
        self.assertEqual(p, (self.root / "inside" / "ok.txt").resolve())

    def test_missing_file_inside_root_is_not_a_containment_error(self):
        # Containment answers "may this path be read", not "does it exist";
        # the caller's own missing-file path must stay reachable.
        p, err = contained_path(self.root, "inside/absent.txt")
        self.assertIsNone(err)
        self.assertEqual(p, (self.root / "inside" / "absent.txt").resolve())


class TestManifestJoinContainment(unittest.TestCase):
    """check_manifest_join: the manifest is repository-supplied input."""

    def _run(self, tmp: Path, joins: dict) -> subprocess.CompletedProcess:
        gd = tmp / ".guardrails"
        gd.mkdir(parents=True)
        (gd / "manifest-joins.json").write_text(
            json.dumps({"api_version": "devgate.manifest-joins/v1",
                        "joins": [joins]}), encoding="utf-8")
        (tmp / "decl.txt").write_text("NAME:alpha\n", encoding="utf-8")
        (tmp / "wire.txt").write_text('"alpha"\n', encoding="utf-8")
        return subprocess.run(
            [PYTHON, str(SCRIPTS / "check_manifest_join.py"), "--repo", str(tmp)],
            capture_output=True, text=True, encoding="utf-8", errors="replace")

    def _join(self, paths):
        return {"id": "j", "reason": "because",
                "declared": {"paths": paths, "pattern": "^NAME:(\\w+)"},
                "wired": {"paths": ["wire.txt"], "pattern": '"([a-z_]+)"'},
                "bidirectional": True, "allow_undeclared": []}

    def test_traversal_in_manifest_is_usage_error_and_never_read(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "repo").mkdir()
            _host_secret(tmp)
            r = self._run(tmp / "repo", self._join(["../host-secret.txt"]))
            self.assertEqual(r.returncode, 2, (r.returncode, r.stdout, r.stderr))
            self.assertIn("../host-secret.txt", r.stderr)
            self.assertIn("manifest path refused", r.stderr)
            self.assertIn("traversal", r.stderr)
            self.assertNotIn(MARKER, r.stdout + r.stderr)

    def test_absolute_path_in_manifest_is_usage_error(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "repo").mkdir()
            secret = _host_secret(tmp)
            r = self._run(tmp / "repo", self._join([str(secret)]))
            self.assertEqual(r.returncode, 2, (r.returncode, r.stdout, r.stderr))
            self.assertIn("absolute", r.stderr)
            self.assertNotIn(MARKER, r.stdout + r.stderr)

    def test_contained_manifest_still_agrees(self):
        # The fix must not turn healthy manifests into usage errors.
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "repo").mkdir()
            _host_secret(tmp)
            r = self._run(tmp / "repo", self._join(["decl.txt"]))
            self.assertEqual(r.returncode, 0, (r.stdout, r.stderr))


def _load_classifier():
    spec = importlib.util.spec_from_file_location(
        "spec_fleet_classify", SCRIPTS / "spec-fleet-classify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestProvenanceContainment(unittest.TestCase):
    """spec-fleet-classify: the templates lock's `vendored_path`."""

    def test_vendored_path_traversal_is_a_fault_naming_the_path(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root = tmp / "repo"
            (root / "templates").mkdir(parents=True)
            _host_secret(tmp)
            lock = tmp / "spec-templates.lock.json"
            lock.write_text(json.dumps({"templates": {
                "evil": {"vendored_path": "../host-secret.txt",
                         "pinned_sha256": "0" * 64}}}), encoding="utf-8")
            mod = _load_classifier()
            out = mod.check_provenance(root, lock)
            self.assertTrue(out["fault"], out)
            self.assertTrue(out.get("escaping"), out)
            self.assertIn("../host-secret.txt", json.dumps(out))
            # Nothing hashed, nothing reported: no local_hash for the entry.
            state = out["templates"]["evil"]
            self.assertNotIn("local_hash", state)

    def test_vendored_path_absolute_is_a_fault(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root = tmp / "repo"
            (root / "templates").mkdir(parents=True)
            secret = _host_secret(tmp)
            lock = tmp / "spec-templates.lock.json"
            lock.write_text(json.dumps({"templates": {
                "evil": {"vendored_path": str(secret),
                         "pinned_sha256": "0" * 64}}}), encoding="utf-8")
            mod = _load_classifier()
            out = mod.check_provenance(root, lock)
            self.assertTrue(out["fault"], out)
            self.assertIn("absolute", json.dumps(out))

    def test_contained_vendored_path_is_not_a_fault(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root = tmp / "repo"
            vend = root / "templates" / "openspec" / "t.md"
            vend.parent.mkdir(parents=True)
            vend.write_text("template\n", encoding="utf-8")
            lock = tmp / "spec-templates.lock.json"
            lock.write_text(json.dumps({"templates": {
                "ok": {"vendored_path": "templates/openspec/t.md",
                       "pinned_sha256": ""}}}), encoding="utf-8")
            mod = _load_classifier()
            out = mod.check_provenance(root, lock)
            self.assertFalse(out["fault"], out)
            self.assertEqual(out["drift"], [])


class TestFailureRegistryContainment(unittest.TestCase):
    """regression_corpus: the registry's `affected_files`."""

    def test_escaping_affected_file_reported_and_not_read(self):
        sys.path.insert(0, str(ROOT))
        from scripts.regression_corpus import stale_entries

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root = tmp / "repo"
            root.mkdir()
            _host_secret(tmp)
            entry = {"failure_id": "FAIL-X", "status": "resolved",
                     "affected_files": ["../host-secret.txt"],
                     "regression_pattern": MARKER}
            stale = stale_entries([entry], root)
            self.assertEqual(len(stale), 1, stale)
            self.assertIn("../host-secret.txt", stale[0]["escaping_paths"])
            # The pattern matches the host file's content — if the gate had
            # read it, it would now be reporting an "unresolved pattern".
            self.assertEqual(stale[0]["unresolved_pattern"], "")


class TestFindingsToSpecContainment(unittest.TestCase):
    """findings_to_spec: the capability becomes a directory it writes into."""

    def _registry(self, tmp: Path) -> Path:
        reg = tmp / ".guardrails" / "failure-registry.jsonl"
        reg.parent.mkdir(parents=True)
        reg.write_text(json.dumps({
            "failure_id": "FAIL-C1", "category": "save", "severity": "warning",
            "error_message": "a bug", "status": "active",
            "affected_files": ["src/save.rs"]}) + "\n", encoding="utf-8")
        return reg

    def test_traversal_capability_refused_and_nothing_written(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root = tmp / "repo"
            root.mkdir()
            reg = self._registry(root)
            r = subprocess.run(
                [PYTHON, str(SCRIPTS / "findings_to_spec.py"), "--root", str(root),
                 "--registry", str(reg), "--capability", "../../escaped"],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertNotEqual(r.returncode, 0, (r.returncode, r.stdout))
            self.assertIn("../../escaped", r.stderr + r.stdout)
            # root/openspec/specs/../../escaped resolves to root/escaped: a
            # gate that trusted the flag would have written outside its tree.
            self.assertFalse((root / "escaped").exists())
            self.assertFalse((root / "openspec").exists())

    def test_contained_capability_still_writes(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            root = tmp / "repo"
            root.mkdir()
            reg = self._registry(root)
            r = subprocess.run(
                [PYTHON, str(SCRIPTS / "findings_to_spec.py"), "--root", str(root),
                 "--registry", str(reg), "--capability", "save-system"],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(r.returncode, 0, (r.stdout, r.stderr))
            self.assertTrue((root / "openspec" / "specs" / "save-system" / "spec.md").exists())


if __name__ == "__main__":
    unittest.main()
