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
import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


FLOOR_SCRIPT = Path(__file__).resolve().parent / "gen_floors.py"
FLOOR_SPEC = importlib.util.spec_from_file_location("gen_floors", FLOOR_SCRIPT)
floor_gate = importlib.util.module_from_spec(FLOOR_SPEC)
assert FLOOR_SPEC.loader is not None
FLOOR_SPEC.loader.exec_module(floor_gate)


class PositiveSuiteFloors(unittest.TestCase):
    """The name join covers inventory; this covers each joined floor value."""

    def test_positive_integer_floors_pass_when_counts_meet_them(self):
        doc = {"floors": {"test_alpha": 2}, "total_floor": 2}
        self.assertEqual(floor_gate.validate(doc, {"test_alpha": 2}), [])

    def test_suite_floor_above_collected_count_fails(self):
        doc = {"floors": {"test_alpha": 3}, "total_floor": 1}
        self.assertEqual(floor_gate.validate(doc, {"test_alpha": 2}),
                         ["test_alpha: 2 collected < floor 3"])

    def test_gate_exits_nonzero_for_a_synthetic_zero_suite_floor(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "expected-counts.json"
            out.write_text(json.dumps({"floors": {"test_alpha": 0},
                                       "total_floor": 1}), encoding="utf-8")
            stdout = io.StringIO()
            with (patch.object(floor_gate, "OUT", out),
                  patch.object(floor_gate, "collect",
                               return_value={"test_alpha": 2}),
                  patch.object(sys, "argv", [str(FLOOR_SCRIPT)]),
                  contextlib.redirect_stdout(stdout)):
                self.assertEqual(floor_gate.main(), 1)
            self.assertIn("floor must be a positive JSON integer", stdout.getvalue())

    def test_boolean_float_and_string_suite_floors_fail(self):
        for floor in (True, False, 1.0, "1"):
            with self.subTest(floor=floor):
                doc = {"floors": {"test_alpha": floor}, "total_floor": 1}
                self.assertEqual(
                    floor_gate.validate(doc, {"test_alpha": 2}),
                    ["test_alpha: floor must be a positive JSON integer"],
                )

    def test_historical_missing_or_zero_total_floor_remains_optional(self):
        for doc in (
            {"floors": {"test_alpha": 1}},
            {"floors": {"test_alpha": 1}, "total_floor": 0},
        ):
            with self.subTest(doc=doc):
                self.assertEqual(
                    floor_gate.validate(doc, {"test_alpha": 1}), [])

    def test_update_repairs_invalid_manifest_and_keeps_floors_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "expected-counts.json"
            out.write_text(json.dumps({"note": "keep",
                                       "floors": {"test_alpha": 0}}),
                           encoding="utf-8")
            stdout = io.StringIO()
            with (patch.object(floor_gate, "OUT", out),
                  patch.object(floor_gate, "collect",
                               return_value={"test_alpha": 1}),
                  patch.object(sys, "argv", [str(FLOOR_SCRIPT), "--update"]),
                  contextlib.redirect_stdout(stdout)):
                self.assertEqual(floor_gate.main(), 0)
            updated = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(updated["note"], "keep")
            self.assertEqual(updated["floors"], {"test_alpha": 1})
            self.assertEqual(updated["total_floor"], 0)
            self.assertIn("floors regenerated", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
