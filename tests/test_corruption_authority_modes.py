"""Behavioral checks for the independent corruption-review authority modes."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import check_corruption as gate
from corruption_diff import ReviewModeError, validate_review_mode
import corruption_git


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


class ReviewModeArguments(unittest.TestCase):
    def test_conflicting_arguments_are_rejected_before_scope_or_authority_io(self):
        full = "a" * 40
        cases = (
            ["--reviewed-transitions", "--range", f"{full}..{full}",
             "--repository-id", "Org/repo"],
            ["--repository-id", "Org/repo", "--range", f"{full}..HEAD",
             "--review-file", "/tmp/review.json"],
            ["--reviewed-transitions"],
            ["--repository-id", "Org/repo", "--range", f"{full}..HEAD",
             "--staged"],
            ["--repository-id", "Org/repo", "--range", f"{full}..HEAD",
             "--no-baseline"],
        )
        with patch.object(gate, "_load_gate_common") as load_common:
            for args in cases:
                with self.subTest(args=args), patch.object(
                        sys, "argv", ["check_corruption", *args]):
                    with self.assertRaises(SystemExit) as raised:
                        gate.main()
                    self.assertEqual(raised.exception.code, gate.EXIT_USAGE)
            load_common.assert_not_called()

    def test_conflicting_review_flags_do_not_select_either_mode(self):
        class Args:
            reviewed_transitions = True
            repository_id = "Org/repo"
            review_file = None
            review_sha256 = None
            range = "a" * 40 + ".." + "b" * 40
            staged = False
            write_baseline = False
            no_baseline = False

        with self.assertRaises(ReviewModeError):
            validate_review_mode(Args())

    def test_ordinary_scanner_import_does_not_load_authority_modules(self):
        code = (
            f"import sys; sys.path.insert(0, {str(SCRIPTS)!r}); "
            "import check_corruption; "
            "assert 'corruption_review' not in sys.modules; "
            "assert 'corruption_reviews' not in sys.modules; "
            "assert 'corruption_git' not in sys.modules"
        )
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class InvalidProtectedInput(unittest.TestCase):
    def test_malformed_binding_reports_unusable_authority(self):
        from tests.test_corruption_reviews import CommitReviews  # guardrails-allow PREVENT-024: bundled synthetic controller fixture
        fixture = CommitReviews()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        fixture.documents[fixture.binding_path] = b"invalid json"
        code, output = fixture.scan()
        self.assertEqual(code, gate.EXIT_USAGE)
        self.assertIn("FAIL - protected review", output)
        self.assertNotIn("advisory", output.lower())


class IsolatedCommittedDiff(unittest.TestCase):
    def test_diff_uses_pinned_commits_fixed_config_and_tmp_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "subject"
            root.mkdir()
            git(root, "init", "-q")
            git(root, "config", "user.email", "fixture@example.invalid")
            git(root, "config", "user.name", "Fixture")
            path = root / "story.txt"
            path.write_text("alpha bravo charlie delta echo foxtrot\n", encoding="utf-8")
            git(root, "add", "story.txt")
            git(root, "commit", "-qm", "base")
            base = git(root, "rev-parse", "HEAD")
            path.write_text("qwerty uiopas dfghjkl zxcvbnm poiuyt\n", encoding="utf-8")
            git(root, "commit", "-qam", "candidate")
            head = git(root, "rev-parse", "HEAD")
            git(root, "config", "diff.algorithm", "patience")
            git(root, "config", "diff.noprefix", "true")
            private_tmp = root / "subject-tmp"
            private_tmp.mkdir()

            with patch.dict(os.environ, {"TMPDIR": str(private_tmp)}):
                with patch.object(tempfile, "tempdir", None):
                    with corruption_git.committed_range_view(root, base, head) as view:
                        before = view.diff()
                        self.assertEqual(view.git_dir.parent, Path("/tmp"))
                        self.assertIn("diff --git a/story.txt b/story.txt", before)
                        self.assertIn("@@ -1 +1 @@", before)
                        path.write_text("a later edit to the working checkout\n", encoding="utf-8")
                        git(root, "add", "story.txt")
                        git(root, "commit", "-qm", "move HEAD after snapshot")
                        self.assertEqual(view.diff(), before)
            self.assertEqual(list(private_tmp.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
