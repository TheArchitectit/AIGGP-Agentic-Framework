# fw-noise-01 (R8) + fw-prov-01 (R11): allowlist-growth monitor and
# exec-bit integrity — both guards must be proven able to FAIL.
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HEALTH = REPO / "scripts" / "allowlist_health.py"
EXECS = REPO / "scripts" / "check_exec_bits.py"


def _git(*a, cwd):
    return subprocess.run(["git", *a], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def _init_repo(with_baseline: bool, entries: list) -> Path:
    td = tempfile.TemporaryDirectory()
    repo = Path(td.name) / "repo"
    repo.mkdir(parents=True)
    _git("init", "-q", cwd=repo)
    _git("config", "user.email", "t@t", cwd=repo)
    _git("config", "user.name", "t", cwd=repo)
    al = repo / ".guardrails" / "silent-success-allowlist.json"
    al.parent.mkdir(parents=True)
    al.write_text(json.dumps({"entries": entries}), encoding="utf-8")
    if with_baseline:
        _git("add", "-A", cwd=repo)
        _git("commit", "-qm", "baseline", cwd=repo)
    _KEEPALIVE.append(td)
    return repo


def run_health(repo: Path, target: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HEALTH), "--allowlist",
         ".guardrails/silent-success-allowlist.json", "--target", target],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, cwd=str(repo))


_KEEPALIVE: list = []


def entry(file, marker):
    return {"file": file, "marker": marker, "family": "x", "reason": "r",
            "removal": "never"}


class TestAllowlistHealth(unittest.TestCase):
    def test_malformed_allowlist_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            _git("init", "-q", cwd=repo)
            bad = repo / ".guardrails" / "silent-success-allowlist.json"
            bad.parent.mkdir(parents=True)
            bad.write_text("{not json", encoding="utf-8")
            r = subprocess.run([sys.executable, str(HEALTH)], cwd=str(repo),
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertIn("FAIL", r.stderr)

    def test_growth_within_budget_is_notice(self):
        repo = _init_repo(True, [entry("a.go", "old")])
        al = repo / ".guardrails" / "silent-success-allowlist.json"
        doc = json.loads(al.read_text(encoding="utf-8"))
        doc["entries"].append(entry("b.go", "new-marker"))
        al.write_text(json.dumps(doc), encoding="utf-8")
        r = run_health(repo, "HEAD")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("NOTICE", r.stdout)
        self.fw_tmp_cleanup = getattr(repo, "fw_tmp", None)

    def test_growth_over_budget_trips_advisory(self):
        repo = _init_repo(True, [entry(f"f{i}.go", f"old{i}")
                                 for i in range(5)])
        al = repo / ".guardrails" / "silent-success-allowlist.json"
        doc = json.loads(al.read_text(encoding="utf-8"))
        doc["entries"].extend(entry(f"n{i}.go", f"new{i}") for i in range(30))
        al.write_text(json.dumps(doc), encoding="utf-8")
        r = run_health(repo, "HEAD")
        self.assertEqual(r.returncode, 10, r.stdout)
        self.assertIn("exceeds the +25 budget", r.stdout)

    def test_test_file_suppression_share_trips_advisory(self):
        repo = _init_repo(True, [entry("prod.go", "old")])
        al = repo / ".guardrails" / "silent-success-allowlist.json"
        doc = json.loads(al.read_text(encoding="utf-8"))
        # 3 additions, all in *_test.go files — above the 50% heuristic.
        doc["entries"].extend(entry(f"t{i}_test.go", f"m{i}")
                              for i in range(3))
        al.write_text(json.dumps(doc), encoding="utf-8")
        r = run_health(repo, "HEAD")
        self.assertEqual(r.returncode, 10, r.stdout)
        self.assertIn("TEST-file content", r.stdout)

    def test_shrink_is_positive_news(self):
        repo = _init_repo(True, [entry(f"f{i}.go", f"old{i}")
                                 for i in range(10)])
        al = repo / ".guardrails" / "silent-success-allowlist.json"
        doc = json.loads(al.read_text(encoding="utf-8"))
        doc["entries"] = doc["entries"][:2]
        al.write_text(json.dumps(doc), encoding="utf-8")
        r = run_health(repo, "HEAD")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("removed (good)", r.stdout)


class TestExecBitCheck(unittest.TestCase):
    def test_negative_control_fires_and_remediation_clears(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "scratch"
            repo.mkdir()

            def g(*a):
                return subprocess.run(["git", *a], cwd=str(repo),
                                      capture_output=True, text=True, encoding="utf-8", errors="replace")

            g("init", "-q")
            g("config", "user.email", "t@t")
            g("config", "user.name", "t")
            g("config", "core.fileMode", "false")  # the lying configuration
            (repo / "run.sh").write_text("#!/bin/bash\necho hi\n", encoding="utf-8")
            g("add", "run.sh")
            r = subprocess.run([sys.executable, str(EXECS), "--repo",
                                str(repo)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=60)
            self.assertEqual(r.returncode, 1,
                             "a shebang file at 100644 must FAIL")
            self.assertIn("git update-index --chmod=+x run.sh",
                          r.stdout + r.stderr)
            g("update-index", "--chmod=+x", "run.sh")
            r2 = subprocess.run([sys.executable, str(EXECS), "--repo",
                                 str(repo)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=60)
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)

    def test_real_tree_passes(self):
        r = subprocess.run([sys.executable, str(EXECS), "--repo", str(REPO)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("all 100755", r.stdout)


if __name__ == "__main__":
    unittest.main()
