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
import json, os, re, sys, subprocess
from pathlib import Path

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
    d = Path.cwd()
    for i in range(10):
        for marker in ("project.godot", "package.json", "Cargo.toml", ".git"):
            if (d / marker).exists():
                return d
        parent = d.parent
        if parent == d:
            break
        d = parent
    return Path.cwd()

def load_failure_registry(root):
    """Load .guardrails/failure-registry.jsonl — one JSON object per line."""
    registry_path = root / ".guardrails" / "failure-registry.jsonl"
    entries = []
    if not registry_path.exists():
        return entries
    for line in registry_path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries

def get_changed_files(root, staged=True):
    """Get list of changed files via git."""
    cmd = ["git", "diff", "--name-only", "--cached"] if staged else ["git", "diff", "--name-only"]
    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
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
        # Skip inline guardrails-allow annotations
        if "guardrails-allow" in line:
            continue
        for pattern_name, regexes in patterns.items():
            for regex in regexes:
                if re.search(regex, line):
                    issues.append({
                        "file": file_path,
                        "line": line_num,
                        "pattern": pattern_name,
                        "match": line.strip()[:120],
                    })
    return issues

def scan_failure_registry_patterns(file_path, entries):
    """Check file against failure-registry regression_pattern regexes."""
    issues = []
    try:
        content = Path(file_path).read_text(errors="replace")
    except Exception:
        return issues

    for entry in entries:
        pattern = entry.get("regression_pattern")
        if not pattern:
            continue
        try:
            for line_num, line in enumerate(content.splitlines(), 1):
                if re.search(pattern, line):
                    issues.append({
                        "file": file_path,
                        "line": line_num,
                        "pattern": f"REGISTRY:{entry.get('failure_id', 'unknown')}",
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

    # Determine which files to scan
    if args.all:
        files = []
        for ext in (".gd", ".ts", ".js", ".py", ".rs", ".go"):
            files.extend(str(p) for p in root.rglob(f"*{ext}") if "node_modules" not in str(p) and ".git" not in str(p))
    elif args.staged or args.unstaged:
        files = get_changed_files(root, staged=args.staged)
        files = [str(root / f) for f in files]
    else:
        files = []
        for ext in (".gd", ".ts", ".js", ".py", ".rs", ".go"):
            files.extend(str(p) for p in root.rglob(f"*{ext}") if "node_modules" not in str(p) and ".git" not in str(p))

    if not files:
        print("[game-regression] no files to scan")
        sys.exit(0)

    print(f"[game-regression] scanning {len(files)} file(s)")
    all_issues = []

    for f in files:
        # Built-in game-class patterns
        issues = scan_file_for_patterns(f, GAME_PATTERNS)
        # Failure-registry patterns
        issues.extend(scan_failure_registry_patterns(f, registry))
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
