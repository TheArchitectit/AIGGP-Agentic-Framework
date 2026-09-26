# fw-* audit infrastructure: long-term regression corpus / engineering memory.
"""The failure registry is an engineering memory only if it can answer:
'which historical failures does this change risk reintroducing?' and 'is
the recorded protection still real?'. These tests pin both semantics,
including the inverted-reading trap: a pattern matching nothing in the
current tree means the guard is ARMED, not stale.
"""
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.regression_corpus import (load_registry, relevant_entries,
                                       stale_entries)


def _entry(fid="FAIL-1", files=("src/a.py",), pattern=r"buggy_call\(",
           status="resolved", glob=None):
    e = {
        "failure_id": fid,
        "error_message": "something broke",
        "status": status,
        "affected_files": list(files),
        "regression_pattern": pattern,
    }
    if glob:
        e["file_glob"] = glob
    return e


class TestRelevanceSelection(unittest.TestCase):
    def test_direct_path_match(self):
        e = _entry(files=("hub/coherence/evidence.py",))
        hits = relevant_entries([e], ["hub/coherence/evidence.py",
                                      "tests/other.py"])
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["failure_id"], "FAIL-1")

    def test_glob_match(self):
        e = _entry(glob=["hub/coherence/*.py"])
        hits = relevant_entries([e], ["hub/coherence/policy.py"])
        self.assertEqual(len(hits), 1)

    def test_directory_scope_glob(self):
        e = _entry(glob=["hub/"])
        hits = relevant_entries([e], ["hub/server.py"])
        self.assertEqual(len(hits), 1)

    def test_no_match_is_no_hit(self):
        e = _entry(files=("go/cmd/game/runtime.go",))
        self.assertEqual(relevant_entries([e], ["hub/server.py"]), [])

    def test_multiple_entries_multiple_hits(self):
        e1 = _entry(fid="FAIL-1", files=("hub/server.py",))
        e2 = _entry(fid="FAIL-2", glob=["tests/"])
        hits = relevant_entries([e1, e2],
                                ["hub/server.py", "tests/test_x.py"])
        self.assertEqual({h["failure_id"] for h in hits},
                         {"FAIL-1", "FAIL-2"})


class TestStaleness(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "a.py").write_text("x = buggy_call(1)\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_healthy_entry_not_flagged(self):
        """The inverted-reading trap: pattern matches the tree (bug absent?
        then it wouldn't match) — here the file exists and the pattern is
        compilable and the entry is resolved BUT the pattern matches the
        fixed file, which is the overbroad/unresolved case. A genuinely
        healthy entry (pattern absent from the tree) must NOT be flagged."""
        e = _entry(files=("src/a.py",), pattern=r"removed_buggy_thing\(")
        self.assertEqual(stale_entries([e], self.root), [])

    def test_missing_affected_files_flagged(self):
        e = _entry(files=("src/deleted_subsystem.py",))
        stale = stale_entries([e], self.root)
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["missing_paths"],
                         ["src/deleted_subsystem.py"])

    def test_uncompilable_pattern_flagged(self):
        """A pattern that cannot compile can never fire — dead protection."""
        e = _entry(files=("src/a.py",), pattern=r"buggy([call\(")
        stale = stale_entries([e], self.root)
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["dead_pattern"], r"buggy([call\(")

    def test_resolved_entry_matching_own_files_flagged(self):
        """A RESOLVED entry whose pattern still matches its own affected
        file means either the fix is missing or the pattern describes the
        fix's neighborhood instead of the defect — review required."""
        e = _entry(files=("src/a.py",), pattern=r"buggy_call\(",
                   status="resolved")
        stale = stale_entries([e], self.root)
        self.assertEqual(len(stale), 1)
        self.assertIn("buggy_call", stale[0]["unresolved_pattern"])

    def test_active_entry_matching_files_not_flagged(self):
        """An ACTIVE (unfixed) entry whose pattern matches is doing its
        job — it must NOT be reported as stale."""
        e = _entry(files=("src/a.py",), pattern=r"buggy_call\(",
                   status="active")
        self.assertEqual(stale_entries([e], self.root), [])

    def test_multiple_conditions_reported_together(self):
        e = _entry(fid="FAIL-9", files=("src/gone.py",),
                   pattern=r"broken([x")
        stale = stale_entries([e], self.root)
        self.assertEqual(len(stale), 1)
        self.assertTrue(stale[0]["missing_paths"])
        self.assertTrue(stale[0]["dead_pattern"])


class TestRegistryLoading(unittest.TestCase):
    def test_header_comments_skipped_silently(self):
        with TemporaryDirectory() as td:
            p = Path(td) / "registry.jsonl"
            p.write_text(
                "# DevGate Failure Registry\n"
                "# Format: one JSON object per line\n"
                + json.dumps({"failure_id": "FAIL-1"}) + "\n", encoding="utf-8")
            entries = load_registry(p)
            self.assertEqual([e["failure_id"] for e in entries], ["FAIL-1"])

    def test_bad_line_skipped_not_fatal(self):
        with TemporaryDirectory() as td:
            p = Path(td) / "registry.jsonl"
            p.write_text('{"failure_id": "FAIL-1"}\nNOT JSON\n', encoding="utf-8")
            entries = load_registry(p)
            self.assertEqual(len(entries), 1)

    def test_missing_registry_is_empty_not_crash(self):
        with TemporaryDirectory() as td:
            self.assertEqual(load_registry(Path(td) / "nope.jsonl"), [])


if __name__ == "__main__":
    unittest.main()
