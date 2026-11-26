#!/usr/bin/env python3
"""Behavioral tests for scripts/baseline_ownership_check.py (base-own-01).

The gate's job is narrow and load-bearing: a BUNDLED baseline entry may name
only this repository's paths and only families this repository ships. The case
that motivates it is not hypothetical - the bundled silent-success allowlist was
emptied on 2026-09-19 and silently restored with 1,725 foreign entries the next
day, where it stayed through three more commits that "verified" it.

Every failing case is paired with a positive control, so a gate that passed by
refusing everything could not be green here.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "baseline_ownership_check.py"
ALLOWLIST_REL = Path(".guardrails") / "silent-success-allowlist.json"
RULES_REL = Path(".guardrails") / "prevention-rules" / "silent-success-rules.json"

FAMILY = "go_return_nil_after_ignored_error"
_DEFAULT = object()  # "write the JSON built from entries/families"


def _entry(file: str, *, family: str = FAMILY, marker: str = "_ = f.Close()") -> dict:
    return {"file": file, "marker": marker, "family": family,
            "reason": "fixture", "removal": "n/a"}


class _Tree:
    """A throwaway repo with the two bundled files and a real source file."""

    def __init__(self, entries, *, families=(FAMILY,), disabled=(),
                 file_text="# x\n", rel="pkg/thing.go", allowlist=_DEFAULT,
                 rules=_DEFAULT):
        self._td = tempfile.TemporaryDirectory(prefix="dg-bown-")
        self.root = Path(self._td.name)
        if file_text is not None:
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(file_text, encoding="utf-8")
        if allowlist is not None:
            path = self.root / ALLOWLIST_REL
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"entries": entries}) if allowlist is _DEFAULT
                else allowlist, encoding="utf-8")
        if rules is not None:
            path = self.root / RULES_REL
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                rules if rules is not _DEFAULT else json.dumps(
                    {"rules": [{"family": f, "regex": "x", "enabled": f not in disabled}
                               for f in families]}), encoding="utf-8")

    def check(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--repo", str(self.root), *args],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=60)

    def close(self):
        self._td.cleanup()


class TestBundledAllowlistOwnership(unittest.TestCase):
    def _run(self, entries, *args, **kw):
        tree = _Tree(entries, **kw)
        self.addCleanup(tree.close)
        return tree.check(*args)

    def test_entry_naming_a_live_path_is_clean(self):
        r = self._run([_entry("pkg/thing.go")])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK", r.stdout)

    def test_empty_allowlist_is_clean(self):
        r = self._run([])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_foreign_path_is_error(self):
        r = self._run([_entry("go/cmd/game/battle_test.go")])
        self.assertEqual(r.returncode, 1)
        self.assertIn("go/cmd/game/battle_test.go", r.stderr)
        self.assertIn("base-own-01", r.stderr)

    def test_one_foreign_entry_among_live_ones_still_fails(self):
        r = self._run([_entry("pkg/thing.go"), _entry("internal/admin/bootstrap.go")])
        self.assertEqual(r.returncode, 1)
        self.assertIn("internal/admin/bootstrap.go", r.stderr)

    def test_undeclared_family_is_error(self):
        r = self._run([_entry("pkg/thing.go", family="rust_noop_ok_return")])
        self.assertEqual(r.returncode, 1)
        self.assertIn("rust_noop_ok_return", r.stderr)

    def test_entry_for_a_disabled_family_is_error(self):
        # Declared but disabled: the scanner never evaluates the family, so the
        # entry suppresses nothing while still counting as coverage.
        r = self._run([_entry("pkg/thing.go")], disabled=(FAMILY,))
        self.assertEqual(r.returncode, 1)
        self.assertIn("ships disabled", r.stderr)

    def test_enabled_family_with_a_live_path_is_clean(self):
        # Positive control for the clause above: same family, enabled.
        r = self._run([_entry("pkg/thing.go")], families=(FAMILY,), disabled=())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_absolute_path_is_error(self):
        r = self._run([_entry("/etc/passwd")])
        self.assertEqual(r.returncode, 1)
        self.assertIn("absolute path", r.stderr)

    def test_entry_without_file_is_error(self):
        bad = _entry("pkg/thing.go")
        del bad["file"]
        r = self._run([bad])
        self.assertEqual(r.returncode, 1)
        self.assertIn("no 'file'", r.stderr)

    def test_missing_allowlist_fails_closed(self):
        r = self._run([], allowlist=None)
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing", r.stderr)
        self.assertIn("fail closed", r.stderr)

    def test_malformed_allowlist_fails_closed(self):
        r = self._run([], allowlist="{not json")
        self.assertEqual(r.returncode, 1)
        self.assertIn("cannot be read as JSON", r.stderr)

    def test_non_list_entries_fails_closed(self):
        r = self._run([], allowlist=json.dumps({"entries": {"file": "x"}}))
        self.assertEqual(r.returncode, 1)
        self.assertIn("not a list", r.stderr)

    def test_missing_rules_file_fails_closed(self):
        # The "capabilities" clause cannot be settled without the family list.
        r = self._run([_entry("pkg/thing.go")], rules=None)
        self.assertEqual(r.returncode, 1)
        self.assertIn("fail closed", r.stderr)

    def test_max_report_truncates_and_counts(self):
        entries = [_entry(f"gone/{i}.go") for i in range(30)]
        r = self._run(entries, *["--max-report", "2"])
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr.count("does not exist in this tree"), 2)
        self.assertIn("and 28 more", r.stderr)
        self.assertIn("30 total", r.stderr)


class TestTheRepositoryItself(unittest.TestCase):
    def test_this_repository_is_clean(self):
        r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_bundled_allowlist_is_empty_by_contract(self):
        # Not a style preference: every entry the file could carry belongs to
        # some other repository, and the gate above would fail on it.
        doc = json.loads((REPO / ALLOWLIST_REL).read_text(encoding="utf-8"))
        self.assertEqual(doc["entries"], [],
                         "bundled entries must be empty; a consumer's go in its overlay")


if __name__ == "__main__":
    unittest.main()
