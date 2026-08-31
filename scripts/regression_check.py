#!/usr/bin/env python3
"""
DevGate Regression Check Tool — language-agnostic.
Auto-detects the project root and scans whatever source directories exist.
Does NOT assume any specific language, package manager, or directory structure.

Usage:
    python scripts/regression_check.py              # Check staged changes
    python scripts/regression_check.py --unstaged     # Check unstaged changes
    python scripts/regression_check.py --all         # Check all changes
    python scripts/regression_check.py --pre-commit   # Exit non-zero if issues found

Environment Variables:
    FAILURE_REGISTRY_PATH: Path to registry file
    PREVENTION_RULES_PATH: Path to prevention rules directory
    DEVGATE_DB_PATH: Database connection string (if using schema health check)

Diff scanning semantics:
    Only ADDED lines ('+' lines of a unified diff) are scanned, so pre-existing
    legitimate code is never flagged — only new introductions. The diff parser is
    hunk-accurate: it tracks '+++' headers and '@@' hunk ranges so every finding
    reports the real (path, new_line_number) instead of an offset into a
    concatenated blob.

    Each failure-registry entry may carry a `regression_pattern` (a regex that
    must not reappear in added code) and an optional `file_glob` scoping it to
    matching files, so docs and helper scripts can quote a pattern without
    tripping the gate. The two files that DEFINE the patterns — the registry and
    pattern-rules.json — are excluded from the added-line scan, since every
    pattern trivially matches its own definition.
"""

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_REGISTRY_PATH = Path(".guardrails/failure-registry.jsonl")
DEFAULT_RULES_PATH = Path(".guardrails/prevention-rules")

# Hunk-accurate diff parsing + failure-registry pattern matching live in a
# sibling module (keeps both files under DevGate's own 500-line hard limit).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from regression_audit import (  # noqa: E402
    _detect_package_manager,
    check_npm_audit,
    print_npm_audit_report,
)
from regression_sizes import (  # noqa: E402
    SRC_HARD,
    SRC_SOFT,
    TEST_HARD,
    check_file_sizes,
    format_severity,
    print_file_size_report,
)
from regression_diff import (  # noqa: E402
    SCANNED_STATUSES,
    SELF_REFERENTIAL,
    check_added_against_registry,
    compile_registry_patterns,
    get_added_lines,
    glob_matches,
    load_active_failures,
    load_failure_registry,
    parse_diff,
)

# --- Auto-detect project root ------------------------------------------------
def find_project_root():
    """Walk up from CWD to find a project marker."""
    cwd = Path.cwd()
    markers = ["package.json", "Cargo.toml", "pyproject.toml", "setup.py",
               "go.mod", "project.godot", ".git"]
    for d in [cwd] + list(cwd.parents):
        for m in markers:
            if (d / m).exists():
                return d
    return cwd

PROJECT_ROOT = find_project_root()

# --- Source directories to scan (auto-detect what exists) -------------------
SOURCE_DIRS = []
for candidate in ["src", "lib", "app", "extensions", "scripts", "internal", "pkg", "cmd", "game"]:
    if (PROJECT_ROOT / candidate).is_dir():
        SOURCE_DIRS.append(candidate)

# If no standard dirs found, scan the project root itself
if not SOURCE_DIRS:
    SOURCE_DIRS = ["."]



# --- Git / failure registry / pattern rules (unchanged logic) ---------------

def run_git_command(args: list[str]) -> tuple[int, str, str]:
    try:
        result = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 1, "", "git command not found"


def get_changed_files(staged: bool = True, unstaged: bool = False) -> list[str]:
    files = []
    if staged:
        rc, stdout, _ = run_git_command(["diff", "--cached", "--name-only"])
        if rc == 0:
            files.extend(stdout.strip().split("\n") if stdout.strip() else [])
    if unstaged:
        rc, stdout, _ = run_git_command(["diff", "--name-only"])
        if rc == 0:
            files.extend(stdout.strip().split("\n") if stdout.strip() else [])
    return list({f for f in files if f})


