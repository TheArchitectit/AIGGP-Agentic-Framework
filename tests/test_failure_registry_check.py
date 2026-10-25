"""Behavioral tests for scripts/failure_registry_check.py hygiene gate.

Focus (audit finding): an EXPLICIT registry path that does not exist used to
be silently skipped for the non-"devgate" label — a typo'd
FAILURE_REGISTRY_PATH yielded zero entries, zero errors, exit 0, a vacuous
green from the hygiene gate itself. Also locks the merge semantics the
overlay contract promises.
"""
import json
import os
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
    env = dict(os.environ)
    env.pop("FAILURE_REGISTRY_PATH", None)
    return subprocess.run([PYTHON, str(SCRIPT), *args],
                          capture_output=True, text=True, env=env)


class TestExplicitPathHonesty(unittest.TestCase):
    def test_missing_explicit_path_fails_not_vacuous_green(self):
        missing = Path(tempfile.mkdtemp()) / "no-such-registry.jsonl"
        r = run_check()
        # via env override, the documented single-file mode
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


class TestBaseOwn01BundledVsOverlay(unittest.TestCase):
    """base-own-01 splits the same finding by SOURCE: a BUNDLED baseline entry
    naming a stale path or a fix_commit absent from this repo's history is an
    ERROR ("a hygiene gate SHALL fail when a bundled entry references a path
    absent from this tree"), while a project overlay keeps the warning and the
    documented short-SHA leniency. Every failing case is paired with a positive
    control, so the gate cannot pass by refusing everything.
    """

    def _check_module(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from scripts import failure_registry_check as frc  # guardrails-allow PREVENT-024: local scripts/ module, not a registry package
        return frc

    def _layout(self):
        base = Path(tempfile.mkdtemp(prefix="dg-frc-own-"))
        dg = base / "devgate"
        proj = base / "project"
        for root in (dg, proj):
            (root / ".guardrails").mkdir(parents=True)
        return dg, proj

    def _write(self, root, entry):
        path = root / ".guardrails" / "failure-registry.jsonl"
        path.write_text(json.dumps(entry) + "\n")
        return path

    def _entry(self, **over):
        entry = dict(GOOD_ENTRY)
        entry.update(over)
        return entry

    def _git_repo(self, root):
        env = dict(os.environ)
        env.update({
            "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
        })
        subprocess.run(["git", "init", "-q", str(root)], check=True, env=env)
        (root / "tracked.txt").write_text("x\n")
        subprocess.run(["git", "-C", str(root), "add", "tracked.txt"],
                       check=True, env=env)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "init"],
                       check=True, env=env)
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True, env=env,
        ).stdout.strip()

    def test_bundled_stale_path_is_error(self):
        frc = self._check_module()
        dg, proj = self._layout()
        self._write(dg, self._entry(affected_files=["scripts/no-such-file.py"]))
        code, findings = frc.check(devgate_root=dg, project_root=proj)
        self.assertEqual(code, 1, findings)
        self.assertTrue(any("base-own-01" in f for f in findings), findings)
        self.assertTrue(any("scripts/no-such-file.py" in f for f in findings), findings)

    def test_bundled_live_path_is_clean(self):
        dg, proj = self._layout()
        (dg / "scripts").mkdir()
        (dg / "scripts" / "real.py").write_text("#\n")
        self._write(dg, self._entry(affected_files=["scripts/real.py"]))
        code, findings = self._check_module().check(devgate_root=dg, project_root=proj)
        self.assertEqual(code, 0, findings)

    def test_overlay_stale_path_stays_a_warning(self):
        dg, proj = self._layout()
        self._write(dg, self._entry(failure_id="FAIL-base0001"))
        self._write(proj, self._entry(failure_id="FAIL-proj0001",
                                      affected_files=["lib/gone.py"]))
        code, findings = self._check_module().check(devgate_root=dg, project_root=proj)
        self.assertEqual(code, 0, findings)
        self.assertTrue(any("warning" in f and "stale" in f for f in findings), findings)

    def test_bundled_foreign_short_sha_is_error(self):
        dg, proj = self._layout()
        self._git_repo(dg)
        self._write(dg, self._entry(fix_commit="0badc0d"))
        code, findings = self._check_module().check(devgate_root=dg, project_root=proj)
        self.assertEqual(code, 1, findings)
        self.assertTrue(any("not found in git history" in f for f in findings), findings)

    def test_bundled_local_short_sha_is_clean(self):
        dg, proj = self._layout()
        short = self._git_repo(dg)
        self._write(dg, self._entry(fix_commit=short))
        code, findings = self._check_module().check(devgate_root=dg, project_root=proj)
        self.assertEqual(code, 0, findings)

    def test_bundled_foreign_full_sha_is_error(self):
        dg, proj = self._layout()
        self._git_repo(dg)
        self._write(dg, self._entry(fix_commit="0123456789abcdef" * 2 + "01234567"))
        code, findings = self._check_module().check(devgate_root=dg, project_root=proj)
        self.assertEqual(code, 1, findings)
        self.assertTrue(any("not found in git history" in f for f in findings), findings)

    def test_bundled_short_sha_without_git_warns(self):
        dg, proj = self._layout()  # no git history to ask
        self._write(dg, self._entry(fix_commit="0badc0d"))
        code, findings = self._check_module().check(devgate_root=dg, project_root=proj)
        self.assertEqual(code, 0, findings)
        self.assertTrue(any("unverified" in f for f in findings), findings)

    def test_overlay_short_sha_is_not_resolved(self):
        dg, proj = self._layout()
        self._git_repo(dg)
        self._write(dg, self._entry(failure_id="FAIL-base0002"))
        self._write(proj, self._entry(failure_id="FAIL-proj0002", fix_commit="0badc0d"))
        code, findings = self._check_module().check(devgate_root=dg, project_root=proj)
        self.assertEqual(code, 0, findings)


if __name__ == "__main__":
    unittest.main()
