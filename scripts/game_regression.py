#!/usr/bin/env python3
"""Game-class regression scanner (engine-aware).
# spec: zig-regress-01, zig-scope-01

Ported from Sword of Hope's regression_check.py + failure-registry.jsonl patterns.
Adds game-specific failure classes beyond DevGate's generic scanner:

  NULL_DEREF       — runtime null dereference
  SCENE_LOAD_FAIL  — scene fails to instantiate
  SAVE_CORRUPT     — save/load round-trip breaks
  ORPHAN_SIGNAL    — button/signal with no handler
  DETERMINISM_BREAK — seeded run diverges
  PERF_REGRESSION  — frame time / memory exceeds budget

SCRIPT_ERROR was retired 2026-10-26 (see GAME_PATTERNS): its rules flagged
`push_error(` and `assert(`, which are the recommended handling and a
deliberate guard rather than defects. DETERMINISM_BREAK and PERF_REGRESSION
are documented classes with no line-regex rule yet — they need a seeded run /
a timing harness, not a text scan, and the scanner does not pretend otherwise.

Patterns are matched line by line; a rule may be a `(regex, guard, window)`
tuple that suppresses its hit when one of the next `window` lines matches
`guard`, so a null check written on the following line is recognised instead
of reported as the bug.

The engine is detected from game-manifest.json (else project files) and the
matching pattern table is applied; unknown engines fall back to the Godot set.
Zig + OpenGL classes (ZIG_COMPILE, ZIG_MEMORY, OPENGL_CTX, SHADER_FAIL,
INPUT_CAPTURE) were imported from the former devgate-game-framework repository
(merged 2026-09-26).

Reads .guardrails/failure-registry.jsonl and scans staged/unstaged changes
against known game-class patterns. Exit 1 on hard violations with --pre-commit.

Spec coverage:
  zig-regress-01 — the Zig + OpenGL regression classes block staged changes.
  zig-scope-01  — scan scope is declared by the project manifest:
                  game-manifest.json `scan.exclude_dirs` unions with the built-in
                  defaults (a project may add exclusions, never remove them),
                  matched on whole path components; a missing `scan` key means
                  "defaults apply", not an error.
"""
import json, os, re, sys, subprocess
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_overlay  # noqa: E402
# Shared primitives — one implementation (scripts/gate_common.py).
from gate_common import (  # noqa: E402
    glob_matches,
    is_ignored,
    line_has_allow,
    load_ignore_patterns,
    load_skip_dirs,
    project_root,
    nothing_scanned,
)

# Game-class patterns (regex-based, loaded from failure-registry.jsonl).
#
# A rule is either a bare regex, matched against one line, or a
# `(regex, guard, window)` tuple: the hit is NOT reported when any of the next
# `window` lines matches `guard`. That is how a one-line heuristic honours the
# check the author actually wrote on the following line — without it the gate
# reports the check itself as the failure.
#
# Measured on MergeKingdom, 2026-10-26 (`--all --pre-commit`, 60 issues):
# every SCENE_LOAD_FAIL and SAVE_CORRUPT hit was this shape — a `preload` on a
# compile-time constant, or a `FileAccess.open` whose very next line is
# `if file == null:`. None of the 60 was a defect.
#
# The guard has to accept GDScript's truthiness check too: `if file:` and
# `if not file:` are the idiom the save system actually uses (6 of the first 7
# hits left after the null-check guard), and a one-line `if …:` head is the
# only form that can be recognised without tracking variable names.
_CHECKED = r"(==\s*null|!=\s*null|is_instance_valid\(|^\s*if\b.*:\s*$)"
_OK_GUARD = r"(!=\s*(Error\.)?OK|==\s*(Error\.)?OK)"

