#!/usr/bin/env python3
# spec: fw-encoding-01
"""Behavioral tests for scripts/check_encoding.py (fw-encoding-01).

Locks the contract:
  * a UTF-8 BOM FAILS;
  * UTF-16 (BOM) FAILS;
  * invalid UTF-8 FAILS and is named;
  * CRLF where .gitattributes declares LF FAILS;
  * LF where .gitattributes declares CRLF FAILS;
  * a reviewed allowlist entry (byte-exact fixture) PASSES;
  * a malformed .gitattributes refuses to run (exit 2);
  * a zero-file scan FAILS (no vacuous green);
  * the ratchet grandfathers existing drift but blocks new drift.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_encoding.py"
PYTHON = sys.executable


def make_repo(tmp: Path, files: dict[str, bytes], attrs: str | None = None,
              allowlist: dict | None = None, track: list[str] | None = None):
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    subprocess.run(["git", "-C", str(tmp), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp), "config", "user.name", "t"], check=True)
    gd = tmp / ".guardrails"
    gd.mkdir(exist_ok=True)
    (gd / "scope.json").write_text(
        json.dumps({"api_version": "devgate.scope/v1",
                    "skip_dirs": [".git", "node_modules"]}), encoding="utf-8")
    if allowlist is not None:
        (gd / "encoding-allowlist.json").write_text(json.dumps(allowlist),
                                                    encoding="utf-8")
    if attrs is not None:
        (tmp / ".gitattributes").write_text(attrs, encoding="utf-8")
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


class EncodingGate(unittest.TestCase):
    def test_utf8_bom_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": b"\xef\xbb\xbfhello\n"})
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("BOM", r.stdout)

    def test_utf16_bom_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": "hello\n".encode("utf-16")})
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_invalid_utf8_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": b"caf\xe9 not utf-8\n"})
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("not valid UTF-8", r.stdout)

    def test_crlf_where_lf_declared_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": b"line one\r\nline two\r\n"},
                      attrs="*.md text eol=lf\n")
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("CRLF", r.stdout)

    def test_lf_where_crlf_declared_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.bat": b"line one\nline two\n"},
                      attrs="*.bat text eol=crlf\n")
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("LF-only", r.stdout)

    def test_allowlisted_fixture_passes(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"fixtures/crlf.txt": b"hello\r\n"},
                      attrs="*.txt text eol=lf\n",
                      allowlist={"entries": [
                          {"path": "fixtures/crlf.txt", "reason": "byte pin"}]})
            r = run(t)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_malformed_gitattributes_is_usage_error(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": b"x\n"}, attrs="onlyonefield\n")
            r = run(t)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

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

    def test_clean_tree_passes(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": b"plain\nlines\n"},
                      attrs="*.md text eol=lf\n")
            r = run(t)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ratchet_grandfathers_but_blocks_new(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": b"\xef\xbb\xbfdebt\n"})
            self.assertEqual(run(t).returncode, 1)
            (t / ".guardrails" / "encoding-baseline.json").write_text(
                json.dumps({"files": {"a.md": 1}}), encoding="utf-8")
            subprocess.run(["git", "-C", str(t), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(t), "commit", "-qm", "b"], check=True)
            self.assertEqual(run(t).returncode, 0, run(t).stdout)
            (t / "b.md").write_bytes(b"\xef\xbb\xbfnew debt\n")
            subprocess.run(["git", "-C", str(t), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(t), "commit", "-qm", "c"], check=True)
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("b.md", r.stdout)


if __name__ == "__main__":
    unittest.main()
