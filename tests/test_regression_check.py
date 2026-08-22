#!/usr/bin/env python3
"""Fixture-based tests for the regression gate's diff + registry matching.

Satisfies the prevention_rule recorded in FAIL-2026071301: "add a unit test
asserting rules fire on a known violation". A gate that silently stops firing is
worse than no gate, so these tests assert the gate FIRES on known violations and
stays SILENT on the cases that must not trip it.

Runnable two ways (DevGate's run-tests.mjs discovers test_*.py via pytest, and
this file also works standalone with plain asserts):

    python3 tests/test_regression_check.py     # standalone
    pytest tests/test_regression_check.py      # via run-tests.mjs

Covers:
  * line-number accuracy on a synthetic multi-hunk, multi-file diff
  * regression_pattern fires when a known bug's signature is re-added
  * file_glob scoping (pattern only fires for matching files)
  * SELF_REFERENTIAL exclusion (definition files never self-match)
  * --all tag-base behaviour (tag wins; HEAD~20 only when no tag exists)
  * touched-vs-untouched hard file-size classification
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from regression_diff import (  # noqa: E402
    SELF_REFERENTIAL,
    check_added_against_registry,
    compile_registry_patterns,
    get_added_lines,
    glob_matches,
    load_active_failures,
    load_failure_registry,
    parse_diff,
    resolve_all_base,
)
from regression_sizes import check_file_sizes  # noqa: E402

# --- fixtures ---------------------------------------------------------------

# Two files, and in the first file two separate hunks. The '@@' headers declare
# the NEW-file start lines, so added lines must be reported at the real numbers:
# src/a.py hunk 1 starts at 10, hunk 2 starts at 200; src/b.go starts at 1.
MULTI_HUNK_DIFF = """\
diff --git a/src/a.py b/src/a.py
--- a/src/a.py
+++ b/src/a.py
@@ -10,3 +10,5 @@ def existing():
 context_line_10
+added_at_11
+added_at_12
 context_line_13
-removed_does_not_advance
 context_line_14
@@ -200,2 +200,3 @@ def other():
 context_line_200
+added_at_201
 context_line_202
diff --git a/src/b.go b/src/b.go
--- /dev/null
+++ b/src/b.go
@@ -0,0 +1,2 @@
+package main
+func main() {}
"""


def _entry(**over) -> dict:
    base = {
        "failure_id": "FAIL-TEST01",
        "status": "resolved",
        "severity": "high",
        "error_message": "the original failure",
        "prevention_rule": "do not do that again",
        "regression_pattern": r"dangerous_call\(",
    }
    base.update(over)
    return base


def _check(added, entries):
    compiled, warnings = compile_registry_patterns(entries)
    return check_added_against_registry(added, compiled), warnings


# --- tests ------------------------------------------------------------------

def test_line_numbers_are_hunk_accurate():
    """Added lines must carry their REAL new-file line numbers, per hunk."""
    added = parse_diff(MULTI_HUNK_DIFF)
    got = [(p, n, t) for p, n, t in added]
    assert got == [
        ("src/a.py", 11, "added_at_11"),
        ("src/a.py", 12, "added_at_12"),
        ("src/a.py", 201, "added_at_201"),
        ("src/b.go", 1, "package main"),
        ("src/b.go", 2, "func main() {}"),
    ], f"hunk-accurate parsing broken: {got}"


def test_removed_lines_do_not_advance_counter():
    """A '-' line does not exist in the new file, so it must not shift numbers."""
    added = parse_diff(MULTI_HUNK_DIFF)
    a_py = [n for p, n, _ in added if p == "src/a.py"]
    assert 201 in a_py, f"second hunk misnumbered (removed line leaked): {a_py}"


def test_regression_pattern_fires_on_readd():
    """A known bug's pattern re-appearing in ADDED code is a violation."""
    added = [("src/app.py", 42, "    dangerous_call(user_input)")]
    violations, warnings = _check(added, [_entry()])
    assert warnings == []
    assert len(violations) == 1, f"pattern did not fire: {violations}"
    v = violations[0]
    assert v["failure_id"] == "FAIL-TEST01"
    assert v["file"] == "src/app.py"
    assert v["line"] == 42, f"wrong line number: {v['line']}"


def test_clean_code_does_not_fire():
    """No match means no violation — the gate must not cry wolf."""
    added = [("src/app.py", 42, "    safe_call(user_input)")]
    violations, _ = _check(added, [_entry()])
    assert violations == [], f"false positive: {violations}"


def test_file_glob_scopes_the_pattern():
    """A globbed entry fires only for matching files (docs may quote patterns)."""
    entries = [_entry(file_glob=["*.py"])]
    py_hit, _ = _check([("src/app.py", 1, "dangerous_call(x)")], entries)
    doc_hit, _ = _check([("docs/notes.md", 1, "never write dangerous_call(x)")], entries)
    assert len(py_hit) == 1, "glob-scoped pattern failed to fire on *.py"
    assert doc_hit == [], f"glob scoping leaked into docs: {doc_hit}"


