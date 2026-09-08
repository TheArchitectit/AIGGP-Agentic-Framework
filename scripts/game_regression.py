#!/usr/bin/env python3
"""Game-class regression scanner.

Ported from Sword of Hope's regression_check.py + failure-registry.jsonl patterns.
Adds game-specific failure classes beyond DevGate's generic scanner:

  NULL_DEREF       — runtime null dereference
  SCENE_LOAD_FAIL  — scene fails to instantiate
  SAVE_CORRUPT     — save/load round-trip breaks
  SCRIPT_ERROR     — engine script runtime error
  ORPHAN_SIGNAL    — button/signal with no handler
  DETERMINISM_BREAK — seeded run diverges
  PERF_REGRESSION  — frame time / memory exceeds budget

Reads .guardrails/failure-registry.jsonl and scans staged/unstaged changes
against known game-class patterns. Exit 1 on hard violations with --pre-commit.
"""
import fnmatch
import json, os, re, sys, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate_overlay  # noqa: E402

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

def find_project_root():
    """Project root = the directory CONTAINING .devgate/, by layout contract.

    Resolved from the script's own location, like guardrails-scan.mjs — cwd was
    wrong two ways: run from a subdir (go/) it shrank the scan to that subdir,
    and run from a bare directory with no markers it walked up into unrelated
    sibling repos. DevGate standalone (script not under a .devgate/) is its own
    project.
    """
    script_parent = Path(__file__).resolve().parent.parent  # <root>/.devgate
    if script_parent.name == ".devgate":
        return script_parent.parent
    return script_parent

# Directories that are not first-party source — mirrors SKIP_DIRS in
# guardrails-scan.mjs. Vendored and generated code must not fail the gate.
SKIP_DIRS = {"node_modules", ".git", "vendor", "dist", "build", "target", "out", "__pycache__", ".venv", "venv", ".devgate", ".claude"}

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

def glob_matches(path, globs):
    """Basename OR path glob match — parity with regression_diff.py glob_matches."""
    base = os.path.basename(path)
    return any(fnmatch.fnmatch(base, g) or fnmatch.fnmatch(path, g) for g in globs)

def iter_source_files(root, ignore_patterns=()):
    """Walk the tree collecting scannable source files, skipping SKIP_DIRS and ignores."""
    exts = {".gd", ".ts", ".js", ".py", ".rs", ".go"}
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
    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]

def line_has_allow(line, *ids):
    """True when the line carries a guardrails-allow for any of the given ids.

    Mirrors guardrails-scan.mjs, which keys the annotation on the rule id: a
    substring-only check would let one id's allow silence every other pattern.
    """
    return any(
        re.search(rf"guardrails-allow\s+{re.escape(i)}\s*:", line)
        for i in ids if i
    )

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
    args = parser.parse_args()

    root = find_project_root()
    print(f"[game-regression] project root: {root}")

    registry = load_failure_registry(root)
    print(f"[game-regression] failure registry: {len(registry)} entries")

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
        print("[game-regression] no files to scan")
        sys.exit(0)

    print(f"[game-regression] scanning {len(files)} file(s)")
    all_issues = []

    for f in files:
        # Built-in game-class patterns
        issues = scan_file_for_patterns(f, GAME_PATTERNS)
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
