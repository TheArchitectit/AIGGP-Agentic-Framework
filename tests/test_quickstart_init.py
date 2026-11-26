# fw-quick-01 (R16): the quickstart must take an empty repo to green gates.
"""End-to-end: scripts/init.mjs --dry-run against a fixture repo must (a)
leave the tree untouched, (b) resolve the baseline workflow set, and (c)
never clobber an existing overlay. The full non-dry init needs network
(submodule add), so the live path is exercised by the transcript in
docs/QUICKSTART-VERIFIED.md rather than in CI."""
import json
import os
import tempfile
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def run_init(target: Path, *extra: str):
    return subprocess.run(
        ["node", str(REPO / "scripts" / "init.mjs"), str(target), *extra],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, cwd=str(REPO))


class TestQuickstartInit(unittest.TestCase):
    def _fixture(self) -> Path:
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        proj = Path(td.name) / "proj"
        proj.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=str(proj))
        return proj

    def test_dry_run_writes_nothing(self):
        proj = self._fixture()
        r = run_init(proj, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((proj / ".devgate").exists())
        self.assertFalse((proj / ".github" / "workflows").exists())
        self.assertIn("dry-run", r.stdout)

    def test_dry_run_resolves_cron_and_labels(self):
        proj = self._fixture()
        r = run_init(proj, "--dry-run", "--cron", "41 5 * * *",
                     "--labels", "devgate")
        self.assertIn("41 5 * * *", r.stdout)
        self.assertIn("devgate", r.stdout)

    def test_all_baseline_workflows_present_in_template_set(self):
        for name in ("guardrails-compliance.yml", "secret-validation.yml",
                     "drift-scan.yml"):
            self.assertTrue(
                (REPO / "templates" / "github-workflows" / name).is_file(),
                f"baseline template missing: {name}")

    def test_init_prints_the_four_gates(self):
        proj = self._fixture()
        r = run_init(proj, "--dry-run")
        for gate in ("guardrails-scan.mjs", "semantic-scan.mjs",
                     "regression_check.py", "silent-success-scan.sh"):
            self.assertIn(gate, r.stdout, f"quickstart must print {gate}")

    def test_carriers_flag_copies_selected_or_all_hooks_without_clobbering(self):
        proj = self._fixture()
        (proj / ".devgate").mkdir(parents=True)
        r = run_init(proj, "--carriers", "claude-code,opencode")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cc = proj / ".guardrails" / "hooks" / "claude-code" / "session-start.sh"
        oc = proj / ".guardrails" / "hooks" / "opencode" / "session-start.mjs"
        self.assertTrue(cc.is_file())
        self.assertTrue(oc.is_file())
        cc.write_text("# custom hook\n", encoding="utf-8")
        r2 = run_init(proj, "--carriers", "all")
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertEqual(cc.read_text(encoding="utf-8"), "# custom hook\n",
                         "existing carrier hook must not be overwritten")
        for rel in (
            "pi-extension/session-init.ts",
            "codex/session-start.sh",
            "mimo/session-start.sh",
        ):
            self.assertTrue((proj / ".guardrails" / "hooks" / rel).is_file(), rel)

    def test_unknown_carrier_fails_closed(self):
        proj = self._fixture()
        r = run_init(proj, "--dry-run", "--carriers", "not-a-carrier")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown carrier", r.stderr)



if __name__ == "__main__":
    unittest.main()
