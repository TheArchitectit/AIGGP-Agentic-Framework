"""Behavioral tests for scripts/failure_registry_check.py hygiene gate.

Focus (audit finding): an EXPLICIT registry path that does not exist used to
be silently skipped for the non-"devgate" label — a typo'd
FAILURE_REGISTRY_PATH yielded zero entries, zero errors, exit 0, a vacuous
green from the hygiene gate itself. Also locks the merge semantics the
overlay contract promises.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "failure_registry_check.py"
PYTHON = sys.executable

GOOD_ENTRY = {
    "failure_id": "FAIL-abc12345",
    "timestamp": "2026-09-19T00:00:00Z",
    "category": "runtime", "severity": "high",
    "error_message": "x", "root_cause": "y",
    "affected_files": [], "fix_commit": "pending",
    "regression_pattern": "", "prevention_rule": "z",
    "status": "resolved",
}


def run_check(*args):
    import os
    env = dict(os.environ)
    env.pop("FAILURE_REGISTRY_PATH", None)
    return subprocess.run([PYTHON, str(SCRIPT), *args],
                          capture_output=True, text=True, env=env)


class TestExplicitPathHonesty(unittest.TestCase):
    def test_missing_explicit_path_fails_not_vacuous_green(self):
        missing = Path(tempfile.mkdtemp()) / "no-such-registry.jsonl"
        r = run_check()
        # via env override, the documented single-file mode
        import os
        env = dict(os.environ)
        env["FAILURE_REGISTRY_PATH"] = str(missing)
        r = subprocess.run([PYTHON, str(SCRIPT)], capture_output=True,
                           text=True, env=env)
        self.assertEqual(r.returncode, 1,
                         "a named registry that does not exist must fail")
        self.assertIn("registry not found", r.stderr)

    def test_existing_explicit_path_clean(self):
        tmp = Path(tempfile.mkdtemp(prefix="dg-frc-"))
        reg = tmp / "reg.jsonl"
        reg.write_text(json.dumps(GOOD_ENTRY) + "\n")
        import os
        env = dict(os.environ)
        env["FAILURE_REGISTRY_PATH"] = str(reg)
        env["DEVGATE_PROJECT_ROOT"] = str(tmp)
        r = subprocess.run([PYTHON, str(SCRIPT)], capture_output=True,
                           text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class TestRegistryHygiene(unittest.TestCase):
    def _check_module(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from scripts import failure_registry_check as frc  # guardrails-allow PREVENT-024: local scripts/ module, not a registry package
        return frc

    def test_missing_required_field_is_error(self):
        frc = self._check_module()
        tmp = Path(tempfile.mkdtemp(prefix="dg-frc-"))
        reg = tmp / "reg.jsonl"
        bad = dict(GOOD_ENTRY)
        del bad["root_cause"]
        reg.write_text(json.dumps(bad) + "\n")
        code, findings = frc.check(reg)
        self.assertEqual(code, 1)
        self.assertTrue(any("missing field" in f for f in findings))

    def test_duplicate_id_within_one_file_is_error(self):
        frc = self._check_module()
        tmp = Path(tempfile.mkdtemp(prefix="dg-frc-"))
        reg = tmp / "reg.jsonl"
        reg.write_text(json.dumps(GOOD_ENTRY) + "\n" +
                       json.dumps(GOOD_ENTRY) + "\n")
        code, findings = frc.check(reg)
        self.assertEqual(code, 1)
        self.assertTrue(any("duplicate failure_id" in f for f in findings))

    def test_comment_lines_skipped(self):
        frc = self._check_module()
        tmp = Path(tempfile.mkdtemp(prefix="dg-frc-"))
        reg = tmp / "reg.jsonl"
        reg.write_text("# header comment\n" + json.dumps(GOOD_ENTRY) + "\n")
        code, findings = frc.check(reg)
        self.assertEqual(code, 0, findings)


if __name__ == "__main__":
    unittest.main()
