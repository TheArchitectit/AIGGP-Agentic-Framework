# // spec: coh-id-02
"""Mid-run input mutation (S8 tasks.md:919, measured 2026-09-26): design.md §2
commits to "Snapshots or re-verifies digests at evaluator read time; mutation
mid-run is ERROR (exit 32), never a mixed-content pass", and the exit-32
matrix row names "input mutation" — but the guarantee was documented, not
shipped: `manifest.verify_read` had zero production callers and a probe
showed an evaluator silently reading mutated bytes (a clean VIOLATED computed
from post-snapshot content). The closure re-verifies the closed snapshot
after the last evaluator read (`manifest.first_mutation`): ANY tree move —
replace, delete, add, or a mutation that makes the tree unbuildable — is
ERROR-execution. All fixtures synthetic (R9)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.coherence import evaluate, manifest, result

REPO = Path(__file__).resolve().parent.parent

PACKAGE = {"product": {"identity": {"name": "Alpha"}}}


def _assertion_identity():
    return {
        "id": "a1", "version": 1, "requirement_refs": ["r1"],
        "owner": "o", "requirement": "r",
        "subjects": [{"kind": "file", "path": "README.md"}],
        "evaluator": {"id": "devgate.builtin.identity-consistency",
                      "digest": "sha256:" + "a" * 64},
        "parameters": {"approved_value_ref": "package:product.identity.name"},
        "severity": "high", "dependencies": [],
        "finding_key": ["assertion_id", "subject_location", "violation_class"],
        "evidence": {"retention_days": 1},
    }


def _assertion_marker_scan():
    # The SECOND subject read path: not a declared file, but a whole-tree
    # scan. A guard only on declared files would leave it open.
    return {
        "id": "trace", "version": 1, "requirement_refs": ["r1"],
        "owner": "o", "requirement": "r", "subjects": [],
        "evaluator": {"id": "devgate.builtin.traceability-completeness",
                      "digest": "sha256:" + "b" * 64},
        "parameters": {"marker_scan": True},
        "severity": "high", "dependencies": [],
        "finding_key": ["assertion_id", "subject_location", "violation_class"],
        "evidence": {"retention_days": 1},
    }


class TestMidRunMutation(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dg-mut-"))
        self.root = self.tmp / "subject"
        self.root.mkdir()
        (self.root / "README.md").write_text("# product: Alpha\n",
                                             encoding="utf-8")
        (self.root / "code.py").write_text("# // spec: r1\n", encoding="utf-8")
        self.sm = manifest.build(str(self.root))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, assertion):
        return evaluate.run([assertion], PACKAGE, str(self.root),
                            subject=self.sm)

    def test_honest_tree_still_satisfies(self):
        # Control: the re-verification cannot break honest runs — without
        # this, "mutation refused" proves nothing (the guard could just
        # always fire).
        out = self._run(_assertion_identity())
        self.assertIsNone(out["error"])
        self.assertEqual(out["ledger"][0]["outcome"], "SATISFIED")

    def test_no_subject_snapshot_stays_compatible(self):
        # Legacy/other callers keep working unchanged (subject=None default):
        # the check is wired at the entry point, not forced on every caller.
        out = evaluate.run([_assertion_identity()], PACKAGE, str(self.root))
        self.assertIsNone(out["error"])

    def test_replaced_content_is_execution_error(self):
        (self.root / "README.md").write_text("# product: EVIL\n",
                                             encoding="utf-8")
        out = self._run(_assertion_identity())
        self.assertIsNotNone(out["error"],
                             "mutated bytes must never yield a clean result")
        self.assertEqual(out["error"]["class"], "execution")
        self.assertEqual(out["error"]["reason"],
                         "input-mutation:README.md")
        d, code = result.decide(out["ledger"], 1,
                                error_class=out["error"]["class"])
        self.assertEqual((d, code), ("ERROR", result.EXIT_EXECUTION))
        # "Never a mixed-content pass" is more than the exit code: content
        # computed from POST-snapshot bytes must not reach the findings
        # ledger at all (the outcome gate, not a clear, is what drops them —
        # the honest mutation probe showed a dedicated `fs = []` was dead).
        self.assertEqual(out["findings"], [],
                         "mutated-tree results must not leak into findings")

    def test_deleted_file_is_execution_error(self):
        # Distinct from evaluator UNRESOLVED (selector-empty): deletion must
        # join the mutation class or a swap-to-nothing stays advisory-shaped.
        (self.root / "README.md").unlink()
        out = self._run(_assertion_identity())
        self.assertIsNotNone(out["error"])
        self.assertIn("input-mutation", out["error"]["reason"])

    def test_added_file_is_execution_error(self):
        # The snapshot is CLOSED: an untracked plant changes what the digest
        # committed to, so it is mutation even though no declared file moved.
        (self.root / "planted.py").write_text("x = 1\n", encoding="utf-8")
        out = self._run(_assertion_identity())
        self.assertIsNotNone(out["error"])
        self.assertIn("input-mutation", out["error"]["reason"])

    def test_symlink_boundary_is_pinned_both_directions(self):
        # Symlinks are policy events, not digested content (schema: digest
        # null, frozen). first_mutation compares recorded triples, so a
        # link's POLICY change (forbidden <-> escape) is visible, while an
        # inside-tree RETARGET — same path, same kind, same null digest —
        # is invisible BY DESIGN: the target's content is bound by the
        # subject digest at resolution, not by this guard. Pinned in both
        # directions so a future "digest the symlinks too" change must
        # re-litigate this line, not silently drift from it.
        (self.root / "link").symlink_to("README.md")
        sm2 = manifest.build(str(self.root))
        (self.root / "link").unlink()
        (self.root / "link").symlink_to("code.py")     # retarget, inside tree
        self.assertIsNone(manifest.first_mutation(sm2, str(self.root)),
                          "documented boundary: inside-tree retarget is "
                          "invisible to the triple-diff (target content is "
                          "covered by the subject digest at resolution)")
        (self.root / "link").unlink()
        (self.root / "link").symlink_to("/etc")         # policy class flips
        self.assertEqual(manifest.first_mutation(sm2, str(self.root)),
                         "link", "forbidden -> escape is a recorded-class "
                         "change and MUST be caught")

    def test_undeclared_read_path_is_covered(self):
        # Marker-scan mutation: the guard is whole-tree, so a file NO subject
        # declared cannot drift either.
        (self.root / "code.py").write_text("# nothing\n", encoding="utf-8")
        out = self._run(_assertion_marker_scan())
        self.assertIsNotNone(out["error"])
        self.assertEqual(out["error"]["reason"], "input-mutation:code.py")

    def test_unbuildable_mutation_is_error_not_traceback(self):
        # A mutation that makes the tree ILLEGAL for re-walk (a casefold
        # collision) must relay as execution ERROR — an uncaught
        # SubjectError would crash the run instead of emitting an envelope.
        (self.root / "readme.md").write_text("plant", encoding="utf-8")
        out = self._run(_assertion_identity())
        self.assertIsNotNone(out["error"])
        self.assertEqual(out["error"]["class"], "execution")
        # Exact reason: the sentinel is the ONLY name the envelope carries
        # for this class — a drift in its spelling must not be silent.
        self.assertEqual(out["error"]["reason"],
                         "input-mutation:<tree-unbuildable>")

    def test_first_error_wins_mutation_after_crash(self):
        # Crash already yields ERROR/32; a later-detected mutation must not
        # rewrite the recorded reason (first ERROR-execution condition, the
        # established convention in this loop). The second assertion must
        # PRODUCE a finding from mutated bytes before the check fires — a
        # crashing evaluator returns nothing, so findings stayed empty on its
        # own and the leak this pins was untested (M5 survived the first cut).
        def boom(assertion, package, subject_root, facts):
            raise RuntimeError("crash")

        def dirty_find(assertion, package, subject_root, facts):
            body = (Path(subject_root) / "README.md").read_text(
                encoding="utf-8")
            return [{"assertion_id": assertion["id"],
                     "finding_key": f"{assertion['id']}|README.md|dirty",
                     "violation_class": "dirty", "outcome": "VIOLATED",
                     "enforcement": "BLOCK", "severity": "high",
                     "subject_locations": ["README.md"],
                     "expected": "Alpha", "observed": body, "evidence_refs": []}]

        from unittest import mock
        with mock.patch.dict(evaluate.evaluators.BUILTINS, {
                "devgate.builtin.identity-consistency": boom,
                "devgate.builtin.dirty": dirty_find}):
            a2 = _assertion_identity()
            a2["id"] = "a2"
            a2["evaluator"] = {"id": "devgate.builtin.dirty",
                               "digest": "sha256:" + "c" * 64}
            (self.root / "README.md").write_text("# product: EVIL\n",
                                                 encoding="utf-8")
            out = evaluate.run([_assertion_identity(), a2], PACKAGE,
                               str(self.root), subject=self.sm)
        self.assertIn("evaluator-crash", out["error"]["reason"])
        # Same-run visibility, frozen-matrix style: the mutation is recorded
        # on the row even though the crash owns the run-level reason.
        self.assertEqual(out["ledger"][1]["reason"],
                         "input-mutation:README.md")
        self.assertEqual(out["findings"], [],
                         "the crash-row's run must not leak mutated-bytes findings")

    def test_main_wires_the_snapshot_into_the_runtime(self):
        # Source-level pin (this repo's convention for wiring properties):
        # the built manifest must actually reach evaluate.run — a guard with
        # no caller is how this defect shipped once already.
        src = (REPO / "hub/coherence/__main__.py").read_text(encoding="utf-8")
        self.assertIn("subject=subject", src)


class TestFirstMutation(unittest.TestCase):
    """manifest.first_mutation: the diff primitive itself, named-path exact."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dg-fm-"))
        (self.tmp / "a.txt").write_text("a", encoding="utf-8")
        (self.tmp / "b.txt").write_text("b", encoding="utf-8")
        self.sm = manifest.build(str(self.tmp))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_identical_tree_returns_none(self):
        self.assertIsNone(manifest.first_mutation(self.sm, str(self.tmp)))

    def test_names_first_drifted_path_in_walk_order(self):
        (self.tmp / "b.txt").write_text("changed", encoding="utf-8")
        self.assertEqual(manifest.first_mutation(self.sm, str(self.tmp)),
                         "b.txt")

    def test_repeated_calls_yield_the_same_name(self):
        # Determinism: the reason string must be stable across retries of
        # the same mutated tree (dict/walk order, not set order).
        (self.tmp / "b.txt").write_text("changed", encoding="utf-8")
        (self.tmp / "a.txt").write_text("changed", encoding="utf-8")
        first = manifest.first_mutation(self.sm, str(self.tmp))
        self.assertEqual(first, "a.txt")
        self.assertEqual(first, manifest.first_mutation(self.sm, str(self.tmp)))


if __name__ == "__main__":
    unittest.main()
