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
    p.write_text(text, encoding="utf-8")
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
        (tmp / ".guardrailsignore").write_text("# frozen legacy\narchive/\n*.generated.go\n", encoding="utf-8")
        pats = load_ignore_patterns(tmp)
        assert pats == ["archive/", "*.generated.go"]
        assert is_ignored(str(tmp / "archive/python/main.py"), str(tmp), pats)
        assert is_ignored(str(tmp / "pkg/tool.generated.go"), str(tmp), pats)
        assert not is_ignored(str(tmp / "go/internal/keep.go"), str(tmp), pats)


# zig-scope-01: the regression scanner honors the project's declared scan
# scope (scan.exclude_dirs) on whole path components.
from game_regression import (  # noqa: E402  (zig-scope-01)
    BUILTIN_EXCLUDE_DIRS,
    load_scan_config,
    path_excludes_excluded_dir,
)


def _zig_hit_file(tmp: Path, rel: str) -> str:
    p = tmp / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("const s = std.mem.alloc(u8, 8);\n", encoding="utf-8")
    return str(p)


def test_load_scan_config_missing_manifest_and_missing_scan_key():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        # No manifest at all: defaults apply, not an error.
        assert load_scan_config(tmp) == (frozenset(), [])
        # Manifest without a `scan` key: defaults apply, not an error.
        (tmp / "game-manifest.json").write_text('{"engine": "Zig + OpenGL"}', encoding="utf-8")
        assert load_scan_config(tmp) == (frozenset(), [])


def test_load_scan_config_reads_declared_exclusions():
    import tempfile, json
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "game-manifest.json").write_text(json.dumps(
            {"engine": "Zig + OpenGL",
             "scan": {"exclude_dirs": ["zig-pkg", "vendor/third"],
                      "non_screen_files": ["src/ui/dispatch.zig"]}}),
            encoding="utf-8")
        exclude, non_screen = load_scan_config(tmp)
        assert exclude == frozenset({"zig-pkg", "vendor/third"})
        assert non_screen == ["src/ui/dispatch.zig"]


def test_load_scan_config_fails_closed_on_malformed_scope():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "game-manifest.json").write_text(
            '{"scan": {"exclude_dirs": "zig-pkg"}}', encoding="utf-8")
        try:
            load_scan_config(tmp)
        except ValueError:
            pass
        else:
            raise AssertionError("a manifest that lies about its scope must fail closed")


def test_path_excludes_whole_components_only():
    excl = frozenset({"zig-pkg"})
    assert path_excludes_excluded_dir("zig-pkg/src/main.zig", excl), "declared dir must be excluded"
    assert path_excludes_excluded_dir("libs/zig-pkg/x.zig", excl), "nested declared segment excludes"
    assert not path_excludes_excluded_dir("zig-pkg.txt", excl), "a FILE named zig-pkg.txt is not the dir"
    assert not path_excludes_excluded_dir("libs/zig-pkg-extra/main.zig", excl), "prefix must not match"
    assert not path_excludes_excluded_dir("src/main.zig", excl)
    assert not path_excludes_excluded_dir("src/main.zig", frozenset()), "empty exclusions exclude nothing"


def test_builtin_excludes_apply_without_declaration():
    # The built-in defaults apply even with no manifest: a project adds, never removes.
    assert ".zig-cache" in BUILTIN_EXCLUDE_DIRS
    assert path_excludes_excluded_dir(".zig-cache/p/q.zig", BUILTIN_EXCLUDE_DIRS)


def test_declared_exclusion_unions_with_defaults_and_filters_scan(tmp_path=None):
    # Integration shape: the same filter main() applies removes the vendored
    # tree from the scan scope while an identical file outside it still scans.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "game-manifest.json").write_text(
            '{"scan": {"exclude_dirs": ["zig-pkg"]}}', encoding="utf-8")
        exclude_dirs, _ = load_scan_config(tmp)
        scope = BUILTIN_EXCLUDE_DIRS | exclude_dirs  # union: add, never remove
        vendored = _zig_hit_file(tmp, "zig-pkg/cache/dep.zig")
        live = _zig_hit_file(tmp, "src/engine/main.zig")
        kept = [f for f in (vendored, live)
                if not path_excludes_excluded_dir(
                    os.path.relpath(f, str(tmp)), scope)]
        assert kept == [live], "vendored findings must not be reported; live tree must still scan"
        # And the live file genuinely fires the Zig pattern class:
        hits = scan_file_for_patterns(live, {"ZIG_MEMORY": [r"std\.mem\.alloc\("]})
        assert len(hits) == 1


