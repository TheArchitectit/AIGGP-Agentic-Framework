"""Behavioral tests for scripts/regression_audit.py.

QA C6: npm's `effects` lists a vulnerability's dependents and is [] for a
direct dependency, so the old classification (`any(eff in runtime_deps for
eff in effects)`) downgraded a HIGH vuln in a direct runtime dependency to
dev-only — never blocking. Verified live against lodash@4.17.15
(isDirect=true, effects=[]). These tests drive check_npm_audit's own API
with fixture audit documents (no npm, no network).
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import regression_audit as ra  # noqa: E402


def make_npm_project(files: dict) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="dg-audit-"))
    (tmp / "package.json").write_text(json.dumps(files["package.json"]))
    for rel, content in files.get("extra", {}).items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return tmp


class TestDirectRuntimeVulnClassifiesRuntime(unittest.TestCase):
    def test_direct_high_runtime_vuln_is_blocking(self):
        # The exact QA C6 shape: direct dependency, effects empty.
        proj = make_npm_project({
            "package.json": {"dependencies": {"lodash": "^4.17.15"}},
        })
        audit = {"vulnerabilities": {
            "lodash": {"severity": "high", "isDirect": True,
                       "effects": [], "fixAvailable": True,
                       "via": ["GHSA-35jh-r3h4-6jhm"]},
        }}
        with mock.patch.object(ra.subprocess, "run") as run:
            run.return_value = unittest.mock.Mock(
                stdout=json.dumps(audit), returncode=0)
            blocking, warnings, issues = ra.check_npm_audit(proj)
        self.assertEqual(blocking, 1,
                         "direct HIGH runtime vuln must block (QA C6)")
        self.assertEqual(warnings, 0)
        self.assertTrue(issues[0]["is_runtime"])

    def test_transitive_vuln_reaching_runtime_dep_is_runtime(self):
        proj = make_npm_project({
            "package.json": {"dependencies": {"express": "^4.0.0"}},
        })
        audit = {"vulnerabilities": {
            "minimist": {"severity": "critical", "isDirect": False,
                         "effects": ["express"], "fixAvailable": False,
                         "via": ["GHSA-xvch-5f4q-9x44"]},
        }}
        with mock.patch.object(ra.subprocess, "run") as run:
            run.return_value = unittest.mock.Mock(
                stdout=json.dumps(audit), returncode=0)
            blocking, _, _ = ra.check_npm_audit(proj)
        self.assertEqual(blocking, 1, "effect chain into a runtime dep blocks")

    def test_dev_only_vuln_stays_warning(self):
        proj = make_npm_project({
            "package.json": {"dependencies": {},
                             "devDependencies": {"jest": "^29.0.0"}},
        })
        audit = {"vulnerabilities": {
            "some-dev-dep": {"severity": "high", "isDirect": False,
                             "effects": ["jest"], "fixAvailable": True,
                             "via": ["GHSA-test"]},
        }}
        with mock.patch.object(ra.subprocess, "run") as run:
            run.return_value = unittest.mock.Mock(
                stdout=json.dumps(audit), returncode=0)
            blocking, warnings, _ = ra.check_npm_audit(proj)
        self.assertEqual(blocking, 0, "dev-only vuln must not block")
        self.assertEqual(warnings, 1)


class TestAuditFailureHonesty(unittest.TestCase):
    """npm missing / timeout / empty / unparseable used to read as
    'no vulnerabilities'. They must surface as warnings, never green."""

    def _run(self, proj, **kwargs):
        with mock.patch.object(ra.subprocess, "run") as run:
            if kwargs.get("timeout"):
                run.side_effect = ra.subprocess.TimeoutExpired("npm", 120)
            elif kwargs.get("missing"):
                run.side_effect = FileNotFoundError("npm")
            else:
                run.return_value = unittest.mock.Mock(
                    stdout=kwargs.get("stdout", ""), returncode=1)
            return ra.check_npm_audit(proj)

    def test_missing_npm_is_warning_not_green(self):
        blocking, warnings, issues = self._run(make_npm_project(
            {"package.json": {}}), missing=True)
        self.assertEqual(blocking, 0)
        self.assertEqual(warnings, 1)
        self.assertEqual(issues[0]["name"], "npm-audit-unavailable")

    def test_timeout_is_warning_not_green(self):
        _, warnings, issues = self._run(make_npm_project(
            {"package.json": {}}), timeout=True)
        self.assertEqual(warnings, 1)
        self.assertEqual(issues[0]["name"], "npm-audit-timeout")

    def test_empty_output_is_warning_not_green(self):
        _, warnings, issues = self._run(make_npm_project(
            {"package.json": {}}), stdout="")
        self.assertEqual(warnings, 1)
        self.assertEqual(issues[0]["name"], "npm-audit-empty")

    def test_unparseable_output_is_warning_not_green(self):
        _, warnings, issues = self._run(make_npm_project(
            {"package.json": {}}), stdout="not json{")
        self.assertEqual(warnings, 1)
        self.assertEqual(issues[0]["name"], "npm-audit-unparseable")

    def test_non_npm_project_skips(self):
        proj = Path(tempfile.mkdtemp(prefix="dg-audit-"))
        (proj / "Cargo.toml").write_text("[package]\nname='x'\n")
        blocking, warnings, issues = ra.check_npm_audit(proj)
        self.assertEqual((blocking, warnings, issues), (0, 0, []))


if __name__ == "__main__":
    unittest.main()
