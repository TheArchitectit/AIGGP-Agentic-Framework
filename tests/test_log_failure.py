"""Behavioral tests for scripts/log_failure.py registry targeting (H8).

The default target used to be the bundled baseline registry INSIDE the
DevGate submodule — the documented mechanism by which the shared registry
accumulated entries referencing other repos' files. Now: project overlay by
default, --baseline for maintainers, --registry / FAILURE_REGISTRY_PATH
override, and the append-only contract (never rewrites existing lines).
"""
import importlib.util
import json
import shutil
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
        # Standalone (clone) layout: DevGate IS the project, so the default
        # target resolves to the repo's own .guardrails/failure-registry.jsonl.
        # The layout must be BUILT, not assumed: when this checkout is vendored
        # as <host>/.devgate the module correctly resolves the parent as the
        # project — asserting standalone against the live tree fails in exactly
        # the layout every consumer uses. Copy the script into a tree NOT named
        # .devgate and import that copy. (Verified by resolution, not by
        # writing into any registry.)
        standalone = Path(tempfile.mkdtemp(prefix="dg-logf-standalone-"))
        self.addCleanup(shutil.rmtree, standalone, ignore_errors=True)
        scripts = standalone / "scripts"
        scripts.mkdir()
        shutil.copy2(SCRIPT, scripts / "log_failure.py")
        spec = importlib.util.spec_from_file_location(
            "log_failure_standalone", scripts / "log_failure.py")
        lf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lf)
        self.assertEqual(lf.DEVGATE_ROOT, standalone)
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


class TestBaseWrite01Contract(unittest.TestCase):
    """base-write-01: in a submodule layout the default target is the PROJECT's
    overlay, the shared baseline needs the explicit `--upstream` flag, and the
    output names the file that received the entry.

    The script is staged inside a directory literally named `.devgate`, because
    that name is what selects the consumer layout in the script itself - the
    same deployment-shape reasoning as the containment fixture suite.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dg-logf-own-"))
        staged = self.tmp / ".devgate" / "scripts"
        staged.mkdir(parents=True)
        self.script = staged / "log_failure.py"
        self.script.write_bytes(SCRIPT.read_bytes())
        self.overlay = self.tmp / ".guardrails" / "failure-registry.jsonl"
        self.baseline = self.tmp / ".devgate" / ".guardrails" / "failure-registry.jsonl"

    def _run(self, *args):
        import os
        env = dict(os.environ)
        env.pop("FAILURE_REGISTRY_PATH", None)
        return subprocess.run([PYTHON, str(self.script), *args],
                              capture_output=True, text=True, env=env)

    def test_default_writes_the_project_overlay_and_names_it(self):
        r = self._run("--error-message", "boom")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.overlay.exists(), r.stdout + r.stderr)
        self.assertIn(f"registry: {self.overlay}", r.stdout)
        self.assertEqual(self.overlay.read_text().count("\n"), 1)
        self.assertFalse(self.baseline.exists(),
                         "a consumer's bug must not land in the shared baseline")

    def test_upstream_writes_the_shared_baseline_and_names_it(self):
        r = self._run("--error-message", "boom", "--upstream")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.baseline.exists(), r.stdout + r.stderr)
        self.assertIn(f"registry: {self.baseline}", r.stdout)
        self.assertFalse(self.overlay.exists(),
                         "an explicit upstream append must not also write the overlay")

    def test_baseline_is_still_accepted_as_an_alias(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from scripts import log_failure as lf
        parser = lf.build_parser()
        self.assertTrue(parser.parse_args(["--error-message", "x", "--upstream"]).baseline)
        self.assertTrue(parser.parse_args(["--error-message", "x", "--baseline"]).baseline)
        self.assertFalse(parser.parse_args(["--error-message", "x"]).baseline)


if __name__ == "__main__":
    unittest.main()
