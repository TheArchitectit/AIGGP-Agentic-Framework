"""Behavior tests for the actual application entry point."""

import subprocess
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app.py"


class ApplicationBehaviorTests(unittest.TestCase):
    def run_app(self, value: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(APP), value],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_valid_input_prints_result(self) -> None:
        result = self.run_app("21")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "synthetic result: 42")
        self.assertEqual(result.stderr, "")

    def test_negative_input_fails_with_diagnostic(self) -> None:
        result = self.run_app("-1")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("value must be non-negative", result.stderr)


if __name__ == "__main__":
    unittest.main()
