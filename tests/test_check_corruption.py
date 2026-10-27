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
  * diff scan: a normal small edit PASSES;
  * diff scan: a submodule pin bump (gitlink) is NOT a flip and a
    pin-bump-only diff PASSES - it is a real range with nothing textual
    to judge, never a vacuous scan.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
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

    def test_submodule_pin_bump_is_not_a_flip(self):
        """A gitlink SHA->SHA pin bump is a commit pointer, not text data.

        The measured false positive: bumping the DevGate submodule pin
        presented as 'Subproject commit <40hex>' vs '<40hex>' - equal length,
        ~90% characters different - and tripped the substitution-flip rule,
        so the diff arm could never pass at a pin-bump head. Every DevGate
        consumer bumps this pin routinely.
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location("cc", str(SCRIPT))
        cc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cc)
        old = "955c6f2a42c0d3c8596183bdd45430657bb040fc"
        new = "b01d5e1ba3f0e7b007921a1d4b18c9f8b0c381e5"
        diff = ("diff --git a/.devgate b/.devgate\n"
                f"index {old[:7]}..{new[:7]} 160000\n"
                "--- a/.devgate\n"
                "+++ b/.devgate\n"
                "@@ -1 +1 @@\n"
                f"-Subproject commit {old}\n"
                f"+Subproject commit {new}\n")
        self.assertEqual(cc.scan_diff(diff, {}, 30), 0)
        # Mixed change: the pin bump is skipped and a real flip still fails.
        flip = ("diff --git a/.devgate b/.devgate\n"
                f"index {old[:7]}..{new[:7]} 160000\n"
                "--- a/.devgate\n"
                "+++ b/.devgate\n"
                "@@ -1 +1 @@\n"
                f"-Subproject commit {old}\n"
                f"+Subproject commit {new}\n"
                "diff --git a/x.md b/x.md\n"
                "--- a/x.md\n"
                "+++ b/x.md\n"
                "@@ -1 +1 @@\n"
                "-alpha bravo charlie delta echo foxtrot golf\n"
                "+qwerty uiopas dfghjkl zxcvbnm nm,./ poiuyt\n")
        self.assertEqual(cc.scan_diff(flip, {}, 30), 1)


class CorruptionFlipPairing(unittest.TestCase):
    """fw-corruption-01 flip pairing is per -/+ RUN, not per file.

    Measured origin 2026-10-19: a commit that inserted a 15-line comment block
    above one edited return statement was reported as three substitution flips
    (scripts/check_charset.py:149,151,152). The inserted comments removed
    nothing; the old pairing matched them line-for-line against unrelated lines
    removed by later hunks. A pure insertion cannot corrupt a line it never
    replaced.
    """

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("cc", str(SCRIPT))
        cc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cc)
        return cc

    def test_pure_insertion_is_not_a_flip(self):
        cc = self._load()
        # The MEASURED shape (scripts/check_charset.py, 2026-10-19): a 15-line
        # comment block inserted above one edited line, plus the style edits
        # the same commit made elsewhere. Removals are short code lines, so the
        # old file-wide pairing matched inserted prose against them and called
        # three of them flips (78% / 70% / 64% changed). No line here
        # substitutes characters in a line it replaced.
        comments = "".join(
            f"+    # strict zero comment {i} for the gate baseline rule\n"
            for i in range(15))
        diff = (
            "diff --git a/scripts/g.py b/scripts/g.py\n"
            "--- a/scripts/g.py\n"
            "+++ b/scripts/g.py\n"
            "@@ -145,0 +146,15 @@ def load_policy(root):\n"
            + comments +
            "@@ -152 +167 @@ def load_policy(root):\n"
            "-    return allowed, denied\n"
            "+    return allowed, denied, strict_paths\n"
            "@@ -207 +230,2 @@\n"
            "-         baseline: dict[str, int] | None = None) -> int:\n"
            "+         baseline: dict[str, int] | None = None,\n"
            "+         strict_paths: set[str] | None = None) -> int:\n"
            "@@ -248 +274,2 @@\n"
            "-                    violations.append((rel, lineno, col, cp, ch))\n"
            "+                    violation = (rel, lineno, col, cp, ch)\n"
            "+                    violations.append(violation)\n"
            "@@ -283,0 +313,2 @@\n"
            "+    if strict_hits:\n"
            "+        return EXIT_VIOLATIONS\n"
        )
        self.assertEqual(cc.scan_diff(diff, {}, 30), 0)

    def test_substitution_flip_in_one_run_still_fails(self):
        # Negative control for the fix: a genuine character-for-character
        # substitution inside a single run must still FAIL.
        cc = self._load()
        diff = (
            "diff --git a/x.md b/x.md\n--- a/x.md\n+++ b/x.md\n"
            "@@ -1 +1 @@\n"
            "-alpha bravo charlie delta echo foxtrot golf\n"
            "+qwerty uiopas dfghjkl zxcvbnm nm,./ poiuyt\n"
        )
        self.assertEqual(cc.scan_diff(diff, {}, 30), 1)

    def test_insert_then_substitute_fails_on_the_substitution(self):
        # Both shapes in one diff: the insertion must stay silent and the real
        # flip must still be reported -- the fix narrows scope, not detection.
        cc = self._load()
        inserted = "".join(
            f"+    # unrelated comment {i} that removes nothing at all\n"
            for i in range(12))
        diff = (
            "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n"
            "@@ -1,0 +2,12 @@\n" + inserted +
            "@@ -40 +52 @@\n"
            "-alpha bravo charlie delta echo foxtrot golf\n"
            "+qwerty uiopas dfghjkl zxcvbnm nm,./ poiuyt\n"
        )
        self.assertEqual(cc.scan_diff(diff, {}, 30), 1)

    def test_unequal_block_is_not_paired_by_index(self):
        # The second measured defect. git emits all removals then all additions
        # in one block, so rewriting a function is ONE run of N removals and M
        # additions. Index pairing drifts when N != M and compares unrelated
        # lines: on scripts/check_corruption.py itself,
        # 'elif line.startswith("@@@"):' was paired with
        # 'path = old_path = None' and called a 65% substitution flip.
        #
        # The first pair below is deliberately tuned to trip the flip
        # thresholds (71% changed, 11% length delta) so that an index-pairing
        # implementation reports a finding here and fails this test. Without
        # that tuning the test passes for the wrong reason and pins nothing.
        cc = self._load()
        removed = [
            "-        elif line.startswith('+++ '):",
            "-            path = line[6:].strip()",
            "-                path = path[2:]",
        ]
        added = [
            "+    qwerty uiopas dfghjkl zxcvbnm",
            "+    poiuyt lkjhg fdsaa mnbvc",
            "+    aqwedrftyu ghjkloiuyt",
            "+    zxcvb nmqwe rtyui opasd",
            "+    lkjhgf dsapoi uytrew qzxcv",
        ]
        diff = ("diff --git a/g.py b/g.py\n--- a/g.py\n+++ b/g.py\n"
                "@@ -1,3 +1,5 @@\n" + "\n".join(removed) + "\n"
                + "\n".join(added) + "\n")
        self.assertEqual(cc.scan_diff(diff, {}, 30), 0)

    def test_equal_size_replacement_still_fails(self):
        # Control in the other direction: when the sizes DO match, the pair is
        # a real replacement and a character substitution must still be caught.
        cc = self._load()
        diff = (
            "diff --git a/x.md b/x.md\n--- a/x.md\n+++ b/x.md\n"
            "@@ -1,2 +1,2 @@\n"
            "-alpha bravo charlie delta echo foxtrot golf\n"
            "-the second line is untouched here\n"
            "+qwerty uiopas dfghjkl zxcvbnm nm,./ poiuyt\n"
            "+the second line is untouched here\n"
        )
        self.assertEqual(cc.scan_diff(diff, {}, 30), 1)

    def test_removed_line_starting_with_dashes_is_content(self):
        # A removed Markdown rule ("--- a note") is data, not a file header.
        # Asserted as a POSITIVE: the removed line must be seen as a removed
        # line, so a character-for-character substitution of it is reported. If
        # the parser swallows it as a header, the flip goes undetected and this
        # fails -- which is what the old parser did.
        cc = self._load()
        diff = (
            "diff --git a/doc.md b/doc.md\n--- a/doc.md\n+++ b/doc.md\n"
            "@@ -1 +1 @@\n"
            "---- alpha bravo charlie delta echo foxtrot golf\n"
            "+--- qwerty uiopas dfghjkl zxcvbnm nm,./ poiuyt\n"
        )
        self.assertEqual(cc.scan_diff(diff, {}, 30), 1)

    def test_whole_file_rewrite_alignment_artifact_is_not_a_flip(self):
        # Measured 2026-10-27 on the vbrainstorm invites.ts barrel split (a
        # 548-line implementation rewritten to a 37-line re-export barrel).
        # The diff is a whole-file rewrite: no line correspondence exists
        # between the sides, but SequenceMatcher still emits equal-size
        # replace blocks from its local alignment, and positional pairing
        # inside one compared a DELETED comment ("This replaces the Phase-1
        # FIXTURE_INVITES map…") with an UNRELATED ADDED comment ("Every
        # public name this module historically exported…") — 78% "changed",
        # length within 3% — and failed the gate on correct code. A rewrite
        # asserts no correspondence at all: the mass-rewrite rule judges it
        # (still warned here — never silent), never flip pairs.
        cc = self._load()
        removed = ["// This replaces the Phase-1 FIXTURE_INVITES map; the InviteView response"]
        removed += [f"// old implementation line {i} carries the moved logic text" for i in range(11)]
        added = ["// Every public name this module historically exported is re-exported here,"]
        added += [f"// barrel re-export stub number {i} keeps import sites unchanged" for i in range(11)]
        diff = ("diff --git a/src/community/invites.ts b/src/community/invites.ts\n"
                "--- a/src/community/invites.ts\n+++ b/src/community/invites.ts\n"
                "@@ -1,12 +1,12 @@\n"
                + "".join(f"-{line}\n" for line in removed)
                + "".join(f"+{line}\n" for line in added))
        out = io.StringIO()
        with redirect_stdout(out):
            verdict = cc.scan_diff(diff, {}, 30)
        self.assertEqual(verdict, 0, out.getvalue())
        self.assertIn("MASS REWRITE", out.getvalue())
        # Control: the SAME tuned pair outside a rewrite is a 1-to-1 in-place
        # substitution and must still fail — the fix narrows scope, not
        # detection (same contract as test_insert_then_substitute_fails_on_the_substitution).
        small = ("diff --git a/src/community/invites.ts b/src/community/invites.ts\n"
                 "--- a/src/community/invites.ts\n+++ b/src/community/invites.ts\n"
                 "@@ -6 +6 @@\n"
                 f"-{removed[0]}\n+{added[0]}\n")
        self.assertEqual(cc.scan_diff(small, {}, 30), 1)


class CorruptionDiffPathResolution(unittest.TestCase):
    """Diff headers resolve to the real path on BOTH sides.

    The header parser used to slice ``line[6:]`` — stripping ``--- `` plus two
    more characters. That works by accident for git's usual ``a/``/``b/``
    prefixed paths (the prefix is consumed by the slice), but a pure
    deletion's ``+++ /dev/null`` became ``ev/null``: the deleted file's
    removed lines were attributed to a nonsense path, so per-file accounting
    (mass-rewrite counting, allowlist lookup, report lines) named the wrong
    file. The slice is the 4-char header marker; the optional prefix is
    stripped separately. Measured shape: any `git rm` hunk in a range.
    """

    def _load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("cc", str(SCRIPT))
        cc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cc)
        return cc

    def test_pure_deletion_attributes_to_the_real_path(self):
        cc = self._load()
        diff = (
            "diff --git a/gone.txt b/gone.txt\n"
            "deleted file mode 100644\n"
            "index 1234567..0000000\n"
            "--- a/gone.txt\n"
            "+++ /dev/null\n"
            "@@ -1,2 +0,0 @@\n"
            "-alpha line here\n"
            "-bravo line here\n"
        )
        removed = [(p, t) for p, _ln, t in cc._removed_lines(diff)]
        self.assertEqual(removed,
                         [("gone.txt", "alpha line here"),
                          ("gone.txt", "bravo line here")])

    def test_new_file_addition_resolves_to_the_new_path(self):
        cc = self._load()
        diff = (
            "diff --git a/fresh.txt b/fresh.txt\n"
            "new file mode 100644\n"
            "index 0000000..1234567\n"
            "--- /dev/null\n"
            "+++ b/fresh.txt\n"
            "@@ -0,0 +1,2 @@\n"
            "+alpha line here\n"
            "+bravo line here\n"
        )
        added = [(p, t) for p, _ln, t in cc._added_lines(diff)]
        self.assertEqual(added,
                         [("fresh.txt", "alpha line here"),
                          ("fresh.txt", "bravo line here")])

    def test_pure_deletion_scan_stays_clean(self):
        # Negative control: resolving the path correctly must not invent a
        # finding — a deletion replaces nothing.
        cc = self._load()
        diff = (
            "diff --git a/gone.txt b/gone.txt\n"
            "deleted file mode 100644\n"
            "index 1234567..0000000\n"
            "--- a/gone.txt\n"
            "+++ /dev/null\n"
            "@@ -1,2 +0,0 @@\n"
            "-alpha line here\n"
            "-bravo line here\n"
        )
        self.assertEqual(cc.scan_diff(diff, {}, 30), 0)


if __name__ == "__main__":
    unittest.main()
