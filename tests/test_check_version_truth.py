# // spec: doc-version-01
"""Behavioral tests for scripts/check_version_truth.py (doc-version-01).

Each test builds a real miniature git repo (VERSION + CHANGELOG.md + tags)
and asserts the gate names the exact disagreement — the audit's defect was
three version artifacts that contradicted each other while every existing
check stayed green, so every mismatch shape here must FAIL.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check_version_truth.py"
PYTHON = sys.executable

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "version-truth-test",
    "GIT_AUTHOR_EMAIL": "version-truth-test@example.invalid",
    "GIT_COMMITTER_NAME": "version-truth-test",
    "GIT_COMMITTER_EMAIL": "version-truth-test@example.invalid",
}


def run_gate(repo: Path):
    return subprocess.run([PYTHON, str(SCRIPT), "--repo", str(repo)],
                          capture_output=True, text=True)


def make_repo(root: Path, version: str | None, changelog: str,
              tags: list) -> Path:
    repo = root / "repo"
    repo.mkdir()
    if version is not None:
        (repo / "VERSION").write_text(version + "\n", encoding="utf-8")
    (repo / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True,
                   env=GIT_ENV)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True,
                   env=GIT_ENV)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"],
                   check=True, env=GIT_ENV)
    for tag in tags:
        subprocess.run(["git", "-C", str(repo), "tag", tag], check=True,
                       env=GIT_ENV)
    return repo


CHANGELOG_OK = (
    "# Changelog\n\n## [Unreleased]\n\nnothing yet\n\n"
    "## [1.2.3] - 2026-01-02\n\n### Added\n\n- thing\n"
)


class TestVersionTruthGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dg-vtruth-"))
        self.addCleanup(__import__("shutil").rmtree, self.tmp,
                        ignore_errors=True)

    def test_agreeing_repo_passes(self):
        repo = make_repo(self.tmp, "1.2.3", CHANGELOG_OK, ["v1.2.3"])
        r = run_gate(repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("OK", r.stdout)

    def test_version_disagreeing_with_newest_tag_fails_naming_both(self):
        repo = make_repo(self.tmp, "9.9.9", CHANGELOG_OK, ["v1.2.3"])
        r = run_gate(repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("9.9.9", r.stderr)
        self.assertIn("v1.2.3", r.stderr)

    def test_untagged_release_claim_in_changelog_fails(self):
        changelog = CHANGELOG_OK + "\n## [2.0.0] - 2026-02-02\n\n### Added\n\n- x\n"
        repo = make_repo(self.tmp, "1.2.3", changelog, ["v1.2.3"])
        r = run_gate(repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("## [2.0.0]", r.stderr)
        self.assertIn("no git tag v2.0.0", r.stderr)

    def test_tag_with_no_changelog_section_fails(self):
        repo = make_repo(self.tmp, "1.2.3", CHANGELOG_OK,
                         ["v1.2.3", "v0.9.0"])
        r = run_gate(repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("v0.9.0", r.stderr)

    def test_missing_version_file_fails(self):
        repo = make_repo(self.tmp, None, CHANGELOG_OK, ["v1.2.3"])
        r = run_gate(repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("VERSION is missing", r.stderr)

    def test_invisible_tag_set_fails_closed(self):
        repo = make_repo(self.tmp, "1.2.3", CHANGELOG_OK, [])
        r = run_gate(repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no v* semver tags", r.stderr)

    def test_this_repository_agrees(self):
        r = run_gate(REPO)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
