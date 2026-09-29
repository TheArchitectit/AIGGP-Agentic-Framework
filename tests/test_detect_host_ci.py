"""Behavioral tests for scripts/detect-host-ci.py (host CI resolver).

Locks the 2026-09-19 hardening: word-boundary redaction (the old bare
`ak|sk` alternation redacted 40 chars out of ordinary labels like
`blacksmith-2x`), `*.yaml` workflow discovery, unreadable/binary asset
robustness, and `FROM --platform=... <image>` parsing.
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "detect-host-ci.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("detect_host_ci", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestRedaction(unittest.TestCase):
    def setUp(self):
        self.mod = _load_module()

    def test_ordinary_labels_survive(self):
        for label in ("blacksmith-2x", "make-runner", "devgate-runner",
                      "ubuntu-latest", "self-hosted"):
            self.assertEqual(self.mod.redact(label), label,
                             f"{label} must not be redacted")

    def test_secret_shaped_values_redacted(self):
        for text in ("RUNNER_TOKEN=abc123",
                     "api_key: sk-live-999",
                     "password=hunter2",
                     "ghp_abcdefghij1234567890"):
            out = self.mod.redact(text)
            self.assertIn("<redacted>", out, f"{text} must be redacted")

    def test_ip_and_auth_url_redacted(self):
        self.assertIn("<redacted>", self.mod.redact("host 10.0.0.12"))
        self.assertIn("<redacted>", self.mod.redact("https://user:pw@example.com/x"))


class TestWorkflowCollection(unittest.TestCase):
    def setUp(self):
        self.mod = _load_module()
        self.tmp = Path(tempfile.mkdtemp(prefix="dg-host-"))
        (self.tmp / ".github" / "workflows").mkdir(parents=True)

    def test_yaml_extension_discovered(self):
        (self.tmp / ".github/workflows/ci.yaml").write_text(
            "jobs:\n  a:\n    runs-on: devgate\n")
        info = self.mod.collect_workflow_info(self.tmp)
        self.assertIn("devgate", info["runs_on"])

    def test_cron_requires_schedule_block(self):
        (self.tmp / ".github/workflows/x.yml").write_text(
            "on:\n  schedule:\n    - cron: '19 5 * * *'\n"
            "  workflow_dispatch:\n    - cron: 'not-a-schedule'\n")
        info = self.mod.collect_workflow_info(self.tmp)
        self.assertEqual(info["crons"], ["19 5 * * *"])


class TestRunnerAssets(unittest.TestCase):
    def setUp(self):
        self.mod = _load_module()
        self.tmp = Path(tempfile.mkdtemp(prefix="dg-host-"))
        (self.tmp / ".github").mkdir()

    def test_from_with_platform_flag(self):
        (self.tmp / "Containerfile").write_text(
            "FROM --platform=linux/amd64 docker.io/library/python:3.12\n"
            "RUNNER_LABELS=devgate,linux\n")
        assets = self.mod.collect_runner_assets(self.tmp)
        self.assertIn("docker.io/library/python:3.12", assets["images"])
        self.assertIn("devgate,linux", assets["labels"])

    def test_binary_asset_skipped_not_fatal(self):
        (self.tmp / "weird.image").write_bytes(b"\x00\x01\x02binary")
        assets = self.mod.collect_runner_assets(self.tmp)  # must not raise
        self.assertEqual(assets["images"], [])


class TestCLIStandalone(unittest.TestCase):
    def test_standalone_reports_no_host(self):
        r = subprocess.run([sys.executable, str(SCRIPT)],
                           capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["devgate_layout"], "standalone")

    def test_fail_on_missing_standalone_exits_1(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--fail-on-missing"],
                           capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
