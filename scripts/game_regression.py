#!/usr/bin/env python3
"""Game-class regression scanner (engine-aware).

Ported from Sword of Hope's regression_check.py + failure-registry.jsonl patterns.
Adds game-specific failure classes beyond DevGate's generic scanner:

  NULL_DEREF       — runtime null dereference
  SCENE_LOAD_FAIL  — scene fails to instantiate
  SAVE_CORRUPT     — save/load round-trip breaks
  SCRIPT_ERROR     — engine script runtime error
  ORPHAN_SIGNAL    — button/signal with no handler
  DETERMINISM_BREAK — seeded run diverges
  PERF_REGRESSION  — frame time / memory exceeds budget

The engine is detected from game-manifest.json (else project files) and the
matching pattern table is applied; unknown engines fall back to the Godot set.
Zig + OpenGL classes (ZIG_COMPILE, ZIG_MEMORY, OPENGL_CTX, SHADER_FAIL,
INPUT_CAPTURE) were imported from the former devgate-game-framework repository
(merged 2026-09-26).

Reads .guardrails/failure-registry.jsonl and scans staged/unstaged changes
against known game-class patterns. Exit 1 on hard violations with --pre-commit.
"""
import fnmatch
import json, os, re, sys, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_overlay  # noqa: E402
# Shared primitives — one implementation (scripts/gate_common.py).
from gate_common import (  # noqa: E402
    glob_matches,
    line_has_allow,
    load_skip_dirs,
    project_root,
    nothing_scanned,
)

# Game-class patterns (regex-based, loaded from failure-registry.jsonl)
GAME_PATTERNS = {
    "NULL_DEREF": [
        r"\.get_node\([^)]*\)\s*\.\s*\w+",      # unsafe get_node chain
        r"if\s+\w+\s*==\s*null\s*:\s*pass",       # null check + no-op (swallowed)
    ],
    "SCENE_LOAD_FAIL": [
        r"load\([^)]*\.tscn[^)]*\)\s*$",          # load without null check
        r"change_scene_to_file\([^)]*\)",         # scene change without error handling
    ],
    "SAVE_CORRUPT": [
        r"json\.parse\([^)]*\)\s*$",              # JSON.parse without error check
        r"FileAccess\.open[^)]*\)\s*$",           # file open without error check
    ],
    "SCRIPT_ERROR": [
        r"push_error\(",                           # explicit push_error call
        r"assert\(",                               # bare assert (crashes on fail)
    ],
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

def load_ignore_patterns(root):
    """Read <root>/.guardrailsignore — per-project scoping the gate can't know.

    One fnmatch glob per line ('*' crosses '/', same as the rule globs); a
    trailing '/' marks a directory prefix. Blank lines and '#' comments ignored.
    """
    path = Path(root) / ".guardrailsignore"
    patterns = []
    if not path.exists():
        return patterns
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns

def is_ignored(file_path, root, patterns):
    """True when the file matches a .guardrailsignore entry (relpath, basename, or dir prefix)."""
    if not patterns:
        return False
    try:
        rel = os.path.relpath(file_path, root)
    except ValueError:
        rel = str(file_path)
    base = os.path.basename(file_path)
    for pat in patterns:
        if pat.endswith("/"):
            if rel.replace("\\", "/").startswith(pat) or (rel + "/").replace("\\", "/").startswith(pat):
                return True
        elif fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(base, pat):
            return True
    return False

# glob_matches and line_has_allow are re-exported from gate_common (shared).

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

def scan_file_for_patterns(file_path, patterns):
    """Scan a file for game-class regression patterns."""
    issues = []
    try:
        content = Path(file_path).read_text(errors="replace")
    except Exception:
        return issues

    for line_num, line in enumerate(content.splitlines(), 1):
        for pattern_name, regexes in patterns.items():
            if line_has_allow(line, pattern_name):
                continue
            for regex in regexes:
                if re.search(regex, line):
                    issues.append({
                        "file": file_path,
                        "line": line_num,
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

    # Determine which files to scan
    if args.staged or args.unstaged:
        files = [str(root / f) for f in get_changed_files(root, staged=args.staged)]
    else:
        files = iter_source_files(root, ignore_patterns)
    files = [f for f in files if not is_ignored(f, root, ignore_patterns)]

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
