# // spec: coh-sec-01
"""Path-containment tests for repository-supplied content (audit findings
F3/F4): package inventory paths and assertion file selectors are untrusted —
they must be contained under their declared roots before any read, and a
hostile path must never leak host-file content, existence, or length.

Behavioral: every test drives the real resolver/evaluator with real files on
disk in a temp tree, and asserts on rejection semantics (PackageError /
Unresolved with stable reasons) and on the absence of host content.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import canon, evaluators, package  # noqa: E402


def _world(tmp: Path) -> tuple:
    """A minimal valid package world plus a HOST SECRET outside the roots."""
    root = Path(tmp)
    pkg = root / "pkg"
    (pkg / "specs").mkdir(parents=True)
    (root / "secret.txt").write_text("# product: LEAKED-HOST-SECRET\n")
    (pkg / "specs" / "a.json").write_text('{"id": "a"}')
    return root, pkg


def _manifest(pkg: Path, inventory: list) -> None:
    (pkg / "package.json").write_text(json.dumps({
        "schema_version": "devgate.openspec.package/v1",
        "package_id": "com.test.pkg", "package_version": "1",
        "normative_inventory": inventory, "imports": [],
    }))


class TestInventoryContainment(unittest.TestCase):
    def test_relative_traversal_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as td:
            root, pkg = _world(Path(td))
            _manifest(pkg, [{"path": "../secret.txt", "kind": "normative",
                             "digest": "sha256:" + "0" * 64}])
            with self.assertRaises(package.PackageError) as ctx:
                package.resolve(str(pkg))
            self.assertIn("traversal", str(ctx.exception))

    def test_absolute_path_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root, pkg = _world(Path(td))
            secret = str(root / "secret.txt")
            _manifest(pkg, [{"path": secret, "kind": "normative",
                             "digest": "sha256:" + "0" * 64}])
            with self.assertRaises(package.PackageError) as ctx:
                package.resolve(str(pkg))
            self.assertIn("relative", str(ctx.exception))

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root, pkg = _world(Path(td))
            (pkg / "link.txt").symlink_to(root / "secret.txt")
            _manifest(pkg, [{"path": "link.txt", "kind": "normative",
                             "digest": canon.digest_bytes(
                                 "file/v1", (root / "secret.txt").read_bytes())}])
            with self.assertRaises(package.PackageError) as ctx:
                package.resolve(str(pkg))
            self.assertIn("escapes", str(ctx.exception))

    def test_rejection_message_never_contains_host_content(self):
        with tempfile.TemporaryDirectory() as td:
            root, pkg = _world(Path(td))
            _manifest(pkg, [{"path": "../../secret.txt", "kind": "normative",
                             "digest": "sha256:" + "0" * 64}])
            try:
                package.resolve(str(pkg))
                self.fail("hostile path must be rejected")
            except package.PackageError as e:
                self.assertNotIn("LEAKED-HOST-SECRET", str(e))

    def test_wellformed_package_still_resolves(self):
        with tempfile.TemporaryDirectory() as td:
            root, pkg = _world(Path(td))
            inv = [{"path": "specs/a.json", "kind": "normative",
                    "digest": canon.digest_bytes(
                        "file/v1", (pkg / "specs/a.json").read_bytes())}]
            _manifest(pkg, inv)
            resolved = package.resolve(str(pkg))
            self.assertEqual(resolved["package_id"], "com.test.pkg")


class TestSelectorContainment(unittest.TestCase):
    def _assertion(self, path: str) -> dict:
        return {
            "id": "identity", "version": 1,
            "requirement_refs": ["r-01"], "owner": "o", "requirement": "r",
            "subjects": [{"kind": "file", "path": path}],
            "evaluator": {"id": "devgate.builtin.identity-consistency",
                          "digest": "sha256:" + "a" * 64},
            "parameters": {"approved_value_ref": "package:product.identity.name"},
            "severity": "high", "dependencies": [], "evidence": {},
        }

    def test_selector_traversal_is_unresolved_not_read(self):
        with tempfile.TemporaryDirectory() as td:
            root, pkg = _world(Path(td))
            subj = root / "subject"
            subj.mkdir()
            pkg_doc = {"product": {"identity": {"name": "widget"}}}
            with self.assertRaises(evaluators.Unresolved) as ctx:
                evaluators.identity_consistency(
                    self._assertion("../secret.txt"), pkg_doc, str(subj))
            self.assertIn("selector-escapes-subject", str(ctx.exception))

    def test_absolute_selector_is_unresolved(self):
        with tempfile.TemporaryDirectory() as td:
            root, pkg = _world(Path(td))
            subj = root / "subject"
            subj.mkdir()
            with self.assertRaises(evaluators.Unresolved):
                evaluators.identity_consistency(
                    self._assertion(str(root / "secret.txt")),
                    {"product": {"identity": {"name": "widget"}}}, str(subj))

    def test_symlink_selector_escape_is_unresolved(self):
        with tempfile.TemporaryDirectory() as td:
            root, pkg = _world(Path(td))
            subj = root / "subject"
            subj.mkdir()
            (subj / "link.md").symlink_to(root / "secret.txt")
            with self.assertRaises(evaluators.Unresolved) as ctx:
                evaluators.identity_consistency(
                    self._assertion("link.md"),
                    {"product": {"identity": {"name": "widget"}}}, str(subj))
            self.assertIn("selector-escapes-subject", str(ctx.exception))

    def test_legit_selector_still_evaluates(self):
        with tempfile.TemporaryDirectory() as td:
            root, pkg = _world(Path(td))
            subj = root / "subject"
            subj.mkdir()
            (subj / "README.md").write_text("# product: widget\n")
            findings = evaluators.identity_consistency(
                self._assertion("README.md"),
                {"product": {"identity": {"name": "widget"}}}, str(subj))
            self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