GAME_PATTERNS = {
    "NULL_DEREF": [
        r"\.get_node\([^)]*\)\s*\.\s*\w+",      # unsafe get_node chain
        r"if\s+\w+\s*==\s*null\s*:\s*pass",       # null check + no-op (swallowed)
    ],
    "SCENE_LOAD_FAIL": [
        # `preload` resolves at compile time and cannot fail, so the lookbehind
        # keeps a PackedScene constant out of the "unchecked load" family.
        (r"(?<!pre)\bload\([^)]*\.tscn[^)]*\)\s*$", _CHECKED, 2),
        (r"change_scene_to_file\([^)]*\)", _OK_GUARD, 2),  # scene change without error handling
    ],
    "SAVE_CORRUPT": [
        # Lowercase `json.parse` callers (JS/Lua-shaped). GDScript spells it
        # `JSON.parse_string` and every real site checks the result in one of
        # three idioms (== null, `is Dictionary`, bare truthiness) that a
        # one-line regex cannot tell apart, so that spelling is deliberately
        # NOT covered here rather than covered by a guard loose enough to pass
        # everything. See the spec's SAVE_CORRUPT coverage note.
        (r"json\.parse\([^)]*\)\s*$", _CHECKED, 2),   # JSON.parse without error check
        (r"FileAccess\.open[^)]*\)\s*$", _CHECKED, 2),  # file open without error check
    ],
    # SCRIPT_ERROR was retired 2026-10-26: its two rules were `push_error(` and
    # `assert(`, i.e. it flagged the RECOMMENDED handling and a deliberate
    # guard. On MergeKingdom all 43 of its hits were `push_error(...)` call
    # sites; zero were defects. A one-line regex cannot see a GDScript runtime
    # error anyway — that needs a real engine run. See the spec's retired-family
    # scenario for what replaced it.
    "ORPHAN_SIGNAL": [
        r'\.connect\("pressed"',                   # signal connect without method check
    ],
}

# Zig + OpenGL engine patterns — imported from the former devgate-game-framework
# repository (merged 2026-09-26). Selected by detect_engine().
ZIG_PATTERNS = {
    "ZIG_COMPILE": [
        r"error:.*unexpected",
        r"compile error",
    ],
    "ZIG_MEMORY": [
        r"std\.mem\.alloc\(",
    ],
    "OPENGL_CTX": [
        r"glGetError\(\)",
    ],
    "SHADER_FAIL": [
        r"glCompileShader",
    ],
    "INPUT_CAPTURE": [
        r"glfwSetKeyCallback",
    ],
}

# Engine -> pattern table. Unknown engines fall back to the Godot/game set.
ENGINE_PATTERNS = {
    "Godot": GAME_PATTERNS,
    "Zig + OpenGL": ZIG_PATTERNS,
}

# zig-scope-01: whole path components that the scanner never descends into,
# independent of any project declaration (third-party caches, toolchains,
# editor state). `scan.exclude_dirs` unions with this set — a project may
# add exclusions, never remove them.
BUILTIN_EXCLUDE_DIRS = frozenset({
    ".zig-cache", ".zig-o", "zig-out", "node_modules", ".git",
    ".venv", "venv", "__pycache__",
})


def load_scan_config(root):
    """zig-scope-01: read the project's declared scan scope from
    game-manifest.json.

    Returns (exclude_dirs, non_screen_files):
      exclude_dirs      — `scan.exclude_dirs`, matched on WHOLE path
                          components (a declared `zig-pkg` excludes
                          `zig-pkg/src/x.zig`, not a file named `zig-pkg.txt`
                          nor `libs/zig-pkg-extra`). Missing `scan` key (or
                          missing manifest) = defaults apply, not an error.
      non_screen_files  — `scan.non_screen_files` (the UI-inventory carve-out;
                          validated here so the manifest contract fails closed
                          for both game gates; scene_inventory's loader stays
                          authoritative for the UI inventory itself).

    Malformed types are rejected (fail closed) — a manifest that lies about
    its scope must stop the gate, not shrink it silently.
    """
    root = Path(root)
    manifest_path = root / "game-manifest.json"
    if not manifest_path.exists():
        return frozenset(), []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        # Unreadable manifest: no declared scope; the built-in defaults still
        # apply. detect_engine already tolerates this for the engine field.
        return frozenset(), []
    if not isinstance(data, dict):
        return frozenset(), []
    scan = data.get("scan")
    if scan is None:
        return frozenset(), []
    if not isinstance(scan, dict):
        raise ValueError(f"{manifest_path}: 'scan' must be an object")
    exclude = scan.get("exclude_dirs") or []
    non_screen = scan.get("non_screen_files") or []
    if not isinstance(exclude, list) or not all(isinstance(d, str) for d in exclude):
        raise ValueError(f"{manifest_path}: scan.exclude_dirs must be a list of strings")
    if not isinstance(non_screen, list) or not all(isinstance(f, str) for f in non_screen):
        raise ValueError(f"{manifest_path}: scan.non_screen_files must be a list of strings")
    return frozenset(exclude), list(non_screen)


