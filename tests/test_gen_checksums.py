# spec: fw-ci-06, fw-ci-07
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gen-checksums.py"


class ChecksumManifestRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "one.py").write_text("print('one')\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "scripts/one.py"], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def verify(self, body: str):
        (self.root / "CHECKSUMS.sha256").write_text(body, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(SCRIPT), "verify", "--repo", str(self.root)],
            text=True, capture_output=True, check=False,
        )

    def test_rejects_malformed_digest(self):
        result = self.verify("bad  scripts/one.py\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("malformed manifest line", result.stderr)

    def test_rejects_duplicate_path(self):
        digest = hashlib.sha256(b"print('one')\n").hexdigest()
        result = self.verify(f"{digest}  scripts/one.py\n{digest}  scripts/one.py\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate manifest path: scripts/one.py", result.stderr)

    def test_malformed_duplicate_cannot_be_overwritten(self):
        digest = hashlib.sha256(b"print('one')\n").hexdigest()
        result = self.verify(f"bad  scripts/one.py\n{digest}  scripts/one.py\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("malformed manifest line", result.stderr)


class ChecksumTrackedPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "scripts").mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "core.quotePath", "true"], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def run_mode(self, mode: str):
        return subprocess.run(
            [sys.executable, str(SCRIPT), mode, "--repo", str(self.root)],
            text=True, capture_output=True, check=False,
        )

    def add(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("print('tracked')\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "--", str(path.relative_to(self.root))], check=True)

    def test_unicode_and_internal_spaces_are_included_with_quote_path(self):
        unicode_name = "r\u00e9sum\u00e9.py"
        self.add(self.root / "scripts" / "ordinary.py")
        self.add(self.root / "scripts" / unicode_name)
        self.add(self.root / "scripts" / "internal space.py")
        self.add(self.root / "scripts" / "folder with space" / "nested.py")
        if os.name != "nt":
            self.add(self.root / "scripts" / "ignored\nname.txt")

        generated = self.run_mode("generate")
        self.assertEqual(generated.returncode, 0, generated.stderr)
        manifest = (self.root / "CHECKSUMS.sha256").read_text(encoding="utf-8")
        self.assertIn("  scripts/ordinary.py\n", manifest)
        self.assertIn("  scripts/" + unicode_name + "\n", manifest)
        self.assertIn("  scripts/internal space.py\n", manifest)
        self.assertIn("  scripts/folder with space/nested.py\n", manifest)
        self.assertNotIn("ignored", manifest)
        verified = self.run_mode("verify")
        self.assertEqual(verified.returncode, 0, verified.stderr)

    @unittest.skipIf(os.name == "nt", "POSIX permits line separators in filenames")
    def test_unrepresentable_supported_paths_fail_before_manifest_write(self):
        cases = [
            ("scripts/line\nbreak.py", "cannot be represented"),
            ("scripts/carriage\rreturn.py", "cannot be represented"),
            ("scripts/back\\slash.py", "cannot be represented"),
            ("scripts/unicode\u2028separator.py", "cannot be represented"),
        ]
        for name, diagnostic in cases:
            with self.subTest(path=repr(name)), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "scripts").mkdir()
                subprocess.run(["git", "init", "-q", str(root)], check=True)
                subprocess.run(["git", "-C", str(root), "config", "core.quotePath", "true"], check=True)
                (root / "scripts" / "ok.py").write_text("print('ok')\n", encoding="utf-8")
                bad = root / name
                bad.parent.mkdir(parents=True, exist_ok=True)
                bad.write_text("print('bad')\n", encoding="utf-8")
                subprocess.run(["git", "-C", str(root), "add", "--", "scripts"], check=True)
                sentinel = "existing manifest\n"
                (root / "CHECKSUMS.sha256").write_text(sentinel, encoding="utf-8")
                for mode in ("generate", "verify"):
                    result = subprocess.run(
                        [sys.executable, str(SCRIPT), mode, "--repo", str(root)],
                        text=True, capture_output=True, check=False,
                    )
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn(diagnostic, result.stderr)
                    self.assertNotIn("VERIFY OK", result.stdout)
                self.assertEqual((root / "CHECKSUMS.sha256").read_text(encoding="utf-8"), sentinel)

        with self.subTest(path="invalid UTF-8"), tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "scripts").mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            raw_rel = b"scripts/bad-\xff.py"
            raw_path = os.fsencode(root) + b"/" + raw_rel
            fd = os.open(raw_path, os.O_CREAT | os.O_WRONLY, 0o600)
            os.write(fd, b"print('bad')\n")
            os.close(fd)
            subprocess.run([b"git", b"-C", os.fsencode(root), b"add", b"--", raw_rel], check=True)
            sentinel = "existing manifest\n"
            (root / "CHECKSUMS.sha256").write_text(sentinel, encoding="utf-8")
            for mode in ("generate", "verify"):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), mode, "--repo", str(root)],
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("not UTF-8", result.stderr)
                self.assertNotIn("VERIFY OK", result.stdout)
            self.assertEqual((root / "CHECKSUMS.sha256").read_text(encoding="utf-8"), sentinel)

    def test_unmerged_index_duplicate_fails_before_manifest_io(self):
        git = ["git", "-C", str(self.root)]
        subprocess.run(git + ["config", "user.name", "Test"], check=True)
        subprocess.run(git + ["config", "user.email", "test@example.invalid"], check=True)
        conflict = self.root / "scripts" / "conflict.py"
        conflict.write_text("print('base')\n", encoding="utf-8")
        subprocess.run(git + ["add", "scripts/conflict.py"], check=True)
        subprocess.run(git + ["commit", "-qm", "base"], check=True)
        subprocess.run(git + ["branch", "-M", "main"], check=True)
        subprocess.run(git + ["checkout", "-qb", "side"], check=True)
        conflict.write_text("print('side')\n", encoding="utf-8")
        subprocess.run(git + ["commit", "-qam", "side"], check=True)
        subprocess.run(git + ["checkout", "-q", "main"], check=True)
        conflict.write_text("print('main')\n", encoding="utf-8")
        subprocess.run(git + ["commit", "-qam", "main"], check=True)
        merge = subprocess.run(git + ["merge", "side"], capture_output=True, text=True, check=False)
        self.assertEqual(merge.returncode, 1, merge.stdout + merge.stderr)
        stages = subprocess.run(git + ["ls-files", "-s", "--", "scripts/conflict.py"],
                                capture_output=True, text=True, check=True).stdout.splitlines()
        self.assertEqual(len(stages), 3, stages)
        sentinel = "existing manifest\n"
        (self.root / "CHECKSUMS.sha256").write_text(sentinel, encoding="utf-8")

        for mode in ("generate", "verify"):
            result = self.run_mode(mode)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("duplicate supported path in Git index (unmerged index)", result.stderr)
            self.assertNotIn("VERIFY OK", result.stdout)
        self.assertEqual((self.root / "CHECKSUMS.sha256").read_text(encoding="utf-8"), sentinel)


if __name__ == "__main__":
    unittest.main()
