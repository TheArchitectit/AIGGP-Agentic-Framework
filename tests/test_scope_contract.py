# fw-scope-01: single scope contract (R6/R7 of the remediation plan).
"""One SKIP_DIRS definition (.guardrails/scope.json) consumed by every
gate; vendored and cache trees are excluded everywhere; divergence between
gates is a test failure, not a live discovery. The go_return_nil exclusion
seeded per family keeps *_test.go out of THAT family only — scope-not-mute.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class TestSingleScopeContract(unittest.TestCase):
    def test_exactly_one_skip_dirs_definition(self):
        """grep proof: no gate re-declares its own list."""
        hits = []
        for pat in ("scripts/*.mjs", "scripts/*.sh", "scripts/*.py"):
            for f in REPO.glob(pat):
                text = f.read_text(encoding="utf-8", errors="replace")
                if "SKIP_DIRS = [" in text or "SKIP_DIRS = {" in text:
                    hits.append(f.name)
        self.assertEqual(hits, [], f"re-declared scope lists: {hits}")

    def test_scope_json_covers_vendored_and_cache(self):
        scope = json.loads((REPO / ".guardrails/scope.json").read_text())
        for required in ("node_modules", "vendor", "__pycache__", ".venv",
                         ".git", ".sandbox-home"):
            self.assertIn(required, scope["skip_dirs"])

    def test_gates_skip_planted_cache_trees(self):
        """A fake module cache with planted markers must not appear in any
        gate's scan (the 6,703-vs-102 divergence class)."""
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "proj"
            (proj / "src").mkdir(parents=True)
            (proj / "src" / "app.go").write_text(
                "package main\n\nfunc main() {}\n")
            cache = proj / ".sandbox-home" / "go" / "pkg" / "mod" / "example.com"
            cache.mkdir(parents=True)
            planted = cache / "evil.go"
            planted.write_text("package mod\n// fake cache marker\n")
            (proj / ".guardrails").mkdir()
            (proj / ".guardrails" / "scope.json").write_text(
                (REPO / ".guardrails" / "scope.json").read_text())
            env = dict(os.environ, SILENT_SUCCESS_SCAN_ROOT=str(proj))
            ss = subprocess.run(
                ["bash", str(REPO / "scripts" / "silent-success-scan.sh")],
                capture_output=True, text=True, env=env, timeout=120,
                cwd=str(REPO))
            self.assertNotIn("evil.go", ss.stdout + ss.stderr,
                             "cache tree was scanned by silent-success")
            g = subprocess.run(
                ["node", str(REPO / "scripts" / "guardrails-scan.mjs")],
                capture_output=True, text=True, env=env, timeout=120,
                cwd=str(proj))
            self.assertNotIn("evil.go", g.stdout + g.stderr,
                             "cache tree was scanned by guardrails")


class TestGoTestExclusionScopeNotMute(unittest.TestCase):
    """R5: the go_return_nil family excludes *_test.go — and ONLY that
    family; scope belongs to the family, not the walk."""

    def _proj(self, td: Path) -> Path:
        proj = Path(td) / "proj"
        (proj / ".guardrails" / "prevention-rules").mkdir(parents=True)
        rules = json.loads(
            (REPO / ".guardrails" / "prevention-rules" /
             "silent-success-rules.json").read_text())
        (proj / ".guardrails" / "prevention-rules" /
         "silent-success-rules.json").write_text(json.dumps(rules))
        (proj / ".guardrails" / "silent-success-allowlist.json").write_text(
            json.dumps({"entries": []}))
        (proj / "hub").mkdir()
        return proj

    def test_go_test_file_excluded_for_seeded_family(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self._proj(Path(td))
            (proj / "store_test.go").write_text(
                "func TestClose(t *testing.T) {\n"
                "    t.Cleanup(func() { _ = conn.Close() })\n"
                "}\n")
            r = subprocess.run(
                ["bash", str(REPO / "scripts" / "silent-success-scan.sh")],
                capture_output=True, text=True,
                env=dict(os.environ, SILENT_SUCCESS_SCAN_ROOT=str(proj)),
                timeout=120, cwd=str(REPO))
            self.assertEqual(r.returncode, 0, r.stdout)
            # Transparent exclusion, not a silent omit:
            self.assertIn("[excluded] store_test.go", r.stdout)
            self.assertNotIn("[NEW/unlisted] store_test.go", r.stdout)

    def test_non_test_go_file_still_fires(self):
        """The exclusion must not mute the family for production code."""
        with tempfile.TemporaryDirectory() as td:
            proj = self._proj(Path(td))
            (proj / "store.go").write_text(
                "func Close() {\n"
                "    defer func() { _ = conn.Close() }() // ignored error\n"
                "}\n")
            r = subprocess.run(
                ["bash", str(REPO / "scripts" / "silent-success-scan.sh")],
                capture_output=True, text=True,
                env=dict(os.environ, SILENT_SUCCESS_SCAN_ROOT=str(proj)),
                timeout=120, cwd=str(REPO))
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("store.go", r.stdout)


if __name__ == "__main__":
    unittest.main()
