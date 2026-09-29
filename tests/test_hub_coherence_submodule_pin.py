# // spec: coh-id-02
"""Submodule commit-pinning in the manifest (split from
test_hub_coherence.py to stay under the 600-line test hard limit).

Relocated tests keep their identities; the parent suite's floor is
unchanged. The pin is captured from gitdir metadata; an unresolvable pin
is recorded `submodule-unresolved`, never a bare `submodule-pinned` claim.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import manifest


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
        (sub / ".git").write_text("gitdir: ../.git/modules/vendor\n", encoding="utf-8")
        gd = root / ".git" / "modules" / "vendor"
        for name, content in gitdir_body.items():
            fp = gd / name
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")
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
            (sub / ".git").write_text(f"gitdir: {gd}\n", encoding="utf-8")
            (gd / "HEAD").write_text(self.SHA_A + "\n", encoding="utf-8")
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
            (upstream / "seed.txt").write_text("seed\n", encoding="utf-8")
            for args in (["init", "-q"], ["config", "user.email", "t@t"],
                         ["config", "user.name", "t"],
                         ["add", "-A"], ["commit", "-qm", "seed"]):
                subprocess.run([git, "-C", str(upstream)] + args, check=True)
            subject = Path(td) / "subject"
            subject.mkdir()
            (subject / "seed.txt").write_text("seed\n", encoding="utf-8")
            for args in (["init", "-q"], ["config", "user.email", "t@t"],
                         ["config", "user.name", "t"],
                         ["add", "-A"], ["commit", "-qm", "seed"]):
                subprocess.run([git, "-C", str(subject)] + args, check=True)
            subprocess.run([git, "-C", str(subject), "-c",
                            "protocol.file.allow=always", "submodule", "add",
                            "-q", str(upstream), "vendor"], check=True)
            ls = subprocess.run(
                [git, "-C", str(subject), "ls-files", "-s", "vendor"],
                check=True, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
            gitlink_sha = ls.split()[1]
            self.assertEqual(self._vendor_outcome(subject),
                             f"submodule-pinned:{gitlink_sha}")

if __name__ == "__main__":
    unittest.main()
