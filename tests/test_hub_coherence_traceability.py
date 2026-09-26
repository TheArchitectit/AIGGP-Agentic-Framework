# // spec: coh-assert-04, coh-assert-02, coh-eval-04
"""Repo-marker traceability tests, split out of test_hub_coherence.py when
that file crossed its 600-line hard limit (2026-09-26). Dual-runnable.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import evaluators


class TestTraceabilityMarkerScan(unittest.TestCase):
    """Repo-marker half of traceability_completeness (coh-assert-04,
    coh-eval-04): parameters.marker_scan consumes the repo's `// spec:`
    convention, mirroring scripts/spec_traceability.py."""

    PKG = {"normative_requirements": {
        "r1": {"testable": True, "assertion_ids": ["trace.coverage"]},
        "r2": {"testable": True, "assertion_ids": ["trace.coverage"]},
        "r3": {"testable": False},
    }}

    @staticmethod
    def _assertion():
        return {
            "id": "trace.coverage", "version": 1,
            "requirement_refs": ["r1"], "owner": "o", "requirement": "r",
            "subjects": [{"kind": "file", "path": "src/app.py"}],
            "evaluator": {"id": "devgate.builtin.traceability-completeness",
                          "digest": "sha256:" + "c" * 64},
            "parameters": {"marker_scan": True}, "severity": "medium",
            "dependencies": [], "finding_key": ["a", "l", "v"],
            "evidence": {"retention_days": 1},
        }

    def test_multi_id_marker_line_covers_all(self):
        # One comma-separated marker line claims both ids; the trailing
        # comment stays out of the captured ids.
        with tempfile.TemporaryDirectory() as td:
            subj = Path(td) / "subject"
            (subj / "src").mkdir(parents=True)
            (subj / "src" / "app.py").write_text("// spec: r1, r2 -- why\n", encoding="utf-8")
            fs = evaluators.traceability_completeness(
                self._assertion(), dict(self.PKG), str(subj))
            self.assertEqual(fs, [])

    def test_unmarked_requirement_reported_with_distinct_key(self):
        with tempfile.TemporaryDirectory() as td:
            subj = Path(td) / "subject"
            (subj / "src").mkdir(parents=True)
            (subj / "src" / "app.py").write_text("// spec: r1\n", encoding="utf-8")
            fs = evaluators.traceability_completeness(
                self._assertion(), dict(self.PKG), str(subj))
            self.assertEqual(len(fs), 1)
            self.assertEqual(fs[0]["violation_class"], "unmarked-requirement")
            self.assertEqual(fs[0]["subject_locations"], ["r2"])
            self.assertIn("r2", fs[0]["finding_key"])

    def test_hash_marker_covers_per_gate_grammar(self):
        # The gate's documented convention is `(?://|#) spec:` — `#` alone so
        # Python/shell can carry markers (spec_traceability.py's H6 fix). The
        # evaluator claimed to mirror that grammar but matched `//` only, so a
        # repo covered by the gate read UNMARKED to the evaluator. Both forms
        # must mean the same thing — the divergence was silent either way.
        with tempfile.TemporaryDirectory() as td:
            subj = Path(td) / "subject"
            (subj / "src").mkdir(parents=True)
            (subj / "src" / "app.py").write_text("# spec: r1\n# spec: r2\n", encoding="utf-8")
            fs = evaluators.traceability_completeness(
                self._assertion(), dict(self.PKG), str(subj))
            self.assertEqual(fs, [])

    def test_shell_and_zig_markers_cover(self):
        # The gate scans .sh and .zig (scripts/specs-validate-negative-control.sh
        # carries `# // spec:` markers); the evaluator's extension list lacked
        # them, so the same silent-discovery class as the `#` prefix: covered
        # by the gate, invisible here.
        with tempfile.TemporaryDirectory() as td:
            subj = Path(td) / "subject"
            (subj / "scripts").mkdir(parents=True)
            (subj / "src").mkdir(parents=True)
            (subj / "scripts" / "ctl.sh").write_text("# spec: r1\n", encoding="utf-8")
            (subj / "src" / "main.zig").write_text("// spec: r2\n", encoding="utf-8")
            fs = evaluators.traceability_completeness(
                self._assertion(), dict(self.PKG), str(subj))
            self.assertEqual(fs, [])

    def test_trailing_prose_cannot_fake_coverage(self):
        # The id grammar is comma-anchored: `-- why r2` after the marker
        # must not be read as covering r2.
        with tempfile.TemporaryDirectory() as td:
            subj = Path(td) / "subject"
            (subj / "src").mkdir(parents=True)
            (subj / "src" / "app.py").write_text("// spec: r1 -- why r2\n", encoding="utf-8")
            fs = evaluators.traceability_completeness(
                self._assertion(), dict(self.PKG), str(subj))
            self.assertEqual([f["subject_locations"][0] for f in fs], ["r2"])

    def test_skip_dirs_do_not_cover(self):
        # node_modules/.git/etc. are skipped: a marker only in vendored
        # code does not count (same convention as spec_traceability.py).
        with tempfile.TemporaryDirectory() as td:
            subj = Path(td) / "subject"
            (subj / "node_modules").mkdir(parents=True)
            (subj / "node_modules" / "dep.py").write_text("// spec: r2\n", encoding="utf-8")
            fs = evaluators.traceability_completeness(
                self._assertion(), dict(self.PKG), str(subj))
            # r2's only marker sits in a skipped dir, so both ids are
            # reported unmarked — vendored coverage does not count.
            self.assertEqual(sorted(f["subject_locations"][0] for f in fs),
                             ["r1", "r2"])

    def test_off_by_default(self):
        a = self._assertion()
        a["parameters"] = {}
        with tempfile.TemporaryDirectory() as td:
            subj = Path(td) / "subject"
            subj.mkdir()
            fs = evaluators.traceability_completeness(a, dict(self.PKG), str(subj))
            self.assertEqual(fs, [])

    def test_missing_subject_root_unresolved(self):
        # A missing tree would report every requirement unmarked; that is
        # an unresolvable input (coh-assert-02), never a violation.
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(evaluators.Unresolved) as c:
                evaluators.traceability_completeness(
                    self._assertion(), dict(self.PKG), str(Path(td) / "nope"))
            self.assertIn("subject-root-missing", str(c.exception))


if __name__ == "__main__":
    unittest.main()
