#!/usr/bin/env python3
# spec: fw-corruption-01
"""Behavioral tests for scripts/check_corruption.py (fw-corruption-01).

Locks the contract:
  * U+FFFD FAILS (lossy decode);
  * a mojibake sequence FAILS;
  * a C1 control char FAILS;
  * a zero-width / bidi char FAILS;
  * a reviewed allowlist entry PASSES;
  * a malformed allowlist row refuses to run (exit 2);
  * a zero-file scan FAILS (no vacuous green);
  * the ratchet grandfathers existing corruption but blocks new;
  * diff scan: a substitution flip FAILS;
  * diff scan: an 11-file whole rewrite FAILS as BULK MUTATION;
  * diff scan: a normal small edit PASSES.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_corruption.py"
PYTHON = sys.executable


def make_repo(tmp: Path, files: dict[str, bytes], allowlist: dict | None = None,
              track: list[str] | None = None):
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    subprocess.run(["git", "-C", str(tmp), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp), "config", "user.name", "t"], check=True)
    gd = tmp / ".guardrails"
    gd.mkdir(exist_ok=True)
    (gd / "scope.json").write_text(
        json.dumps({"api_version": "devgate.scope/v1",
                    "skip_dirs": [".git", "node_modules"]}), encoding="utf-8")
    if allowlist is not None:
        (gd / "corruption-allowlist.json").write_text(json.dumps(allowlist),
                                                      encoding="utf-8")
    for rel, data in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    if track is None:
        subprocess.run(["git", "-C", str(tmp), "add", "-A"], check=True)
    else:
        subprocess.run(["git", "-C", str(tmp), "add", "--"] + track, check=True)
    subprocess.run(["git", "-C", str(tmp), "commit", "-qm", "x"], check=True)


def run(tmp: Path, *args):
    return subprocess.run([PYTHON, str(SCRIPT), "--repo", str(tmp), *args],
                          capture_output=True, text=True)


class CorruptionContent(unittest.TestCase):
    def test_replacement_char_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": "bad \ufffd byte\n".encode()})
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("U+FFFD", r.stdout)

    def test_mojibake_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            # UTF-8 bytes for e-acute mis-decoded as Latin-1 (A-tilde + e-acute)
            make_repo(t, {"a.md": "caf\u00c3\u00a9\n".encode()})
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("mojibake", r.stdout)

    def test_c1_control_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": "x\u0085y\n".encode()})
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("C1 control", r.stdout)

    def test_zero_width_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": "a\u200bb\n".encode()})
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("zero-width", r.stdout)

    def test_allowlisted_fixture_passes(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"fixtures/bad.txt": "x\ufffdy\n".encode()},
                      allowlist={"entries": [
                          {"path": "fixtures/bad.txt", "reason": "fixture"}]})
            r = run(t)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_allowlist_without_reason_is_usage_error(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": b"x\n"},
                      allowlist={"entries": [{"path": "a.md"}]})
            r = run(t)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_zero_text_files_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"blob.bin": b"\x00\x01\x02"}, track=["blob.bin"])
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("zero text files", r.stderr)

    def test_clean_passes(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": b"perfectly fine\n"})
            r = run(t)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ratchet_grandfathers_but_blocks_new(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": "x\ufffdy\n".encode()})
            self.assertEqual(run(t).returncode, 1)
            (t / ".guardrails" / "corruption-baseline.json").write_text(
                json.dumps({"files": {"a.md": 1}}), encoding="utf-8")
            subprocess.run(["git", "-C", str(t), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(t), "commit", "-qm", "b"], check=True)
            self.assertEqual(run(t).returncode, 0, run(t).stdout)
            (t / "b.md").write_bytes("new \ufffd\n".encode())
            subprocess.run(["git", "-C", str(t), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(t), "commit", "-qm", "c"], check=True)
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("b.md", r.stdout)


class CorruptionDiff(unittest.TestCase):
    def _diff(self, pairs, path="x.md"):
        out = [f"diff --git a/{path} b/{path}", f"--- a/{path}", f"+++ b/{path}",
               "@@ -1,50 +1,50 @@"]
        for old, new in pairs:
            out.append("-" + old)
            out.append("+" + new)
        return "\n".join(out) + "\n"

    def test_substitution_flip_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"x.md": b"placeholder\n"})
            diff = self._diff([("alpha bravo charlie delta echo foxtrot golf",
                                "qwerty uiopas dfghjkl zxcvbnm nm,./ poiuyt")])
            (t / "d.diff").write_text(diff, encoding="utf-8")
            # feed via --range is awkward in a scratch repo; call the module API
            import importlib.util
            spec = importlib.util.spec_from_file_location("cc", str(SCRIPT))
            cc = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cc)
            self.assertEqual(cc.scan_diff(diff, {}, 30), 1)

    def test_bulk_mutation_fails(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("cc", str(SCRIPT))
        cc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cc)
        parts = []
        for f in range(11):
            hdr = (f"diff --git a/f{f}.md b/f{f}.md\n--- a/f{f}.md\n"
                   f"+++ b/f{f}.md\n@@ -1,12 +1,12 @@\n")
            body = "".join(f"-old line {i} content here\n+new line {i} content here\n"
                           for i in range(12))
            parts.append(hdr + body)
        self.assertEqual(cc.scan_diff("".join(parts), {}, 5), 1)

    def test_normal_edit_passes(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("cc", str(SCRIPT))
        cc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cc)
        diff = ("diff --git a/x.md b/x.md\n--- a/x.md\n+++ b/x.md\n"
                "@@ -1,2 +1,3 @@\n unchanged context line\n"
                "+a brand new sentence that adds meaning\n")
        self.assertEqual(cc.scan_diff(diff, {}, 30), 0)

    def test_empty_diff_fails(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("cc", str(SCRIPT))
        cc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cc)
        self.assertEqual(cc.scan_diff("", {}, 30), 1)


if __name__ == "__main__":
    unittest.main()