def get_diff_content(file_path: str, staged: bool = True) -> str:
    cmd = ["diff", "--cached"] if staged else ["diff"]
    rc, stdout, _ = run_git_command(cmd + ["--", file_path])
    return stdout if rc in (0, 1) else ""



def print_registry_regression_report(violations: list[dict]) -> None:
    """Report re-added failure-registry patterns with real file:line locations."""
    if not violations:
        return
    print("\n" + "=" * 70)
    print("FAILURE-REGISTRY REGRESSION (a known bug's pattern was re-added)")
    print("=" * 70)
    for v in violations:
        print(f"\n  🚫 {format_severity(v['severity'])} - {v['failure_id']} "
              f"at {v['file']}:{v['line']}")
        if v["error_message"]:
            print(f"      Original failure: {v['error_message'][:100]}")
        if v["prevention_rule"]:
            print(f"      Prevention: {v['prevention_rule']}")
        print(f"      Matched pattern: {v['pattern']}")
        print(f"      Added line: {v['added']}")
    print("-" * 70)
    print(f"  {len(violations)} registry regression(s)")
    print("=" * 70)


def validate_rule_regex(rule: dict) -> bool:
    pattern = rule.get("pattern", "")
    if pattern:
        try:
            re.compile(pattern)
        except re.error as e:
            print(f"Warning: Invalid regex in rule {rule.get('rule_id')}: {e}")
            return False
    forbidden = rule.get("forbidden_context", "")
    if forbidden:
        try:
            re.compile(forbidden)
        except re.error as e:
            print(f"Warning: Invalid forbidden_context in rule {rule.get('rule_id')}: {e}")
            return False
    return True


def load_prevention_rules(rules_path: Path) -> list[dict]:
    rules = []
    pattern_rules_file = rules_path / "pattern-rules.json"
    if pattern_rules_file.exists():
        try:
            with open(pattern_rules_file) as f:
                data = json.load(f)
                for rule in data.get("rules", []):
                    if rule.get("enabled", True) and validate_rule_regex(rule):
                        rule["rule_type"] = "pattern"
                        rules.append(rule)
        except (OSError, json.JSONDecodeError):
            pass
    semantic_rules_file = rules_path / "semantic-rules.json"
    if semantic_rules_file.exists():
        try:
            with open(semantic_rules_file) as f:
                data = json.load(f)
                for rule in data.get("rules", []):
                    if rule.get("enabled", True):
                        rule["rule_type"] = "semantic"
                        rules.append(rule)
        except (OSError, json.JSONDecodeError):
            pass
    return rules


def check_file_against_failures(file_path: str, failures: list[dict]) -> list[dict]:
    matching_failures = []
    for failure in failures:
        affected_files = failure.get("affected_files", [])
        for affected in affected_files:
            if fnmatch.fnmatch(file_path, affected):
                matching_failures.append(failure)
                break
    return matching_failures


def rules_for_file(rules: list[dict], file_path: str) -> list[dict]:
    """Scope rules to the file via their optional file_glob (full-path OR
    basename match); empty/missing glob = every file. Without this, a
    glob-scoped rule like PREVENT-027 (pattern ".*", file_glob
    ["Dockerfile"]) fires on every changed file's diff."""
    scoped = []
    for rule in rules:
        globs = rule.get("file_glob") or []
        if globs and not any(
            fnmatch.fnmatch(file_path, g) or fnmatch.fnmatch(os.path.basename(file_path), g)
            for g in globs
        ):
            continue
        scoped.append(rule)
    return scoped


