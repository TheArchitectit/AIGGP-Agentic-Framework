#!/usr/bin/env python3
"""Exit-code contract for schema-health-check.mjs and deploy.sh's dispatch.

Regression tests for the 2026-09-27 audit finding: deploy.sh treated the
schema gate's failure exit exactly like a skip (`&&...|| warn`), so a gate
that printed "Deploy blocked." was followed by commit, tag, push, and publish.

Contract now (header of scripts/schema-health-check.mjs):
  0 = ran and passed; 1 = ran and failed / unusable config; 2 = skipped.
deploy.sh: 0 → OK; 2 → loud skip; anything else → abort before release.

    pytest tests/test_schema_health_exitcodes.py   # via run-tests.mjs

The sqlite branches need Node's built-in node:sqlite (experimental flag in
some 22.x lines) — skipped with a reason when the runtime lacks it, never
silently.

"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCHEMA_SCRIPT = REPO / "scripts" / "schema-health-check.mjs"
DEPLOY_SCRIPT = REPO / "scripts" / "deploy.sh"

NODE = shutil.which("node")
SQLITE_OK = False
if NODE:
    _probe = subprocess.run(
        [NODE, "-e", "require('node:sqlite')"], capture_output=True)
    SQLITE_OK = _probe.returncode == 0


def _run_script(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([NODE, str(script), *args],
                          capture_output=True, text=True, timeout=60)


def _configured_copy(tmp: Path, columns: str,
                     uncomment_adapter: bool = True) -> Path:
    """Copy the script with consumer configuration applied.

    Exercises the REAL shipped code with the configuration the header tells
    consumers to apply, rather than re-implementing its logic in the test.
    uncomment_adapter=False leaves the adapter block commented out — the
    "DB_ADAPTER selected but no adapter configured" misconfiguration.
    """
    text = SCHEMA_SCRIPT.read_text(encoding="utf-8")
    text = text.replace(
        'const DB_ADAPTER = "none";', 'const DB_ADAPTER = "sqlite";')
    if uncomment_adapter:
        # Uncomment the sqlite adapter block (the first /*...*/ pair in the
        # adapters section that contains the DatabaseSync import).
        text = re.sub(r"/\*\n(// --- SQLite adapter.*?)\n\*/",
                      r"\1", text, count=1, flags=re.DOTALL)
    text = re.sub(r"const EXPECTED_COLUMNS = \[.*?\];",
                  f"const EXPECTED_COLUMNS = {columns};",
                  text, count=1, flags=re.DOTALL)
    out = tmp / "schema-configured.mjs"
    out.write_text(text, encoding="utf-8")
    return out


class TestExitCodeContract(unittest.TestCase):
    def test_unconfigured_skip_is_exit_2_not_0(self):
        """A skip and a pass must not share an exit code."""
        proc = _run_script(SCHEMA_SCRIPT)
        self.assertEqual(proc.returncode, 2,
                         f"stderr: {proc.stderr}\nstdout: {proc.stdout}")
        self.assertIn("SKIPPED", proc.stdout)

    @unittest.skipUnless(SQLITE_OK, "node:sqlite not available in this runtime")
    def test_adapter_selected_without_block_is_exit_1(self):
        with tempfile.TemporaryDirectory() as td:
            # Adapter block left commented: selected engine, no adapter wired.
            script = _configured_copy(Path(td), '[["t1", "id"]]',
                                      uncomment_adapter=False)
            proc = _run_script(script)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("no adapter is configured", proc.stderr)

    @unittest.skipUnless(SQLITE_OK, "node:sqlite not available in this runtime")
    def test_missing_database_is_a_skip_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            script = _configured_copy(Path(td), '[["t1", "id"]]')
            proc = _run_script(script, "--db", str(Path(td) / "absent.db"))
            self.assertEqual(proc.returncode, 2)
            self.assertIn("SKIPPED", proc.stderr)

    @unittest.skipUnless(SQLITE_OK, "node:sqlite not available in this runtime")
    def test_real_failure_is_exit_1_and_real_pass_is_exit_0(self):
        with tempfile.TemporaryDirectory() as td:
            script = _configured_copy(Path(td), '[["t1", "id"]]')
            db = Path(td) / "app.db"
            subprocess.run([NODE, "-e", f"""
                const {{DatabaseSync}} = require('node:sqlite');
                const db = new DatabaseSync({str(db)!r});
                db.exec('CREATE TABLE t1 (other TEXT)');
            """], check=True, capture_output=True)
            proc = _run_script(script, "--db", str(db))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("Missing column: t1.id", proc.stderr)

            subprocess.run([NODE, "-e", f"""
                const {{DatabaseSync}} = require('node:sqlite');
                const db = new DatabaseSync({str(db)!r});
                db.exec('ALTER TABLE t1 ADD COLUMN id TEXT');
            """], check=True, capture_output=True)
            proc = _run_script(script, "--db", str(db))
            self.assertEqual(proc.returncode, 0, proc.stderr)


class TestDeployDispatch(unittest.TestCase):
    """deploy.sh must abort on gate rc=1 and proceed past the gate on rc=2.

    Drives the REAL deploy.sh in a throwaway git project whose PATH carries a
    node shim: everything passes through to the real node except
    schema-health-check.mjs, which exits the scripted code.
    """

    def _sandbox(self) -> tuple[Path, Path]:
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        proj = Path(td.name) / "project"
        devgate = proj / ".devgate"
        devgate.mkdir(parents=True)
        # deploy.sh derives PROJECT_ROOT from its own location's parent (the
        # layout contract), so the sandbox must look like a .devgate checkout:
        # copy the framework in (minus VCS/caches) and make project/ the repo.
        shutil.copytree(
            REPO, devgate,
            ignore=shutil.ignore_patterns(
                ".git", "__pycache__", "node_modules", ".pytest_cache",
                "*.pyc"),
            dirs_exist_ok=True)
        (proj / "README.md").write_text("sandbox\n")
        for args in (("init", "-q", "-b", "main"),
                     ("config", "user.email", "t@t"),
                     ("config", "user.name", "t"),
                     ("add", "."), ("commit", "-qm", "init"),
                     # Tag the base: deploy's regression gate runs --all
                     # (changes since the last tag), and without a tag it
                     # would audit the copied framework tree itself.
                     ("tag", "-a", "v0.0.1", "-m", "base")):
            subprocess.run(["git", "-C", str(proj), *args],
                           capture_output=True, check=True)
        shim = Path(td.name) / "shim"
        shim.mkdir()
        real_node = shutil.which("node")
        node_shim = shim / "node"
        node_shim.write_text(
            "#!/usr/bin/env bash\n"
            'if [[ "$*" == *schema-health-check.mjs* ]]; then\n'
            '  exit "$FAKE_SCHEMA_RC"\n'
            "fi\n"
            f'exec "{real_node}" "$@"\n')
        node_shim.chmod(0o755)
        return proj, shim

    def _deploy(self, proj: Path, shim: Path, rc: int) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PATH"] = f"{shim}{os.pathsep}{env['PATH']}"
        env["FAKE_SCHEMA_RC"] = str(rc)
        return subprocess.run(
            ["bash", str(proj / ".devgate" / "scripts" / "deploy.sh"), "9.9.9"],
            capture_output=True, text=True, timeout=180, env=env)

    def test_gate_failure_blocks_the_release(self):
        proj, shim = self._sandbox()
        proc = self._deploy(proj, shim, 1)
        combined = proc.stdout + proc.stderr
        self.assertIn("FAIL: schema health gate failed", combined)
        self.assertNotIn("gate complete.", combined)
        self.assertEqual(proc.returncode, 1)

    def test_gate_skip_is_loud_but_non_blocking(self):
        proj, shim = self._sandbox()
        proc = self._deploy(proj, shim, 2)
        combined = proc.stdout + proc.stderr
        self.assertIn("SKIPPED (no database configured)", combined)
        self.assertIn("gate complete.", combined)
        self.assertNotIn("FAIL: schema health", combined)
        # Later stages (tag push without a remote) may abort the sandbox run;
        # the contract under test is only that the GATE did not stop it.


if __name__ == "__main__":
    unittest.main()
