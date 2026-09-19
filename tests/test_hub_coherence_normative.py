# // spec: coh-pkg-03
"""Normative-boundary tests (coh-pkg-03, round-8 spec audit): the package
digests only the normative closure — informative commentary (outside the
inventory or as an informative inventory entry) never moves it, and
reclassifying an inventory entry (a kind flip) is itself a digest change.
All fixtures synthetic (R9)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import canon, package
from tests.fixtures.coherence import fixtures as fx


class TestNormativeBoundary(unittest.TestCase):
    def _package_root(self, td):
        req, _ = fx.build_root(Path(td))
        r = json.loads(req.read_text())
        return r["openspec"]["root"]

    def test_informative_only_change_leaves_normative_digest_stable(self):
        # Spec scenario: only informative text changes -> the normative
        # package digest remains stable.
        with tempfile.TemporaryDirectory() as td:
            root = self._package_root(td)
            before = package.resolve(root)["package_digest"]
            # Commentary outside the authenticated normative inventory.
            (Path(root) / "COMMENTARY.md").write_text(
                "informative note, synthetic (R9)\n")
            (Path(root) / "specs" / "NOTES.md").write_text(
                "design commentary beside the normative closure\n")
            after = package.resolve(root)["package_digest"]
            self.assertEqual(before, after)

    def test_reclassification_changes_package_digest(self):
        # Flipping an inventory entry normative -> informative is a manifest
        # change: the authenticated inventory, not the caller, classifies,
        # and reclassification changes the digest.
        with tempfile.TemporaryDirectory() as td:
            root = self._package_root(td)
            before = package.resolve(root)["package_digest"]
            mp = Path(root) / "package.json"
            manifest = json.loads(mp.read_text())
            manifest["normative_inventory"][0]["kind"] = "informative"
            mp.write_text(json.dumps(manifest))
            after = package.resolve(root)["package_digest"]
            self.assertNotEqual(before, after)

    def test_informative_entry_content_change_leaves_digest_stable(self):
        # An informative inventory entry is load-verified but excluded from
        # the canonical identity: rewriting its content (with the recorded
        # digest honestly updated) is an informative-only change, so the
        # normative package digest must not move. The kind flip happens
        # before the `before` snapshot so only the content change is measured.
        with tempfile.TemporaryDirectory() as td:
            root = self._package_root(td)
            mp = Path(root) / "package.json"
            manifest = json.loads(mp.read_text())
            entry = manifest["normative_inventory"][0]
            entry["kind"] = "informative"
            mp.write_text(json.dumps(manifest))
            before = package.resolve(root)["package_digest"]
            content = b"informative rewrite, synthetic (R9)"
            (Path(root) / entry["path"]).write_bytes(content)
            entry["digest"] = canon.digest_bytes("file/v1", content)
            mp.write_text(json.dumps(manifest))
            after = package.resolve(root)["package_digest"]
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