def path_excludes_excluded_dir(rel_path: str, exclude_dirs) -> bool:
    """zig-scope-01: whole-component matching. True when any segment of the
    file's path equals a declared exclusion. Segment-wise, so `zig-pkg` does
    not exclude `zig-pkg.txt` or `libs/zig-pkg-extra/main.zig`."""
    if not exclude_dirs:
        return False
    parts = PurePosixPath(rel_path.replace("\\", "/")).parts
    return any(seg in exclude_dirs for seg in parts[:-1])

def detect_engine(root):
    """Detect the project engine from game-manifest.json, else by project files.

    Mirrors the detection in scene_inventory.py so both game gates agree on the
    engine. A manifest `engine` value wins; otherwise project/build markers are
    consulted; anything else is `unknown` (callers fall back to Godot patterns).
    """
    root = Path(root)
    manifest_path = root / "game-manifest.json"
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text()).get("engine", "unknown")
        except Exception:
            pass
    if (root / "project.godot").exists():
        return "Godot"
    if (root / "build.zig").exists():
        return "Zig + OpenGL"
    return "unknown"

def find_project_root():
    """Project root by layout contract, with DEVGATE_PROJECT_ROOT override.

    Lives in gate_common.project_root (root-anchor-01). Kept as a named
    alias because callers and tests import it under this name.
    """
    return project_root()

# fw-scope-01: single scope contract — loaded, never redeclared here.
SKIP_DIRS = load_skip_dirs()

# glob_matches / line_has_allow / load_ignore_patterns / is_ignored are
# re-exported from gate_common (shared).

def iter_source_files(root, ignore_patterns=()):
    """Walk the tree collecting scannable source files, skipping SKIP_DIRS and ignores."""
    exts = {".gd", ".ts", ".js", ".py", ".rs", ".go", ".zig"}
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if os.path.splitext(name)[1] in exts:
                path = os.path.join(dirpath, name)
                if not is_ignored(path, root, ignore_patterns):
                    files.append(path)
    return files