def check_diff_against_patterns(diff_content: str, rules: list[dict]) -> list[dict]:
    violations = []
    added_lines = []
    for line in diff_content.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:])
    added_content = "\n".join(added_lines)
    for rule in rules:
        if rule.get("rule_type") != "pattern":
            continue
        pattern = rule.get("pattern")
        if not pattern:
            continue
        try:
            if re.search(pattern, added_content, re.MULTILINE):
                forbidden = rule.get("forbidden_context")
                if forbidden and re.search(forbidden, added_content, re.MULTILINE):
                    continue
                violations.append({"rule_id": rule.get("rule_id"), "name": rule.get("name"),
                                  "message": rule.get("message"), "severity": rule.get("severity", "warning"),
                                  "suggestion": rule.get("suggestion"), "failure_id": rule.get("failure_id")})
        except re.error:
            continue
    return violations


def run_regression_check(registry_path: Path, rules_path: Path, staged: bool = True,
                         unstaged: bool = False, verbose: bool = False) -> tuple[int, list[dict]]:
    issues = []
    failures = load_active_failures(load_failure_registry(registry_path))
    rules = load_prevention_rules(rules_path)
    changed_files = get_changed_files(staged=staged, unstaged=unstaged)
    if not changed_files:
        if verbose:
            print("No changed files to check")
        return 0, []
    for file_path in changed_files:
        file_issues = {"file": file_path, "failures": [], "violations": []}
        matching_failures = check_file_against_failures(file_path, failures)
        if matching_failures:
            file_issues["failures"] = matching_failures
        diff = get_diff_content(file_path, staged=staged)
        if diff:
            violations = check_diff_against_patterns(diff, rules_for_file(rules, file_path))
            if violations:
                file_issues["violations"] = violations
        if file_issues["failures"] or file_issues["violations"]:
            # info-severity findings are advisory: they report, they do not
            # block the pre-commit gate (an info rule like PREVENT-027
            # "missing .dockerignore" must not hard-fail an unrelated repo)
            file_issues["blocking"] = bool(
                file_issues["failures"]
                or any(v.get("severity", "warning").lower() != "info"
                       for v in file_issues["violations"]))
            issues.append(file_issues)
    return len(issues), issues


