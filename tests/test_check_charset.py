#!/usr/bin/env python3
# spec: fw-charset-01
"""Behavioral tests for scripts/check_charset.py (fw-charset-01).

Locks the contract that matters:
  * the reported defect (U+00A7) FAILS even though it is only denied, not
    merely absent from the allow list;
  * an allowlisted codepoint (em dash) PASSES;
  * an emoji fails via the deny range;
  * a policy that both allows and denies a codepoint refuses to run (exit 2);
  * a missing allowlist refuses to run (exit 2) - never a silent ban-nothing;
  * a zero-file scan FAILS (no vacuous green);
  * non-UTF-8 bytes FAIL with a named reason;
  * the deny list beats the allow list.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_charset.py"
PYTHON = sys.executable

# A minimal policy the tests control; mirrors the shipped shape.
POLICY = {
    "api_version": "devgate.charset/v1",
    "deny": [
        {"codepoint": "0x00A7", "reason": "section sign"},
        {"range": ["0x1F300", "0x1FAFF"], "reason": "emoji"},
    ],
    "allow": [
        {"codepoint": "0x2014", "reason": "em dash"},
        {"range": ["0x2500", "0x257F"], "reason": "box drawing"},
    ],
}


def make_repo(tmp: Path, files: dict[str, bytes], policy: dict | None = POLICY,
              track: list[str] | None = None):
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    subprocess.run(["git", "-C", str(tmp), "config", "user.email", "t@t"],
                   check=True)
    subprocess.run(["git", "-C", str(tmp), "config", "user.name", "t"],
                   check=True)
    gd = tmp / ".guardrails"
    gd.mkdir(exist_ok=True)
    if policy is not None:
        (gd / "charset-allowlist.json").write_text(json.dumps(policy),
                                                   encoding="utf-8")
    # scope.json is required by gate_common.load_skip_dirs
    (gd / "scope.json").write_text(
        json.dumps({"api_version": "devgate.scope/v1",
                    "skip_dirs": [".git", "node_modules"]}), encoding="utf-8")
    for rel, data in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    if track is None:
        subprocess.run(["git", "-C", str(tmp), "add", "-A"], check=True)
    else:
        subprocess.run(["git", "-C", str(tmp), "add", "--"] + track, check=True)
    subprocess.run(["git", "-C", str(tmp), "commit", "-qm", "x"], check=True)


def run(tmp: Path):
    return subprocess.run([PYTHON, str(SCRIPT), "--repo", str(tmp)],
                          capture_output=True, text=True)


class CharsetGate(unittest.TestCase):
    def test_section_sign_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": "spec 12 \u00a73.2\n".encode()})
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("U+00A7", r.stdout)

    def test_allowlisted_em_dash_passes(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": "range 09\u201413\n".encode()})
            r = run(t)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_emoji_denied_range_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": "done \U0001F528\n".encode()})
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("U+1F528", r.stdout)

    def test_deny_beats_allow(self):
        # U+00A7 listed in BOTH -> refuse to run, never a silent pass.
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            pol = {"deny": [{"codepoint": "0x00A7", "reason": "d"}],
                   "allow": [{"codepoint": "0x00A7", "reason": "a"}]}
            make_repo(t, {"a.md": "x\n".encode()}, policy=pol)
            r = run(t)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("allowed and denied", r.stderr)

    def test_missing_allowlist_is_usage_error(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": "ok\n".encode()}, policy=None)
            r = run(t)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("allowlist missing", r.stderr)

    def test_allowlist_row_without_reason_is_usage_error(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            pol = {"deny": [{"codepoint": "0x00A7"}], "allow": []}
            make_repo(t, {"a.md": "x\n".encode()}, policy=pol)
            r = run(t)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_zero_text_files_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            # Only a binary file is TRACKED: nothing text to scan -> no
            # vacuous green. Policy files exist on disk but are untracked.
            make_repo(t, {"blob.bin": b"\x00\x01\x02"}, track=["blob.bin"])
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("zero text files", r.stderr)

    def test_non_utf8_fails_with_reason(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": b"caf\xe9 latin-1 not utf-8\n"})
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("not valid UTF-8", r.stdout)

    def test_ascii_only_passes(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": "plain ascii -> fine\n".encode(),
                          "b.py": b"x = 1\n"})
            r = run(t)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("within baseline", r.stdout)

    def test_baseline_grandfathers_existing_but_blocks_new(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": "old \u00a7 debt\n".encode()})
            # Without a baseline the pre-existing debt fails.
            self.assertEqual(run(t).returncode, 1)
            # Grandfather it, then a NEW file still fails.
            (t / ".guardrails" / "charset-baseline.json").write_text(
                json.dumps({"files": {"a.md": 1}}), encoding="utf-8")
            subprocess.run(["git", "-C", str(t), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(t), "commit", "-qm", "b"], check=True)
            self.assertEqual(run(t).returncode, 0, run(t).stdout + run(t).stderr)
            (t / "new.md").write_bytes("new \u00a7 debt\n".encode())
            subprocess.run(["git", "-C", str(t), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(t), "commit", "-qm", "c"], check=True)
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("new.md", r.stdout)

    def test_baseline_may_only_decrease(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            make_repo(t, {"a.md": "one \u00a7\n".encode()})
            (t / ".guardrails" / "charset-baseline.json").write_text(
                json.dumps({"files": {"a.md": 5}}), encoding="utf-8")
            subprocess.run(["git", "-C", str(t), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(t), "commit", "-qm", "b"], check=True)
            r = run(t)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("improved", r.stdout)


if __name__ == "__main__":
    unittest.main()
