#!/usr/bin/env python3
"""Scope-contract tests for the regression gate's per-file diff collection.

Regression tests for the 2026-09-27 audit findings:

* get_diff_content collected either the index hunk OR the worktree hunk
  (--cached vs plain diff) despite a docstring claiming the scopes were
  additive — under --all (staged=True AND unstaged=True) the per-file pattern
  scan saw only committed hunks while the registry scan saw both. One file,
  two scanners, two different verdicts in the same run.
* a git failure other than 0/1 (lock contention, corrupt index) produced ""
  for the file — the pattern check scanned nothing while the run reported
  success, contradicting _collect_git_scope's fail-loud contract
  (gate-vacuous-01).

And the 2026-10-27 fleet finding (AIGGP run 40562221604 on 88c3223):

* get_changed_files parsed only `+++ ` headers, but git emits NO ---/+++ pair
  for a pure mode change and a pure deletion's only `+++` target is
  /dev/null — so a metadata-only push read as an EMPTY scope and
  --fail-if-empty failed a real change ("NOTHING SCANNED — the selected scope
  contains 0 changed files", exit 2). The `diff --git` header names the path
  in every form and must count.

    pytest tests/test_regression_scope.py      # via run-tests.mjs

"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from regression_diff import get_changed_files, get_diff_content  # noqa: E402


def _git(repo: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


class FakeGit:
    """Records every invocation; replies from a scripted table."""

    def __init__(self, replies: dict | None = None):
        self.calls: list[list[str]] = []
        self.replies = replies or {}

    def __call__(self, args):
        self.calls.append(list(args))
        for prefix, (rc, out, err) in self.replies.items():
            if args[:len(prefix)] == list(prefix):
                return (rc, out, err)
        return (0, "", "")


class TestGetDiffContentScopes(unittest.TestCase):
    FILE = ["--", "src/app.py"]

    def test_staged_only_sees_the_index_hunk(self):
        git = FakeGit({("diff", "--cached"): (1, "-cached\n", "")})
        out = get_diff_content(git, "src/app.py", staged=True)
        self.assertIn("-cached", out)
        self.assertEqual(
            [c for c in git.calls if c[:1] == ["diff"]],
            [["diff", "--cached"] + self.FILE],
        )

    def test_staged_false_keeps_worktree_only(self):
        git = FakeGit({("diff",): (1, "-worktree\n", "")})
        out = get_diff_content(git, "src/app.py", staged=False)
        self.assertIn("-worktree", out)
        self.assertEqual(
            [c for c in git.calls if c[:1] == ["diff"]],
            [["diff"] + self.FILE],
        )

    def test_staged_and_unstaged_are_additive(self):
        """--all (staged=True AND unstaged=True) must see BOTH hunks.

        Pre-fix, staged=True forced the --cached-only command, so the
        worktree hunks were invisible to the per-file pattern scan while
        get_added_lines (which passes unstaged) saw them.
        """
        git = FakeGit({
            ("diff", "--cached"): (1, "cached_hunk\n", ""),
            ("diff",): (1, "worktree_hunk\n", ""),
        })
        out = get_diff_content(git, "src/app.py", staged=True, unstaged=True)
        self.assertIn("cached_hunk", out)
        self.assertIn("worktree_hunk", out)
        cmds = [c for c in git.calls if c[:1] == ["diff"]]
        self.assertEqual(len(cmds), 2)
        self.assertEqual(cmds[0], ["diff", "--cached"] + self.FILE)

    def test_base_range_is_still_additive(self):
        git = FakeGit({
            ("diff", "--cached"): (1, "cached_hunk\n", ""),
            ("diff", "main...HEAD"): (1, "base_hunk\n", ""),
        })
        out = get_diff_content(git, "src/app.py", staged=True, base="main")
        self.assertIn("cached_hunk", out)
        self.assertIn("base_hunk", out)


class TestGetDiffContentFailsLoud(unittest.TestCase):
    def test_unreadable_diff_raises_not_swallows(self):
        """rc 128 (lock contention, corrupt index) must not read as ''.

        The old code returned "" for the file: the pattern check scanned
        nothing while the run reported success — the localized fail-open
        the module's own _collect_git_scope already refuses.
        """
        git = FakeGit({("diff", "--cached"): (128, "", "fatal: bad object HEAD")})
        with self.assertRaises(RuntimeError) as ctx:
            get_diff_content(git, "src/app.py", staged=True)
        self.assertIn("128", str(ctx.exception))
        self.assertIn("bad object", str(ctx.exception))

    def test_base_diff_failure_also_raises(self):
        git = FakeGit({("diff", "main...HEAD"): (128, "", "fatal: no ref")})
        with self.assertRaises(RuntimeError):
            get_diff_content(git, "src/app.py", staged=True, base="main")


class TestGetChangedFilesScope(unittest.TestCase):
    """A path is in scope when the diff NAMES it — `+++` headers or not.

    The measured failure (2026-10-27, AIGGP run 40562221604 on the exec-bit fix
    88c3223): get_changed_files read only `+++ ` headers. git emits NO ---/+++
    pair for a pure mode change (old mode/new mode only), and a pure deletion's
    only `+++` target is /dev/null, which the parser skipped — so a real
    metadata-only push counted as ZERO changed files and --fail-if-empty failed
    it ("NOTHING SCANNED — the selected scope contains 0 changed files",
    exit 2). The `diff --git a/<old> b/<new>` header names the path on both
    sides in every form.
    """

    def test_mode_only_hunk_counts_as_a_changed_file(self):
        git = FakeGit({("diff", "--cached"): (1, (
            "diff --git a/scripts/tool.sh b/scripts/tool.sh\n"
            "old mode 100644\n"
            "new mode 100755\n"
        ), "")})
        self.assertEqual(get_changed_files(git, staged=True),
                         ["scripts/tool.sh"])

    def test_pure_deletion_counts_as_a_changed_file(self):
        git = FakeGit({("diff", "--cached"): (1, (
            "diff --git a/gone.txt b/gone.txt\n"
            "deleted file mode 100644\n"
            "index 1234567..0000000\n"
            "--- a/gone.txt\n"
            "+++ /dev/null\n"
            "@@ -1,1 +0,0 @@\n"
            "-bye\n"
        ), "")})
        self.assertEqual(get_changed_files(git, staged=True), ["gone.txt"])

    def test_content_change_still_reports_the_new_path(self):
        git = FakeGit({("diff", "--cached"): (1, (
            "diff --git a/src/app.py b/src/app.py\n"
            "--- a/src/app.py\n"
            "+++ b/src/app.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        ), "")})
        self.assertEqual(get_changed_files(git, staged=True), ["src/app.py"])

    def test_rename_reports_the_post_image_name(self):
        git = FakeGit({("diff", "--cached"): (1, (
            "diff --git a/old.py b/new.py\n"
            "similarity index 90%\n"
            "rename from old.py\n"
            "rename to new.py\n"
            "--- a/old.py\n"
            "+++ b/new.py\n"
            "@@ -1 +1 @@\n"
            "-x = 1\n"
            "+x = 2\n"
        ), "")})
        self.assertEqual(get_changed_files(git, staged=True), ["new.py"])

    def test_mixed_blob_reports_every_path_once(self):
        git = FakeGit({("diff", "--cached"): (1, (
            "diff --git a/scripts/tool.sh b/scripts/tool.sh\n"
            "old mode 100644\n"
            "new mode 100755\n"
            "diff --git a/src/app.py b/src/app.py\n"
            "--- a/src/app.py\n"
            "+++ b/src/app.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
            "diff --git a/src/app.py b/src/app.py\n"
            "--- a/src/app.py\n"
            "+++ b/src/app.py\n"
            "@@ -5 +5 @@\n"
            "-a\n"
            "+b\n"
        ), "")})
        self.assertEqual(get_changed_files(git, staged=True),
                         ["scripts/tool.sh", "src/app.py"])

    def test_unreadable_staged_scope_raises_not_swallows(self):
        """A staged scope that cannot be read is not an empty one.

        The collector used to do `if rc == 0: append` — a lock-contended or
        corrupt index (rc 128) dropped the blob and the scope read as ZERO
        changed files, the same vacuous-empty shape as the mode-only parse
        bug, while the docstring claimed fail-loud (gate-vacuous-01).
        """
        git = FakeGit({("diff", "--cached"): (128, "", "fatal: bad index")})
        with self.assertRaises(RuntimeError) as ctx:
            get_changed_files(git, staged=True)
        self.assertIn("128", str(ctx.exception))
        self.assertIn("bad index", str(ctx.exception))

    def test_real_git_mode_only_and_deletion_are_in_scope(self):
        """Real git, the fleet shape: an exec-bit-only stage and a pure
        deletion stage must both read as changed files."""
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "scripts").mkdir()
            tool = repo / "scripts" / "tool.sh"
            tool.write_text("#!/bin/sh\necho hi\n")
            gone = repo / "gone.txt"
            gone.write_text("bye\n")
            assert _git(repo, "init", "-q", "-b", "main")[0] == 0
            _git(repo, "config", "user.email", "t@t")
            _git(repo, "config", "user.name", "t")
            _git(repo, "add", ".")
            assert _git(repo, "commit", "-qm", "init")[0] == 0

            def run_git(args):
                return _git(repo, *args)

            # Mode-only change (the 88c3223 exec-bit shape).
            tool.chmod(0o755)
            assert _git(repo, "add", "scripts/tool.sh")[0] == 0
            self.assertEqual(get_changed_files(run_git, staged=True),
                             ["scripts/tool.sh"])

            # Pure deletion on top.
            assert _git(repo, "rm", "-q", "gone.txt")[0] == 0
            self.assertEqual(get_changed_files(run_git, staged=True),
                             ["gone.txt", "scripts/tool.sh"])


class TestRealRepoEndToEnd(unittest.TestCase):
    """Real git: a staged violation and an unstaged violation must BOTH be
    visible to the additive scope — the exact --all asymmetry the fix closes."""

    def test_both_hunks_visible_under_all_scope(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            src = repo / "src"
            src.mkdir()
            (src / "app.py").write_text("value = 1\n")
            assert _git(repo, "init", "-q", "-b", "main")[0] == 0
            _git(repo, "config", "user.email", "t@t")
            _git(repo, "config", "user.name", "t")
            _git(repo, "add", ".")
            assert _git(repo, "commit", "-qm", "init")[0] == 0

            # Staged violation and unstaged violation in the same file.
            (src / "app.py").write_text("eval(user_input)\n")
            assert _git(repo, "add", "src/app.py")[0] == 0
            (src / "app.py").write_text("eval(user_input)\n# unstaged too\n")

            def run_git(args):
                return _git(repo, *args)

            out = get_diff_content(run_git, "src/app.py",
                                   staged=True, unstaged=True)
            self.assertIn("eval(user_input)", out)
            self.assertIn("# unstaged too", out)

            # And the staged-only scope stays scoped (no worktree lines).
            out_staged = get_diff_content(run_git, "src/app.py", staged=True)
            self.assertIn("eval(user_input)", out_staged)
            self.assertNotIn("# unstaged too", out_staged)


if __name__ == "__main__":
    unittest.main()