def load_failure_registry(root):
    """Merged failure registry — DevGate's bundled baseline PLUS the project's
    .guardrails/ overlay (the old pick-one-file resolution meant a game with
    its own registry silently lost every upstream entry, and vice versa).

    Merged by failure_id: an overlay entry replaces a same-id bundled entry
    (retune status/fields), new ids append. See gate_overlay.py.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import gate_overlay
    entries, _owner = gate_overlay.resolve_registry(root)
    return entries

def get_changed_files(root, staged=True):
    """Get list of changed files via git."""
    cmd = ["git", "diff", "--name-only", "--cached"] if staged else ["git", "diff", "--name-only"]
    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        return []
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]

def _split_rule(rule):
    """Normalize one rule to (regex, guard, window).

    A rule is a bare regex string, or a `(regex, guard, window)` tuple whose
    `guard` regex suppresses the hit when any of the next `window` lines
    matches it — the author checked the result, just on the following line.
    Bare strings stay valid so callers (and tests) can hand in ad-hoc tables.
    """
    if isinstance(rule, str):
        return rule, None, 0
    regex, guard, window = rule
    return regex, guard, int(window)


def _guarded(lines, index, guard, window):
    """True when the hit at `lines[index]` (0-based) has its guard nearby."""
    if not guard or window <= 0:
        return False
    return any(re.search(guard, follow) for follow in lines[index + 1:index + 1 + window])


def _is_comment_line(line):
    """True for a full-line comment in the languages this scanner reads.

    Only whole-line comments: a line whose first non-space characters are `#`
    or `//`. Trailing comments stay unscanned-as-code because a hit before them
    is real code; and nothing is stripped from inside strings, so a URL or a
    pattern quoted mid-line is unaffected. A comment cannot be a live defect —
    it is either documentation or code that was deliberately disabled — and
    this scanner's own docstrings describe the patterns it looks for, which
    otherwise makes it report itself (measured 2026-10-26: the only hit in
    DevGate's own tree was `scene_inventory.py` explaining `.connect("pressed")`
    in a comment).
    """
    stripped = line.lstrip()
    return stripped.startswith("#") or stripped.startswith("//")


def scan_file_for_patterns(file_path, patterns):
    """Scan a file for game-class regression patterns."""
    issues = []
    try:
        content = Path(file_path).read_text(errors="replace")
    except Exception:
        return issues

    lines = content.splitlines()
    for index, line in enumerate(lines):
        if _is_comment_line(line):
            continue
        for pattern_name, regexes in patterns.items():
            if line_has_allow(line, pattern_name):
                continue
            for rule in regexes:
                regex, guard, window = _split_rule(rule)
                if not re.search(regex, line):
                    continue
                if _guarded(lines, index, guard, window):
                    continue
                issues.append({
                    "file": file_path,
                    "line": index + 1,
                    "pattern": pattern_name,
                    "match": line.strip()[:120],
                })
    return issues

def scan_failure_registry_patterns(file_path, entries, root):
    """Check file against failure-registry regression_pattern regexes.

    Honors each entry's file_glob (basename OR relative path, matching the
    pattern-rules semantics) — without this a "*.go" entry is checked against
    docs and comments in unrelated files, over-reporting.
    """
    issues = []
    try:
        content = Path(file_path).read_text(errors="replace")
    except Exception:
        return issues

    try:
        rel = os.path.relpath(file_path, root)
    except ValueError:
        rel = str(file_path)
    for entry in entries:
        pattern = entry.get("regression_pattern")
        if not pattern:
            continue
        globs = entry.get("file_glob") or []
        if globs and not glob_matches(rel, globs):
            continue
        failure_id = entry.get("failure_id", "unknown")
        prevention_rule = entry.get("prevention_rule")
        try:
            for line_num, line in enumerate(content.splitlines(), 1):
                if _is_comment_line(line):
                    continue
                if line_has_allow(line, failure_id, prevention_rule):
                    continue
                if re.search(pattern, line):
                    issues.append({
                        "file": file_path,
                        "line": line_num,
                        "pattern": f"REGISTRY:{failure_id}",
                        "match": line.strip()[:120],
                    })
        except re.error:
            continue
    return issues

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Game-class regression scanner")
    parser.add_argument("--staged", action="store_true", help="Scan staged changes only")
    parser.add_argument("--unstaged", action="store_true", help="Scan unstaged changes")
    parser.add_argument("--all", action="store_true", help="Scan all source files")
    parser.add_argument("--pre-commit", action="store_true", help="Exit 1 on any hard violation")
    parser.add_argument("--fail-if-empty", action="store_true",
                        help="Exit 2 when the scope evaluated zero files (CI)")
    args = parser.parse_args()

    root = find_project_root()
    engine = detect_engine(root)
    print(f"[game-regression] project root: {root}")
    print(f"[game-regression] detected engine: {engine}")

    registry = load_failure_registry(root)
    print(f"[game-regression] failure registry: {len(registry)} entries")

    active_patterns = ENGINE_PATTERNS.get(engine, GAME_PATTERNS)

    ignore_patterns = load_ignore_patterns(root)
    if ignore_patterns:
        print(f"[game-regression] .guardrailsignore: {len(ignore_patterns)} entries")

    # zig-scope-01: the project may declare extra exclusions; they union with
    # the built-in defaults (a project adds, never removes).
    exclude_dirs, _non_screen = load_scan_config(root)
    if exclude_dirs:
        print(f"[game-regression] scan.exclude_dirs: {len(exclude_dirs)} declared")

    # Determine which files to scan
    if args.staged or args.unstaged:
        files = [str(root / f) for f in get_changed_files(root, staged=args.staged)]
    else:
        files = iter_source_files(root, ignore_patterns)
    files = [f for f in files if not is_ignored(f, root, ignore_patterns)]
    files = [
        f for f in files
        if not path_excludes_excluded_dir(
            os.path.relpath(f, str(root)), exclude_dirs)
    ]

    if not files:
        # No vacuous green (gate-execution-contract): zero files is NOTHING
        # SCANNED, never a clean pass. Default stays non-blocking for
        # non-game consumers; --fail-if-empty turns it into exit 2 for CI.
        sys.exit(nothing_scanned(
            "game-regression",
            "the scope evaluated zero files. This is not evidence of health.",
            fail_if_empty=args.fail_if_empty,
        ))

    print(f"[game-regression] scanning {len(files)} file(s)")
    all_issues = []

    for f in files:
        # Built-in game-class patterns (engine-selected)
        issues = scan_file_for_patterns(f, active_patterns)
        # Failure-registry patterns
        issues.extend(scan_failure_registry_patterns(f, registry, root))
        all_issues.extend(issues)

    if all_issues:
        print(f"\n[game-regression] {len(all_issues)} issue(s) found:")
        for issue in all_issues:
            print(f"  {issue['pattern']}: {issue['file']}:{issue['line']} — {issue['match']}")
    else:
        print(f"[game-regression] no issues found")

    print(f"\n=== Game Regression Summary ===")
    print(f"Files scanned: {len(files)}, Issues: {len(all_issues)}")

    if args.pre_commit and all_issues:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