def print_report(issues: list[dict], verbose: bool = False):
    if not issues:
        print("\n✓ No potential regressions detected")
        return
    print("\n" + "=" * 70)
    print("REGRESSION CHECK REPORT")
    print("=" * 70)
    for issue in issues:
        file_path = issue["file"]
        print(f"\n📄 {file_path}")
        print("-" * 70)
        for failure in issue["failures"]:
            severity = format_severity(failure.get("severity", "medium"))
            print(f"\n  ⚠️  {severity} - Known Bug History")
            print(f"      Failure ID: {failure.get('failure_id', 'N/A')}")
            print(f"      Category: {failure.get('category', 'unknown')}")
            print(f"      Previous Error: {failure.get('error_message', 'N/A')[:80]}...")
            print(f"      Prevention: {failure.get('prevention_rule', 'N/A')}")
        for violation in issue["violations"]:
            severity = format_severity(violation.get("severity", "warning"))
            print(f"\n  🚫 {severity} - Pattern Violation")
            print(f"      Rule: {violation.get('name', 'Unknown')}")
            print(f"      Message: {violation.get('message', 'N/A')}")
            if violation.get("failure_id"):
                print(f"      Related Failure: {violation['failure_id']}")
            if violation.get("suggestion"):
                print(f"      Suggestion: {violation['suggestion']}")
    print("\n" + "=" * 70)
    print(f"Total files with potential issues: {len(issues)}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Check for potential regressions in changed code",
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    # Resolve .devgate-relative paths if running from project root
    devgate_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--registry", "-r", type=Path,
                        default=Path(os.getenv("FAILURE_REGISTRY_PATH", devgate_root / ".guardrails" / "failure-registry.jsonl")))
    parser.add_argument("--rules", type=Path,
                        default=Path(os.getenv("PREVENTION_RULES_PATH", devgate_root / ".guardrails" / "prevention-rules")))
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--staged", action="store_true", default=True)
    group.add_argument("--unstaged", "-u", action="store_true")
    group.add_argument("--all", "-a", action="store_true")
    parser.add_argument("--pre-commit", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-file-sizes", action="store_true")
    parser.add_argument("--no-audit", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--quiet", "-q", action="store_true")
    parser.add_argument("--soft-as-hard", action="store_true")
    parser.add_argument("--soft-as-hard-base", default=None)
    args = parser.parse_args()

    staged = args.staged and not args.unstaged and not args.all
    unstaged = args.unstaged or args.all
    if args.all:
        staged = True

    count, issues = run_regression_check(registry_path=args.registry, rules_path=args.rules,
                                         staged=staged, unstaged=unstaged,
                                         verbose=args.verbose and not args.quiet)

    # Hunk-accurate ADDED lines drive the registry regression scan and tell the
    # file-size check which files this diff actually touches.
    added = get_added_lines(run_git_command, staged=staged, unstaged=unstaged,
                            all_scope=args.all)
    touched = {path for path, _, _ in added}

    all_entries = load_failure_registry(args.registry)
    compiled, pattern_warnings = compile_registry_patterns(all_entries)
    registry_violations = check_added_against_registry(added, compiled)

    size_issues: list[dict] = []
    size_hard_count = 0
    if not args.no_file_sizes:
        size_issues = check_file_sizes(PROJECT_ROOT, SOURCE_DIRS, touched=touched)
        size_hard_count = sum(1 for i in size_issues if i["kind"] == "hard")

    soft_as_hard_count = 0
    soft_as_hard_files: list[dict] = []
    if args.soft_as_hard and not args.no_file_sizes:
        if args.soft_as_hard_base:
            rc, stdout, _ = run_git_command(["diff", "--name-only", f"{args.soft_as_hard_base}...HEAD"])
            changed: set[str] = set()
            if rc == 0 and stdout.strip():
                changed.update(stdout.strip().split("\n"))
            changed.update(get_changed_files(staged=True, unstaged=True))
        else:
            changed = set(get_changed_files(staged=True, unstaged=True))
        for issue in size_issues:
            if issue["kind"] != "soft":
                continue
            rel = issue["file"]
            if rel in changed or rel.replace("/", os.sep) in changed:
                soft_as_hard_count += 1
                soft_as_hard_files.append(issue)

    audit_blocking = 0
    audit_warnings = 0
    audit_issues: list[dict] = []
    if not args.no_audit:
        audit_blocking, audit_warnings, audit_issues = check_npm_audit(PROJECT_ROOT)

    if args.json:
        print(json.dumps({"issue_count": count, "size_violations_hard": size_hard_count,
                           "soft_as_hard_blocked": soft_as_hard_count,
                           "audit_blocking": audit_blocking, "audit_warnings": audit_warnings,
                           "registry_regressions": len(registry_violations),
                           "issues": issues, "file_sizes": size_issues, "audit": audit_issues,
                           "registry_violations": registry_violations,
                           "registry_pattern_warnings": pattern_warnings}, indent=2))
    else:
        for warn in pattern_warnings:
            print(f"Warning: {warn}")
        if not args.quiet or count > 0:
            print_report(issues, verbose=args.verbose)
        print_registry_regression_report(registry_violations)
        if size_issues and (not args.quiet or size_hard_count > 0):
            print_file_size_report(size_issues)
        if not args.no_audit and (not args.quiet or audit_blocking > 0):
            print_npm_audit_report(audit_blocking, audit_warnings, audit_issues)
        if args.soft_as_hard and soft_as_hard_count > 0:
            print("\n" + "=" * 70)
            print("SOFT-AS-HARD HEADROOM GATE (--soft-as-hard)")
            print("=" * 70)
            print("  These changed files exceeded the SOFT limit — split them:")
            for issue in soft_as_hard_files:
                print(f"    {issue['file']}  ({issue['lines']} lines, soft {issue['soft']})")
            print("=" * 70)

    blocking = sum(1 for issue in issues if issue.get("blocking"))
    if args.pre_commit and (blocking > 0 or size_hard_count > 0 or soft_as_hard_count > 0
                            or audit_blocking > 0 or registry_violations):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
