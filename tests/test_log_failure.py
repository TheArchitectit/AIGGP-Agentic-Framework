"""Behavioral tests for scripts/log_failure.py registry targeting (H8).

The default target used to be the bundled baseline registry INSIDE the
DevGate submodule — the documented mechanism by which the shared registry
accumulated entries referencing other repos' files. Now: project overlay by
default, --baseline for maintainers, --registry / FAILURE_REGISTRY_PATH
override, and the append-only contract (never rewrites existing lines).
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "log_failure.py"
PYTHON = sys.executable


def run_log(*args, env_extra=None):
    import os
    env = dict(os.environ)
    env.pop("FAILURE_REGISTRY_PATH", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run([PYTHON, str(SCRIPT), *args],
                          capture_output=True, text=True, env=env)


class TestLogFailureTargeting(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dg-logf-"))

    def test_explicit_registry_flag_writes_there(self):
        target = self.tmp / "custom.jsonl"
        r = run_log("--error-message", "boom", "--registry", str(target))
        self.assertEqual(r.returncode, 0, r.stderr)
        entry = json.loads(target.read_text().strip())
        self.assertEqual(entry["error_message"], "boom")

    def test_env_override_wins(self):
        target = self.tmp / "env.jsonl"
        r = run_log("--error-message", "from env",
                    env_extra={"FAILURE_REGISTRY_PATH": str(target)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(target.exists())

    def test_standalone_default_is_the_repo_registry(self):
        # Standalone layout: DevGate IS the project, so the default target
        # resolves to this repo's own .guardrails/failure-registry.jsonl —
        # the same file the old default used. (Verified by resolution, not by
        # writing into the real registry.)
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from scripts import log_failure as lf
        self.assertEqual(lf.PROJECT_ROOT, lf.DEVGATE_ROOT)
        self.assertEqual(lf.DEFAULT_REGISTRY,
                         lf.DEVGATE_ROOT / ".guardrails" / "failure-registry.jsonl")
        self.assertEqual(lf.BASELINE_REGISTRY, lf.DEFAULT_REGISTRY)

    def test_append_only_never_rewrites(self):
        target = self.tmp / "reg.jsonl"
        target.write_text('{"failure_id": "FAIL-old"}\n')
        run_log("--error-message", "second", "--registry", str(target))
        lines = target.read_text().strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["failure_id"], "FAIL-old")

    def test_missing_newline_is_repaired(self):
        target = self.tmp / "reg.jsonl"
        target.write_text('{"failure_id": "FAIL-a"}')  # no trailing newline
        run_log("--error-message", "b", "--registry", str(target))
        lines = target.read_text().strip().splitlines()
        self.assertEqual(len(lines), 2, "appended entry must not merge lines")
        for ln in lines:
            json.loads(ln)  # both lines parse


if __name__ == "__main__":
    unittest.main()
