#!/usr/bin/env python3
# spec: bd-01, bd-02, evc-01, evc-02, oia-01, oia-02, sr-01, sr-02, srch-01, srch-02, tc-01, tc-02
"""Behavioral fixtures for the six open-item gates (add-open-item-gates 2.9 / 4.3).

Task 2.9 claimed each gate "was demonstrated failing on a fixture before the
commit, and passing on a clean fixture". That demonstration lived only in the
authoring session: nothing in the tree could re-run it, which is the same shape
the package exists to eliminate. Task 4.3 names the remedy. This suite is it.

Every gate is driven end to end as a subprocess against a synthetic fixture,
and each one is pinned in both directions:

  * the failing fixture must exit 1 AND name the offending input, so a gate
    that fails for the wrong reason cannot pass as a pass
  * the clean fixture must exit 0, so the gate is not simply always-red
  * the empty input must exit 3 (or 2 for a missing path), so the shared
    "nothing scanned is never a green" contract is pinned too

Fixtures are built per-test under tmp_path; nothing here touches the real
repository, and no test writes to the tree it is run from.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
PYTHON = sys.executable

EXIT_OK, EXIT_VIOLATION, EXIT_USAGE, EXIT_EMPTY = 0, 1, 2, 3

# A deterministic git identity: the fixtures must run on a machine that has no
# global git config at all (CI runners do), so every invocation carries its own
# and ignores both global config files.
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "open-item-fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "open-item-fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
}


def run(script: str, *args: object) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(SCRIPTS / script), *(str(a) for a in args)],
        capture_output=True, text=True, timeout=180, env=GIT_ENV,
    )


def git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(cwd), env=GIT_ENV,
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd}: {r.stderr}")
    return r.stdout


def make_repo(root: Path, name: str, remote: Path | None = None) -> Path:
    d = root / name
    d.mkdir(parents=True)
    git(d, "init", "-q", "-b", "main")
    if remote is not None:
        git(d, "remote", "add", "origin", str(remote))
    (d / "tracked.txt").write_text("one\n", encoding="utf-8")
    git(d, "add", "tracked.txt")
    git(d, "commit", "-q", "-m", "initial")
    return d


class BranchDrift(unittest.TestCase):
    """branch_drift_check.py — a commit that exists only on local disk is drift."""

    def setUp(self) -> None:
        self.tmp = Path(self._tmp_path())
        self.origin = self.tmp / "origin.git"
        git(self.tmp, "init", "-q", "--bare", str(self.origin))
        self.clone = make_repo(self.tmp, "clone", remote=self.origin)
        git(self.clone, "push", "-q", "-u", "origin", "main")

    def _tmp_path(self) -> str:
        import tempfile
        d = tempfile.mkdtemp(prefix="bd-fixture-")
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        return d

    def _run(self) -> subprocess.CompletedProcess:
        return run("branch_drift_check.py", "--root", self.tmp, "--max-depth", "1")

    def test_clean_when_every_ref_is_on_the_remote(self) -> None:
        r = self._run()
        self.assertEqual(r.returncode, EXIT_OK, r.stdout + r.stderr)

    def test_local_only_commit_is_drift_and_is_named(self) -> None:
        (self.clone / "local.txt").write_text("only here\n", encoding="utf-8")
        git(self.clone, "add", "local.txt")
        git(self.clone, "commit", "-q", "-m", "local only")
        r = self._run()
        self.assertEqual(r.returncode, EXIT_VIOLATION, r.stdout + r.stderr)
        self.assertIn("drift refs: 1", r.stdout)
        self.assertIn("main", r.stdout)

    def test_archive_tag_parks_the_commit_instead_of_failing(self) -> None:
        (self.clone / "parked.txt").write_text("parked\n", encoding="utf-8")
        git(self.clone, "add", "parked.txt")
        git(self.clone, "commit", "-q", "-m", "deliberately parked")
        git(self.clone, "tag", "archive/local-only-20260101")
        r = self._run()
        self.assertEqual(r.returncode, EXIT_OK, r.stdout + r.stderr)
        self.assertIn("archived", r.stdout)

    def test_repository_free_root_is_not_green(self) -> None:
        empty = self.tmp / "empty"
        empty.mkdir()
        r = run("branch_drift_check.py", "--root", empty, "--max-depth", "1")
        self.assertEqual(r.returncode, EXIT_EMPTY, r.stdout + r.stderr)


class EvidenceClaim(unittest.TestCase):
    """evidence_claim_check.py — a marker must carry a followable reference."""

    def setUp(self) -> None:
        import tempfile
        d = tempfile.mkdtemp(prefix="evc-fixture-")
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        self.root = Path(d)

    def _run(self) -> subprocess.CompletedProcess:
        return run("evidence_claim_check.py", "--root", self.root)

    def _write(self, body: str) -> None:
        (self.root / "work.py").write_text(body, encoding="utf-8")

    def test_bare_marker_fails_and_is_named(self) -> None:
        self._write("# TODO: replace the fake repository here\n")
        r = self._run()
        self.assertEqual(r.returncode, EXIT_VIOLATION, r.stdout + r.stderr)
        self.assertIn("work.py", r.stdout)
        self.assertIn("no evidence annotation", r.stdout)

    def test_annotation_missing_a_required_field_fails(self) -> None:
        self._write('# DEFERRED(owner="roger", reason="window")\n')
        r = self._run()
        self.assertEqual(r.returncode, EXIT_VIOLATION, r.stdout + r.stderr)
        self.assertIn("missing", r.stdout)
        self.assertIn("review", r.stdout)

    def test_expired_deferral_fails(self) -> None:
        self._write('# DEFERRED(owner="roger", reason="window", review="2020-01-01")\n')
        r = self._run()
        self.assertEqual(r.returncode, EXIT_VIOLATION, r.stdout + r.stderr)
        self.assertIn("expired", r.stdout)

    def test_fully_annotated_marker_passes(self) -> None:
        self._write(
            '# MOCK(src="docs/fixtures/orders.json", why="vendor sandbox down")\n'
            '# STUB(issue="AIGGP-412", why="interface frozen")\n'
            '# DEFERRED(owner="roger", reason="PG16 window", review="2999-01-01")\n'
        )
        r = self._run()
        self.assertEqual(r.returncode, EXIT_OK, r.stdout + r.stderr)

    def test_empty_root_is_not_green(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        r = run("evidence_claim_check.py", "--root", empty)
        self.assertEqual(r.returncode, EXIT_EMPTY, r.stdout + r.stderr)


class OpenItemAging(unittest.TestCase):
    """open_item_aging_check.py — an aged open item needs a live disposition."""

    TODAY = "2026-11-13"

    def setUp(self) -> None:
        import tempfile
        d = tempfile.mkdtemp(prefix="oia-fixture-")
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        self.root = Path(d)
        self.backlog = self.root / "backlog.md"
        self.triage = self.root / "triage.jsonl"

    def _run(self) -> subprocess.CompletedProcess:
        return run("open_item_aging_check.py", self.backlog,
                   "--triage", self.triage, "--today", self.TODAY)

    def _row(self) -> None:
        self.backlog.write_text(
            "- [ ] NEXT-014 unexercised rotation (2026-08-26)\n", encoding="utf-8")

    def _disposition(self, record: dict) -> None:
        self.triage.write_text(json.dumps(record) + "\n", encoding="utf-8")

    def test_aged_item_without_disposition_fails(self) -> None:
        self._row()
        r = self._run()
        self.assertEqual(r.returncode, EXIT_VIOLATION, r.stdout + r.stderr)
        self.assertIn("NEXT-014", r.stderr)
        self.assertIn("no triage disposition", r.stderr)

    def test_aged_item_with_a_fixed_disposition_passes(self) -> None:
        self._row()
        self._disposition({"id": "NEXT-014", "disposition": "fixed"})
        r = self._run()
        self.assertEqual(r.returncode, EXIT_OK, r.stdout + r.stderr)

    def test_expired_deferral_fails_even_though_it_was_triaged(self) -> None:
        self._row()
        self._disposition({"id": "NEXT-014", "disposition": "deferred",
                           "reason": "waiting", "review_by": "2026-09-01"})
        r = self._run()
        self.assertEqual(r.returncode, EXIT_VIOLATION, r.stdout + r.stderr)
        self.assertIn("has passed", r.stderr)

    def test_open_row_with_no_source_date_fails(self) -> None:
        self.backlog.write_text("- [ ] NEXT-020 an item with no date\n", encoding="utf-8")
        r = self._run()
        self.assertEqual(r.returncode, EXIT_VIOLATION, r.stdout + r.stderr)
        self.assertIn("no parseable source date", r.stderr)

    def test_backlog_with_no_open_rows_is_not_green(self) -> None:
        self.backlog.write_text("- [x] NEXT-001 already closed\n", encoding="utf-8")
        r = self._run()
        self.assertEqual(r.returncode, EXIT_EMPTY, r.stdout + r.stderr)


class SecretRotation(unittest.TestCase):
    """secret_rotation_check.py — scrubbing a secret is not revoking it."""

    TODAY = "2026-11-13"

    def setUp(self) -> None:
        import tempfile
        d = tempfile.mkdtemp(prefix="sr-fixture-")
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        self.ledger = Path(d) / "secret-rotation.jsonl"

    def _entries(self, *rows: dict) -> None:
        self.ledger.write_text(
            "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def _run(self) -> subprocess.CompletedProcess:
        return run("secret_rotation_check.py", self.ledger, "--today", self.TODAY)

    def _base(self, **over: object) -> dict:
        row = {"id": "fp-1", "family": "openai-key", "first_seen": "2026-10-01",
               "removed_from_head": True, "revoked": False}
        row.update(over)
        return row

    def test_scrubbed_but_never_revoked_fails(self) -> None:
        self._entries(self._base())
        r = self._run()
        self.assertEqual(r.returncode, EXIT_VIOLATION, r.stdout + r.stderr)
        self.assertIn("never revoked", r.stderr)

    def test_still_in_head_past_the_window_fails(self) -> None:
        self._entries(self._base(removed_from_head=False))
        r = self._run()
        self.assertEqual(r.returncode, EXIT_VIOLATION, r.stdout + r.stderr)
        self.assertIn("still in HEAD", r.stderr)

    def test_revoked_without_evidence_fails(self) -> None:
        self._entries(self._base(revoked=True, revoked_at="2026-10-02"))
        r = self._run()
        self.assertEqual(r.returncode, EXIT_VIOLATION, r.stdout + r.stderr)
        self.assertIn("missing", r.stderr)

    def test_revocation_with_date_and_evidence_passes(self) -> None:
        self._entries(self._base(revoked=True, revoked_at="2026-10-02",
                                 evidence="TICKET-4471"))
        r = self._run()
        self.assertEqual(r.returncode, EXIT_OK, r.stdout + r.stderr)

    def test_empty_ledger_is_a_pass_by_contract(self) -> None:
        self.ledger.write_text("", encoding="utf-8")
        r = self._run()
        self.assertEqual(r.returncode, EXIT_OK, r.stdout + r.stderr)

    def test_comment_only_ledger_is_not_green(self) -> None:
        self.ledger.write_text("# nothing recorded yet\n", encoding="utf-8")
        r = self._run()
        self.assertEqual(r.returncode, EXIT_EMPTY, r.stdout + r.stderr)


class SurfaceReach(unittest.TestCase):
    """surface_reach_check.py — a change must reach every declared surface."""

    def setUp(self) -> None:
        import tempfile
        d = tempfile.mkdtemp(prefix="srch-fixture-")
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        self.root = Path(d)
        self.manifest = self.root / "surfaces.json"

    def _manifest(self, groups: list[dict]) -> None:
        self.manifest.write_text(json.dumps({"groups": groups}), encoding="utf-8")

    def _surface(self, name: str, body: str) -> Path:
        p = self.root / name
        p.write_text(body, encoding="utf-8")
        return p

    def test_divergent_surfaces_fail_and_the_odd_one_is_named(self) -> None:
        # Two agreeing surfaces and one that drifts: the majority is the
        # intended content, so the odd-one-out is not ambiguous and the gate
        # must name it. A 1-1 pair has no majority; that case is pinned by
        # test_a_tie_still_names_a_surface_and_is_deterministic below.
        a = self._surface("ui-a.tsx", "fixed\n")
        b = self._surface("ui-b.tsx", "fixed\n")
        c = self._surface("ui-c.tsx", "unfixed\n")
        self._manifest([{"name": "shared-sheet", "paths": [str(a), str(b), str(c)]}])
        r = run("surface_reach_check.py", self.manifest)
        self.assertEqual(r.returncode, EXIT_VIOLATION, r.stdout + r.stderr)
        self.assertIn("not reached", r.stderr)
        self.assertIn("ui-c.tsx", r.stderr)

    def test_a_tie_still_names_a_surface_and_is_deterministic(self) -> None:
        # No majority to prefer, so which surface is called "not reached" is a
        # policy choice — but it must be the SAME choice every run. The first
        # version picked max() over a set of hashes, so the answer followed
        # hash randomisation and this fixture named ui-a on one run and ui-b
        # on the next (observed in the full suite, not standalone). Identical
        # input now has to produce byte-identical output.
        a = self._surface("ui-a.tsx", "fixed\n")
        b = self._surface("ui-b.tsx", "unfixed\n")
        self._manifest([{"name": "shared-sheet", "paths": [str(a), str(b)]}])
        first = run("surface_reach_check.py", self.manifest)
        second = run("surface_reach_check.py", self.manifest)
        self.assertEqual(first.returncode, EXIT_VIOLATION, first.stdout + first.stderr)
        self.assertEqual(first.stdout, second.stdout, "tie-break is not deterministic")
        self.assertEqual(first.stderr, second.stderr, "tie-break is not deterministic")
        self.assertTrue("ui-a.tsx" in first.stderr or "ui-b.tsx" in first.stderr,
                        f"no surface named: {first.stderr}")

    def test_identical_surfaces_pass(self) -> None:
        a = self._surface("ui-a.tsx", "fixed\n")
        b = self._surface("ui-b.tsx", "fixed\n")
        self._manifest([{"name": "shared-sheet", "paths": [str(a), str(b)]}])
        r = run("surface_reach_check.py", self.manifest)
        self.assertEqual(r.returncode, EXIT_OK, r.stdout + r.stderr)

    def test_missing_surface_fails_rather_than_skips(self) -> None:
        a = self._surface("ui-a.tsx", "fixed\n")
        self._manifest([{"name": "shared-sheet",
                         "paths": [str(a), str(self.root / "gone.tsx")]}])
        r = run("surface_reach_check.py", self.manifest)
        self.assertEqual(r.returncode, EXIT_VIOLATION, r.stdout + r.stderr)
        self.assertIn("missing", r.stderr)

    def test_exists_mode_checks_presence_only(self) -> None:
        a = self._surface("build-a.txt", "one\n")
        b = self._surface("build-b.txt", "two\n")
        self._manifest([{"name": "generated", "compare": "exists",
                         "paths": [str(a), str(b)]}])
        r = run("surface_reach_check.py", self.manifest)
        self.assertEqual(r.returncode, EXIT_OK, r.stdout + r.stderr)

    def test_manifest_with_no_groups_is_not_green(self) -> None:
        self._manifest([])
        r = run("surface_reach_check.py", self.manifest)
        self.assertEqual(r.returncode, EXIT_EMPTY, r.stdout + r.stderr)


class TreeClean(unittest.TestCase):
    """tree_clean_check.py — unclassified dirt is a failure, generated churn is not."""

    def setUp(self) -> None:
        import tempfile
        d = tempfile.mkdtemp(prefix="tc-fixture-")
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        self.root = Path(d)
        self.repo = make_repo(self.root, "repo")

    def _run(self) -> subprocess.CompletedProcess:
        return run("tree_clean_check.py", "--root", self.root, "--max-depth", "1")

    def test_clean_tree_passes(self) -> None:
        r = self._run()
        self.assertEqual(r.returncode, EXIT_OK, r.stdout + r.stderr)

    def test_untracked_source_file_fails_and_is_named(self) -> None:
        (self.repo / "stray.py").write_text("print('x')\n", encoding="utf-8")
        r = self._run()
        self.assertEqual(r.returncode, EXIT_VIOLATION, r.stdout + r.stderr)
        self.assertIn("stray.py", r.stdout)

    def test_generated_churn_is_classified_not_failed(self) -> None:
        # The human report names generated churn only for offending repos, so
        # this asserts the classification itself via --json: the entry must be
        # counted as generated (not merely tolerated as zero dirt).
        (self.repo / "bytecode.pyc").write_text("binary-ish\n", encoding="utf-8")
        r = run("tree_clean_check.py", "--root", self.root, "--max-depth", "1", "--json")
        self.assertEqual(r.returncode, EXIT_OK, r.stdout + r.stderr)
        result = json.loads(r.stdout)["results"][0]
        self.assertEqual(result["generated"], 1)
        self.assertEqual(result["real_count"], 0)

    def test_repository_free_root_is_not_green(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        r = run("tree_clean_check.py", "--root", empty, "--max-depth", "1")
        self.assertEqual(r.returncode, EXIT_EMPTY, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