# --- 2026-10-26: the pattern table must not report the CHECK as the bug ------
# MergeKingdom's `--all --pre-commit` run reported 60 issues and every one was
# a false positive: 3 `preload` constants, 14 `FileAccess.open` calls whose next
# line is `if file == null:`, 43 `push_error(...)` call sites. Each of these
# tests pins one of those shapes so the noise cannot come back.
from game_regression import GAME_PATTERNS  # noqa: E402


def _scan_text(tmp: Path, name: str, text: str):
    return scan_file_for_patterns(_write(tmp, name, text), GAME_PATTERNS)


def test_preload_constant_is_not_an_unchecked_scene_load():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        hits = _scan_text(tmp, "a.gd",
                          'const SHOP: PackedScene = preload("res://src/ui/shop_popup.tscn")\n')
        assert hits == [], "preload resolves at compile time and cannot fail unchecked"


def test_load_without_a_null_check_still_fires():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        hits = _scan_text(tmp, "b.gd", 'var s = load("res://src/ui/shop_popup.tscn")\n')
        assert [h["pattern"] for h in hits] == ["SCENE_LOAD_FAIL"]


def test_file_open_checked_on_the_next_line_is_not_save_corrupt():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        text = ('func _load() -> void:\n'
                '\tvar file := FileAccess.open("res://data/zones.json", FileAccess.READ)\n'
                '\tif file == null:\n'
                '\t\tpush_error("Failed to open")\n'
                '\t\treturn\n')
        assert _scan_text(tmp, "c.gd", text) == [], "the null check IS the handling, not the bug"


def test_file_open_without_a_null_check_still_fires():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        text = ('func _load() -> void:\n'
                '\tvar file := FileAccess.open("res://data/zones.json", FileAccess.READ)\n'
                '\tprint(file.get_as_text())\n')
        assert [h["pattern"] for h in _scan_text(tmp, "d.gd", text)] == ["SAVE_CORRUPT"]


def test_file_open_guarded_by_gdscript_truthiness():
    # Godot's own save system checks the open with `if file:` / `if not file:`
    # rather than `== null`; both are checks and neither is a defect.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        truthy = ('var file := FileAccess.open(SAVE_PATH, FileAccess.READ)\n'
                  'if file:\n'
                  '\tvar content := file.get_as_text()\n')
        negated = ('var file := FileAccess.open(SAVE_PATH, FileAccess.READ)\n'
                   'if not file:\n'
                   '\treturn false\n')
        assert _scan_text(tmp, "t.gd", truthy) == []
        assert _scan_text(tmp, "n.gd", negated) == []


def test_guard_window_is_bounded():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        text = ('var file := FileAccess.open("res://data/zones.json", FileAccess.READ)\n'
                '\tvar text := file.get_as_text()\n'
                '\tvar n := text.length()\n'
                '\tprint(n)\n'
                '\tif file == null:\n')
        hits = _scan_text(tmp, "e.gd", text)
        assert [h["pattern"] for h in hits] == ["SAVE_CORRUPT"], \
            "a check four lines later is not a guard — the window is 2"


def test_push_error_and_assert_are_not_defects():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        text = ('func f() -> void:\n'
                '\tpush_error("SaveManager: save file is not valid JSON")\n'
                '\tassert(true)\n')
        hits = _scan_text(tmp, "f.gd", text)
        assert hits == [], "SCRIPT_ERROR was retired: push_error is the recommended handling"
        assert "SCRIPT_ERROR" not in GAME_PATTERNS


def test_comment_describing_a_pattern_is_not_a_hit():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        text = ('# Wiring looks like btn.connect("pressed", callable) — described here.\n'
                '// and the same in a C-style comment: x.connect("pressed")\n')
        assert _scan_text(tmp, "g.gd", text) == []


_TESTS = [v for k, v, in sorted(globals().items()) if k.startswith("test_") and callable(v)]

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


def test_zero_files_is_nothing_scanned_not_pass(tmp_path, capsys):
    """No vacuous green: an empty scope prints NOTHING SCANNED and exits 0 by
    default (non-game consumers), 2 with --fail-if-empty (CI)."""
    import subprocess, sys
    script = Path(__file__).resolve().parent.parent / "scripts" / "game_regression.py"
    r = subprocess.run(
        [sys.executable, str(script), "--all", "--pre-commit", "--fail-if-empty"],
        capture_output=True, text=True,
        env={"DEVGATE_PROJECT_ROOT": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "NOTHING SCANNED" in r.stdout
