# spec: fw-ci-06
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


if __name__ == "__main__":
    unittest.main()
