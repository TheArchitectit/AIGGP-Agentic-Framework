#!/usr/bin/env python3
"""Fixture tests for game_regression.py — locks the corrected gate semantics.

Same lesson as test_guardrails_scan.mjs and test_regression_check.py: a gate
that silently stops firing (or over-fires on files it was never scoped to) is
worse than no gate. These assert the scanner:

  * honors a registry entry's file_glob (a "*.go" pattern must NOT fire on a
    .md file that merely quotes the bad pattern),
  * keys guardrails-allow on an ID — accepting the entry's failure_id OR its
    prevention_rule (a bare-substring allow lets one ID silence everything),
  * reads .guardrailsignore so frozen/archived trees are scoped out.

Runnable two ways (pytest collects the test_* functions; the __main__ block
runs them with plain asserts):

    python3 tests/test_game_regression.py
    pytest tests/test_game_regression.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from game_regression import (  # noqa: E402
    glob_matches,
    is_ignored,
    line_has_allow,
    load_ignore_patterns,
    scan_failure_registry_patterns,
    scan_file_for_patterns,
)

# --- registry entry mirroring FAIL-fc601f4b (a real .go-scoped pattern) ------
FC_ENTRY = {
    "failure_id": "FAIL-fc601f4b",
    "regression_pattern": r"string\(rune\('0'\s*\+",
    "prevention_rule": "PREVENT-030",
    "file_glob": ["*.go"],
}


def _write(tmp: Path, rel: str, text: str) -> str:
    p = tmp / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return str(p)


def test_glob_matches_basename_and_relpath():
    assert glob_matches("go/internal/x/x.go", ["*.go"]), "basename arm must reach nested files"
    assert glob_matches("x.go", ["*.go"])
    assert glob_matches("a/b/c.py", ["*.py"])
    assert not glob_matches("a/b/c.md", ["*.go"])
    assert glob_matches("a/b/c.go", ["a/b/*.go"]), "relpath arm for path-scoped globs"


def test_registry_entry_scoped_by_file_glob():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        go = _write(tmp, "internal/spawners/spawners.go", "var x = string(rune('0' + 3))\n")
        md = _write(tmp, "internal/docs/PLAN.md", "spritePath += \"_0\" + string(rune('0'+variant))\n")
        go_hits = scan_failure_registry_patterns(go, [FC_ENTRY], str(tmp))
        md_hits = scan_failure_registry_patterns(md, [FC_ENTRY], str(tmp))
        assert len(go_hits) == 1, "pattern must fire on the matching *.go file"
        assert md_hits == [], "a *.go entry must NOT fire on a .md that quotes it"


def test_allow_is_id_aware_for_registry():
    # The annotation that fixes spawners_test.go must satisfy BOTH gates:
    # Python accepts failure_id OR prevention_rule; JS keys on the rule id.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        by_failure = _write(tmp, "internal/x/x_test.go", "var s = string(rune('0' + 3)) // guardrails-allow FAIL-fc601f4b: asserts absence\n")
        by_rule = _write(tmp, "internal/y/y_test.go", "var s = string(rune('0' + 3)) // guardrails-allow PREVENT-030: asserts absence\n")
        unrelated = _write(tmp, "internal/z/z.go", "var s = string(rune('0' + 3)) // guardrails-allow PREVENT-999: wrong id\n")
        assert scan_failure_registry_patterns(by_failure, [FC_ENTRY], str(tmp)) == []
        assert scan_failure_registry_patterns(by_rule, [FC_ENTRY], str(tmp)) == []
        assert len(scan_failure_registry_patterns(unrelated, [FC_ENTRY], str(tmp))) == 1, "an unrelated allow id must not silence the rule"


def test_line_has_allow_helper():
    assert line_has_allow("// guardrails-allow PREVENT-030: x", "PREVENT-030")
    assert line_has_allow("// guardrails-allow FAIL-abc: x", "FAIL-abc", "PREVENT-030")
    assert not line_has_allow("// guardrails-allow PREVENT-999: x", "PREVENT-030")
    assert not line_has_allow("no annotation here", "PREVENT-030")


def test_builtin_game_pattern_allow():
    # game-class patterns (NULL_DEREF) are also allow-able by their pattern name.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        line = "n = obj.get_node(\"X\").method()  # guardrails-allow NULL_DEREF: guarded above\n"
        f = _write(tmp, "scene.gd", line)
        assert scan_file_for_patterns(f, {"NULL_DEREF": [r"\.get_node\([^)]*\)\s*\.\s*\w+"]}) == []


def test_guardrailsignore_scans(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / ".guardrailsignore").write_text("# frozen legacy\narchive/\n*.generated.go\n")
        pats = load_ignore_patterns(tmp)
        assert pats == ["archive/", "*.generated.go"]
        assert is_ignored(str(tmp / "archive/python/main.py"), str(tmp), pats)
        assert is_ignored(str(tmp / "pkg/tool.generated.go"), str(tmp), pats)
        assert not is_ignored(str(tmp / "go/internal/keep.go"), str(tmp), pats)


_TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]

if __name__ == "__main__":
    failed = 0
    for t in _TESTS:
        try:
            t()
            print(f"ok - {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL - {t.__name__}: {e}")
    print("\nALL TESTS PASSED" if failed == 0 else f"\n{failed} TEST(S) FAILED")
    sys.exit(1 if failed else 0)
