#!/usr/bin/env python3
# spec: fw-manifest-join-01
"""Behavioral tests for scripts/check_manifest_join.py (fw-manifest-join-01).

The gate exists because a name-keyed join can drift silently: seven
registered MCP tools were absent from the authorization table and every
credential was refused while the tools were still advertised.

  * a declared name with no wired counterpart FAILS (advertised, unreachable)
  * a wired name with no declared counterpart FAILS (dead wiring)
  * agreement in both directions PASSES
  * allow_undeclared suppresses a reviewed exception
  * a STALE join (zero names on either side) FAILS — the vacuity rule
  * a missing manifest FAILS
  * a manifest row without a reason FAILS (reviewability)
  * bidirectional:false tolerates orphans but not unwired names
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_manifest_join.py"
PYTHON = sys.executable


def build(tmp: Path, files: dict[str, str], joins: list[dict]) -> None:
    gd = tmp / ".guardrails"
    gd.mkdir(parents=True, exist_ok=True)
    (gd / "manifest-joins.json").write_text(
        json.dumps({"api_version": "devgate.manifest-joins/v1", "joins": joins}),
        encoding="utf-8")
    for rel, body in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")


def run(tmp: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run([PYTHON, str(SCRIPT), "--repo", str(tmp), *args],
                          capture_output=True, text=True)


def join(declared_pattern="^NAME:(\\w+)", wired_pattern='"([a-z_]+)"',
         allow=(), bidir=True, reason="because") -> dict:
    return {
        "id": "j",
        "reason": reason,
        "declared": {"paths": ["decl.txt"], "pattern": declared_pattern},
        "wired": {"paths": ["wire.txt"], "pattern": wired_pattern},
        "bidirectional": bidir,
        "allow_undeclared": list(allow),
    }


class ManifestJoin(unittest.TestCase):
    def test_agreement_passes(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            build(t, {"decl.txt": "NAME:alpha\nNAME:beta\n",
                      "wire.txt": '{"alpha": 1, "beta": 2}\n'}, [join()])
            r = run(t)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_declared_but_unwired_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            build(t, {"decl.txt": "NAME:alpha\nNAME:ghost\n",
                      "wire.txt": '{"alpha": 1}\n'}, [join()])
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("ghost", r.stdout)

    def test_wired_but_undeclared_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            build(t, {"decl.txt": "NAME:alpha\n",
                      "wire.txt": '{"alpha": 1, "orphan": 2}\n'}, [join()])
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("orphan", r.stdout)

    def test_allow_undeclared_suppresses(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            build(t, {"decl.txt": "NAME:alpha\n",
                      "wire.txt": '{"alpha": 1, "orphan": 2}\n'},
                  [join(allow=["orphan"])])
            r = run(t)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_stale_join_fails_not_skips(self):
        """The vacuity rule: zero names on one side is a FAILURE."""
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            build(t, {"decl.txt": "nothing matches here\n",
                      "wire.txt": '{"alpha": 1}\n'}, [join()])
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("ZERO names", r.stdout)

    def test_missing_manifest_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            (t / "decl.txt").write_text("NAME:x\n", encoding="utf-8")
            r = run(t)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_row_without_reason_fails(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            build(t, {"decl.txt": "NAME:alpha\n", "wire.txt": '{"alpha": 1}\n'},
                  [join(reason="")])
            r = run(t)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_filename_source_join(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            build(t, {"suites/test_alpha.py": "x\n", "suites/test_beta.py": "x\n",
                      "floors.json": '{"test_alpha": 3}\n'},
                  [{
                      "id": "suite-floor",
                      "reason": "every suite needs a floor row",
                      "declared": {"paths": ["suites"], "source": "filename",
                                   "pattern": "^(test_[a-z]+)\\.py$"},
                      "wired": {"paths": ["floors.json"],
                                "pattern": '"(test_[a-z]+)":\\s*[0-9]+'},
                      "bidirectional": True,
                  }])
            r = run(t)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("test_beta", r.stdout)

    def test_non_bidirectional_tolerates_orphans(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d)
            build(t, {"decl.txt": "NAME:alpha\n",
                      "wire.txt": '{"alpha": 1, "extra": 2}\n'},
                  [join(bidir=False)])
            r = run(t)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
