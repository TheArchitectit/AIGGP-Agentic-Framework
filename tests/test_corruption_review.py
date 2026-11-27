#!/usr/bin/env python3
# spec: fw-corruption-02
"""Focused tests for detached exact corruption-range review receipts."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_corruption.py"
PYTHON = sys.executable


def make_repo(tmp: Path, files: dict[str, bytes], repository: str = "Org/repo") -> None:
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    subprocess.run(["git", "-C", str(tmp), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(tmp), "remote", "add", "origin",
                    f"https://github.com/{repository}.git"], check=True)
    guardrails = tmp / ".guardrails"
    guardrails.mkdir()
    (guardrails / "scope.json").write_text(
        json.dumps({"api_version": "devgate.scope/v1",
                    "skip_dirs": [".git", "node_modules"]}), encoding="utf-8")
    for rel, data in files.items():
        path = tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    subprocess.run(["git", "-C", str(tmp), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp), "commit", "-qm", "x"], check=True)


class DetachedCorruptionReview(unittest.TestCase):
    """Exact range reviews are authority-digested and outside the subject."""

    old = b"alpha bravo charlie delta echo foxtrot golf\n"
    new = b"qwerty uiopas dfghjkl zxcvbnm nm,./ poiuyt\n"

    def _command(self, root: Path, *args, env: dict | None = None):
        command_env = os.environ.copy()
        command_env.pop("GITHUB_REPOSITORY", None)
        command_env.pop("GITHUB_SHA", None)
        if env is not None:
            command_env.update(env)
        return subprocess.run([PYTHON, str(SCRIPT), "--repo", str(root), *args],
                              capture_output=True, text=True, env=command_env)

    def _git(self, root: Path, *args: str) -> str:
        return subprocess.run(["git", "-C", str(root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def _repo(self, root: Path, changed: bytes | None = None,
              extra_allowlist: bool = False) -> tuple[str, str]:
        make_repo(root, {"x.md": self.old})
        base = self._git(root, "rev-parse", "HEAD")
        if changed is not None:
            (root / "x.md").write_bytes(changed)
            if extra_allowlist:
                (root / ".guardrails/corruption-allowlist.json").write_text(
                    json.dumps({"entries": [{"path": "x.md", "reason": "self-approved"}]}),
                    encoding="utf-8")
            self._git(root, "add", "-A")
            self._git(root, "commit", "-qm", "candidate")
        return base, self._git(root, "rev-parse", "HEAD^{tree}")

    def _review(self, review_path: Path, repo: str, base: str, tree: str,
                flips: list[str], inventory: dict | None = None) -> str:
        doc = {"api_version": "devgate.corruption-range-review/v1",
               "review_id": "review-001", "repository": repo,
               "base_commit": base, "target_tree": tree,
               "inventory": inventory or {
                   "flips": sorted(flips), "mass_rewrites": [],
                   "bulk_mutation": None, "strict_mass_rewrite": False,
                   "failures": sorted(flips), "warnings": []}}
        raw = (json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n").encode()
        review_path.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def test_exact_detached_review_reports_every_finding(self):
        with tempfile.TemporaryDirectory() as d:
            outer = Path(d)
            root = outer / "repo"
            root.mkdir()
            base, tree = self._repo(root, self.new)
            ordinary = self._command(root, "--range", f"{base}..HEAD",
                                     "--repository-id", "Org/repo")
            flip = next(line.strip() for line in ordinary.stdout.splitlines()
                        if "substitution flip" in line)
            review = outer / "review.json"
            digest = self._review(review, "Org/repo", base, tree, [flip])
            result = self._command(root, "--range", f"{base}..HEAD",
                                   "--repository-id", "Org/repo",
                                   "--review-file", str(review),
                                   "--review-sha256", digest)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("REVIEWED: " + flip, result.stdout)

    def test_subject_allowlist_cannot_suppress_exact_range_finding(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "repo"
            root.mkdir()
            base, _tree = self._repo(root, self.new, extra_allowlist=True)
            result = self._command(root, "--range", f"{base}..HEAD",
                                   "--repository-id", "Org/repo")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("substitution flip", result.stdout)
            legacy = self._command(root, "--range", f"{base}..HEAD")
            self.assertEqual(legacy.returncode, 0, legacy.stdout + legacy.stderr)

    def test_valid_stale_review_does_not_fail_clean_range(self):
        with tempfile.TemporaryDirectory() as d:
            outer = Path(d)
            root = outer / "repo"
            root.mkdir()
            make_repo(root, {"x.md": self.old})
            base = self._git(root, "rev-parse", "HEAD")
            (root / "clean.md").write_bytes(b"a harmless addition\n")
            self._git(root, "add", "-A")
            self._git(root, "commit", "-qm", "clean addition")
            tree = self._git(root, "rev-parse", "HEAD^{tree}")
            review = outer / "review.json"
            digest = self._review(review, "Other/repo", "0" * 40, "1" * 40, [])
            result = self._command(root, "--range", f"{base}..HEAD",
                                   "--repository-id", "Org/repo",
                                   "--review-file", str(review),
                                   "--review-sha256", digest)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("does not match repository", result.stdout)

    def test_review_file_must_be_external_and_hash_valid(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "repo"
            root.mkdir()
            base, _tree = self._repo(root, self.new)
            inside = root / "review.json"
            inside.write_text("{}", encoding="utf-8")
            result = self._command(root, "--range", f"{base}..HEAD",
                                   "--repository-id", "Org/repo",
                                   "--review-file", str(inside),
                                   "--review-sha256", "0" * 64)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("outside the scanned repository", result.stderr)

    def test_digest_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            outer = Path(d)
            root = outer / "repo"
            root.mkdir()
            base, tree = self._repo(root, self.new)
            review = outer / "review.json"
            self._review(review, "Org/repo", base, tree, [])
            result = self._command(root, "--range", f"{base}..HEAD",
                                   "--repository-id", "Org/repo",
                                   "--review-file", str(review),
                                   "--review-sha256", "0" * 64)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("does not match the authority SHA-256", result.stderr)

    def test_target_tree_change_leaves_findings_blocking(self):
        with tempfile.TemporaryDirectory() as d:
            outer = Path(d)
            root = outer / "repo"
            root.mkdir()
            base, tree = self._repo(root, self.new)
            ordinary = self._command(root, "--range", f"{base}..HEAD",
                                     "--repository-id", "Org/repo")
            flip = next(line.strip() for line in ordinary.stdout.splitlines()
                        if "substitution flip" in line)
            review = outer / "review.json"
            digest = self._review(review, "Org/repo", base, tree, [flip])
            (root / "added.md").write_bytes(b"expanded review scope\n")
            self._git(root, "add", "-A")
            self._git(root, "commit", "-qm", "change after review")
            changed = self._command(root, "--range", f"{base}..HEAD",
                                    "--repository-id", "Org/repo",
                                    "--review-file", str(review),
                                    "--review-sha256", digest)
            self.assertEqual(changed.returncode, 1, changed.stdout + changed.stderr)
            self.assertIn("does not match target tree", changed.stdout)
            self.assertIn("substitution flip", changed.stdout)

    def test_exact_mode_rejects_arbitrary_range_and_missing_digest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "repo"
            root.mkdir()
            self._repo(root, self.new)
            bad_range = self._command(root, "--range", "HEAD~1..HEAD",
                                      "--repository-id", "Org/repo")
            self.assertEqual(bad_range.returncode, 2)
            missing_digest = self._command(root, "--range", "0" * 40 + "..HEAD",
                                           "--repository-id", "Org/repo",
                                           "--review-file", "/tmp/review.json")
            self.assertEqual(missing_digest.returncode, 2)

    def test_review_cannot_be_replayed_into_another_repository(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "repo"
            root.mkdir()
            make_repo(root, {"x.md": self.old}, repository="Other/repo")
            base = self._git(root, "rev-parse", "HEAD")
            (root / "x.md").write_bytes(self.new)
            self._git(root, "add", "-A")
            self._git(root, "commit", "-qm", "flip")
            result = self._command(root, "--range", f"{base}..HEAD",
                                   "--repository-id", "Org/repo")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("does not match the scanned target", result.stderr)

    def test_github_actions_sha_must_match_resolved_head(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "repo"
            root.mkdir()
            base, _tree = self._repo(root, self.new)
            env = os.environ.copy()
            env["GITHUB_REPOSITORY"] = "Org/repo"
            env["GITHUB_SHA"] = base
            result = self._command(root, "--range", f"{base}..HEAD",
                                   "--repository-id", "Org/repo", env=env)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("does not match the GitHub Actions run SHA", result.stderr)

    def test_strict_mass_rewrite_mode_is_bound_by_inventory(self):
        with tempfile.TemporaryDirectory() as d:
            outer = Path(d)
            root = outer / "repo"
            root.mkdir()
            old = "".join(f"old line {i} distinct words item\n" for i in range(10)).encode()
            make_repo(root, {"rewrite.md": old})
            base = self._git(root, "rev-parse", "HEAD")
            (root / "rewrite.md").write_text(
                "".join(f"new line {i} changed words item\n" for i in range(10)),
                encoding="utf-8")
            self._git(root, "add", "-A")
            self._git(root, "commit", "-qm", "rewrite")
            tree = self._git(root, "rev-parse", "HEAD^{tree}")
            review = outer / "review.json"
            inventory = {"flips": [], "mass_rewrites": [
                             {"path": "rewrite.md", "added": 10, "removed": 10}],
                         "bulk_mutation": None, "strict_mass_rewrite": False,
                         "failures": [], "warnings": [
                             "rewrite.md: MASS REWRITE - 10 added / 10 removed line(s) in one change"]}
            digest = self._review(review, "Org/repo", base, tree, [], inventory)
            result = self._command(root, "--range", f"{base}..HEAD",
                                   "--repository-id", "Org/repo",
                                   "--review-file", str(review),
                                   "--review-sha256", digest,
                                   "--strict-mass-rewrite")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("inventory differed", result.stdout)

    def test_boolean_is_not_accepted_as_line_count(self):
        with tempfile.TemporaryDirectory() as d:
            outer = Path(d)
            root = outer / "repo"
            root.mkdir()
            base, tree = self._repo(root, self.new)
            review = outer / "review.json"
            self._review(review, "Org/repo", base, tree, [])
            doc = json.loads(review.read_text(encoding="utf-8"))
            doc["inventory"]["mass_rewrites"] = [
                {"path": "x.md", "added": True, "removed": 10}]
            raw = (json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n").encode()
            review.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            result = self._command(root, "--range", f"{base}..HEAD",
                                   "--repository-id", "Org/repo",
                                   "--review-file", str(review),
                                   "--review-sha256", digest)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("inventory is malformed", result.stderr)

    def test_symlink_receipt_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            outer = Path(d)
            root = outer / "repo"
            root.mkdir()
            base, _tree = self._repo(root, self.new)
            review = outer / "review.json"
            digest = self._review(review, "Org/repo", base,
                                  self._git(root, "rev-parse", "HEAD^{tree}"), [])
            link = outer / "review-link.json"
            link.symlink_to(review)
            result = self._command(root, "--range", f"{base}..HEAD",
                                   "--repository-id", "Org/repo",
                                   "--review-file", str(link),
                                   "--review-sha256", digest)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("symlinks", result.stderr)

    def test_complete_bulk_rewrite_inventory_is_reviewed(self):
        with tempfile.TemporaryDirectory() as d:
            outer = Path(d)
            root = outer / "repo"
            root.mkdir()
            old_files = {f"docs/{i:02}.md": "".join(
                f"old line {i} distinct words item {j}\n" for j in range(10)).encode()
                         for i in range(10)}
            make_repo(root, old_files)
            base = self._git(root, "rev-parse", "HEAD")
            for i in range(10):
                (root / f"docs/{i:02}.md").write_text(
                    "".join(f"new line {i} changed words item {j}\n" for j in range(10)),
                    encoding="utf-8")
            self._git(root, "add", "-A")
            self._git(root, "commit", "-qm", "bulk rewrite")
            tree = self._git(root, "rev-parse", "HEAD^{tree}")
            paths = [f"docs/{i:02}.md" for i in range(10)]
            rewrites = [{"path": path, "added": 10, "removed": 10} for path in paths]
            warnings = [f"{path}: MASS REWRITE - 10 added / 10 removed line(s) in one change"
                        for path in paths]
            failures = ["BULK MUTATION - 10 whole files rewritten in one change "
                        "(ransomware / runaway-script shape)"]
            inventory = {"flips": [], "mass_rewrites": rewrites,
                         "bulk_mutation": {"files": 10, "threshold": 10},
                         "strict_mass_rewrite": False, "failures": failures,
                         "warnings": warnings}
            review = outer / "review.json"
            digest = self._review(review, "Org/repo", base, tree, [], inventory)
            result = self._command(root, "--range", f"{base}..HEAD",
                                   "--repository-id", "Org/repo",
                                   "--review-file", str(review),
                                   "--review-sha256", digest)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for path in paths:
                self.assertIn(f"REVIEWED: {path}: MASS REWRITE", result.stdout)
            self.assertIn("REVIEWED: BULK MUTATION - 10", result.stdout)

            # A digest-valid review that omits even one rewritten path cannot
            # hide the expanded shape inventory.
            inventory["mass_rewrites"] = rewrites[:-1]
            inventory["warnings"] = warnings[:-1]
            digest = self._review(review, "Org/repo", base, tree, [], inventory)
            expanded = self._command(root, "--range", f"{base}..HEAD",
                                     "--repository-id", "Org/repo",
                                     "--review-file", str(review),
                                     "--review-sha256", digest)
            self.assertEqual(expanded.returncode, 1, expanded.stdout + expanded.stderr)
            self.assertIn("inventory differed", expanded.stdout)
            self.assertIn("BULK MUTATION - 10", expanded.stdout)
