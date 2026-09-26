# fw-* audit infrastructure: the silent-success gate must be able to FAIL.
"""A gate that cannot fail is decoration. The silent-success scan shipped
with every detector family disabled, so DevGate's own CI ran it vacuously
(green while testing nothing). Two families are now live for the shipped
service tree; this canary proves both directions against a REAL scan run:

  - a planted 'except ...: pass' in a hub-scoped path is DETECTED (exit 1)
  - a planted violation OUTSIDE every family's glob is NOT (scope honored)
  - the DevGate tree itself passes with the families live
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import pytest

# Requires Unix tooling (bash/chmod/fcntl/systemctl/podman): these tests
# shell out to things that do not exist on Windows, so they cannot run there.
# A test that cannot run must SKIP, not fail -- failing here is indistinguishable
# from real breakage.
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="requires Unix tooling")

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "silent-success-scan.sh"


def run_scan(root: Path, allowlist: Path = None) -> subprocess.CompletedProcess:
    env = dict(os.environ, SILENT_SUCCESS_SCAN_ROOT=str(root))
    if allowlist is not None:
        env["SILENT_SUCCESS_SCAN_ALLOWLIST"] = str(allowlist)
    return subprocess.run(["bash", str(SCRIPT)], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env=env, timeout=120, cwd=str(REPO))


def make_project(tmp: Path) -> Path:
    """A minimal project layout the scan accepts: rules + (empty) allowlist
    + a src tree, mirroring a DevGate submodule consumer."""
    proj = tmp / "proj"
    (proj / ".guardrails" / "prevention-rules").mkdir(parents=True)
    rules = json.loads(
        (REPO / ".guardrails" / "prevention-rules" /
         "silent-success-rules.json").read_text(encoding="utf-8"))
    (proj / ".guardrails" / "prevention-rules" /
     "silent-success-rules.json").write_text(json.dumps(rules), encoding="utf-8")
    allowlist = {"entries": []}
    (proj / ".guardrails" / "silent-success-allowlist.json").write_text(
        json.dumps(allowlist), encoding="utf-8")
    (proj / "hub").mkdir()
    return proj


class TestSilentSuccessGateCanary(unittest.TestCase):
    def test_planted_swallowed_exception_fails_the_gate(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(Path(td))
            victim = proj / "hub" / "evil.py"
            victim.write_text(
                "def handle(req):\n"
                "    try:\n"
                "        return do_work(req)\n"
                "    except Exception: pass  # silent success\n", encoding="utf-8")
            r = run_scan(proj)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("NEW/unlisted", r.stdout)
            self.assertIn("evil.py", r.stdout)
            self.assertIn("python_inline_swallowed_exception", r.stdout)

    def test_scope_respected_outside_globs_is_not_a_hit(self):
        """Tests are where stubs legitimately live; the families' globs
        (hub/, scripts/) must not reach elsewhere."""
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(Path(td))
            (proj / "tests").mkdir()
            (proj / "tests" / "test_stub.py").write_text(
                "def test_x():\n"
                "    try:\n"
                "        run()\n"
                "    except Exception: pass\n", encoding="utf-8")
            r = run_scan(proj)
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_devgate_tree_itself_passes_with_live_families(self):
        """The real self-gate: DevGate's own hub/ and scripts/ are scanned
        with the families live on every run."""
        r = subprocess.run(["bash", str(SCRIPT)], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=120, cwd=str(REPO))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("4 enabled family(ies)", r.stdout,
                      "the self-gate must not be running vacuously")

    def test_allowlisted_hit_is_accepted_but_reported(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(Path(td))
            (proj / "hub").mkdir(exist_ok=True)
            victim = proj / "hub" / "handled.py"
            marker_line = '    except ValueError: pass  # reviewed: no-op is the contract\n'
            victim.write_text("def f():\n" + marker_line, encoding="utf-8")
            allow_fp = (proj / ".guardrails" /
                        "silent-success-allowlist.json")
            allow = json.loads(allow_fp.read_text(encoding="utf-8"))
            allow["entries"].append({
                "file": "hub/handled.py", "marker": "except ValueError: pass",
                "family": "python_inline_swallowed_exception",
                "reason": "drill fixture", "removal": "never"})
            allow_fp.write_text(json.dumps(allow), encoding="utf-8")
            r = run_scan(proj, allowlist=allow_fp)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("[allowlisted]", r.stdout)


if __name__ == "__main__":
    unittest.main()