def test_glob_matches_basename_and_relpath():
    assert glob_matches("scripts/guardrails-scan.mjs", ["*.mjs"])
    assert glob_matches("scripts/guardrails-scan.mjs", ["scripts/*.mjs"])
    assert not glob_matches("scripts/guardrails-scan.mjs", ["*.py"])


def test_self_referential_files_are_excluded():
    """The registry and pattern-rules define the patterns; they must not self-match.

    The fixture line deliberately CONTAINS text the pattern matches (that is what
    a real registry line looks like), so this test only passes because of the
    SELF_REFERENTIAL skip — not because the pattern happened to miss.
    """
    entries = [_entry()]
    literal = 'dangerous_call('
    for path in SELF_REFERENTIAL:
        line = '{"failure_id":"F","regression_pattern":"' + literal + '"}'
        assert literal in line, "fixture must really contain the matched text"
        # Sanity: the same line in a NORMAL file must fire...
        fires, _ = _check([("src/app.py", 1, line)], entries)
        assert len(fires) == 1, "fixture does not actually match the pattern"
        # ...but must be skipped in a definition file.
        violations, _ = _check([(path, 1, line)], entries)
        assert violations == [], f"{path} self-matched: {violations}"


def test_invalid_pattern_warns_but_does_not_crash():
    """One malformed regex must not take the whole gate down."""
    compiled, warnings = compile_registry_patterns([_entry(regression_pattern="unclosed(")])
    assert compiled == []
    assert len(warnings) == 1 and "invalid regression_pattern" in warnings[0]


def test_empty_pattern_is_skipped():
    compiled, warnings = compile_registry_patterns([_entry(regression_pattern="")])
    assert compiled == [] and warnings == []


def test_resolved_entries_are_enforced_active_only_for_advisory(tmp_path=None):
    """Patterns enforce active+resolved; the advisory list stays active-only."""
    reg = Path(__file__).resolve().parent / "_tmp_registry.jsonl"
    reg.write_text(
        '{"failure_id":"F1","status":"resolved","regression_pattern":"x"}\n'
        '{"failure_id":"F2","status":"active","regression_pattern":"y"}\n'
        '{"failure_id":"F3","status":"deprecated","regression_pattern":"z"}\n'
        "# a comment line\n",
        encoding="utf-8",
    )
    try:
        entries = load_failure_registry(reg)
        ids = sorted(e["failure_id"] for e in entries)
        assert ids == ["F1", "F2"], f"deprecated/comment leaked: {ids}"
        active = sorted(e["failure_id"] for e in load_active_failures(entries))
        assert active == ["F2"], f"advisory should be active-only: {active}"
    finally:
        reg.unlink(missing_ok=True)


def test_all_base_uses_tag_when_one_exists():
    """A tag wins — even when the range is EMPTY (tag == HEAD)."""
    def fake_git_with_tag(args):
        if args[:1] == ["describe"]:
            return (0, "v1.2.3\n", "")
        return (0, "", "")
    assert resolve_all_base(fake_git_with_tag) == "v1.2.3"


def test_all_base_falls_back_only_when_no_tag():
    """HEAD~20 is used ONLY when no tag exists at all."""
    def fake_git_no_tag(args):
        if args[:1] == ["describe"]:
            return (128, "", "fatal: No names found")
        return (0, "", "")
    assert resolve_all_base(fake_git_no_tag) == "HEAD~20"


def test_all_scope_does_not_rescan_history_on_empty_range():
    """Tag exists + empty range => no added lines (not a HEAD~20 rescan)."""
    calls = []

    def fake_git(args):
        calls.append(args)
        if args[:1] == ["describe"]:
            return (0, "v1.0.0\n", "")
        return (0, "", "")  # every diff is empty

    added = get_added_lines(fake_git, staged=True, unstaged=True, all_scope=True)
    assert added == []
    assert ["diff", "v1.0.0...HEAD"] in calls, f"tag base not used: {calls}"
    assert not any("HEAD~20" in " ".join(c) for c in calls), f"fell back wrongly: {calls}"


def test_hard_size_blocks_touched_but_warns_untouched(tmp_path=None):
    """Oversize files: touched => error, untouched => warning (legacy debt)."""
    root = Path(__file__).resolve().parent / "_tmp_sizes"
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    big_a = src / "touched.py"
    big_b = src / "untouched.py"
    big_a.write_text("x = 1\n" * 700, encoding="utf-8")
    big_b.write_text("y = 1\n" * 700, encoding="utf-8")
    try:
        issues = check_file_sizes(root, ["src"], touched={"src/touched.py"})
        by_file = {i["file"]: i for i in issues}
        assert by_file["src/touched.py"]["kind"] == "hard", by_file["src/touched.py"]
        assert by_file["src/touched.py"]["severity"] == "error"
        assert by_file["src/untouched.py"]["kind"] == "hard-untouched", by_file["src/untouched.py"]
        assert by_file["src/untouched.py"]["severity"] == "warning"
    finally:
        big_a.unlink(missing_ok=True)
        big_b.unlink(missing_ok=True)
        src.rmdir()
        root.rmdir()


def main() -> int:
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ok   {name}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
