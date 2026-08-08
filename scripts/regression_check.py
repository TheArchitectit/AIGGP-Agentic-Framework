#!/usr/bin/env python3
"""
DevGate Regression Check Tool
Language-agnostic scanner for potential regressions in changed code.

Usage:
    python scripts/regression_check.py              # Check staged changes
    python scripts/regression_check.py --unstaged     # Check unstaged changes
    python scripts/regression_check.py --all         # Check all changes
    python scripts/regression_check.py --pre-commit   # Exit non-zero if issues found

Environment Variables:
    FAILURE_REGISTRY_PATH: Path to registry file
    PREVENTION_RULES_PATH: Path to prevention rules directory
"""

import argparse
import contextlib
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_REGISTRY_PATH = Path(".guardrails/failure-registry.jsonl")
DEFAULT_RULES_PATH = Path(".guardrails/prevention-rules")

# File-size limits — configurable per directory and language.
# src/ 300 soft / 500 hard; extensions/ 400 soft / 500 hard; tests/ 600 hard.
FILE_SIZE_DIRS = ("src", "extensions")
FILE_SIZE_SKIP_PARTS = ("node_modules", "dist", ".claude", "target", "__pycache__", "worktrees")
FILE_SIZE_SKIP_SUFFIXES = (".d.ts",)
SRC_SOFT = 300
SRC_HARD = 500
EXT_SOFT = 400
EXT_HARD = 500
TEST_HARD = 600

# Python source directories (if you have Python source alongside TS)
PY_DIRS = ("src", "scripts")
PY_HARD = 600


def _classify_file(rel_path: str) -> tuple[int | None, int | None]:
    """Return (soft, hard) line limits for a repo-relative path."""
    parts = rel_path.split(os.sep)
    for skip in FILE_SIZE_SKIP_PARTS:
        if skip in parts:
            return (None, None)
    for suf in FILE_SIZE_SKIP_SUFFIXES:
        if rel_path.endswith(suf):
            return (None, None)
    is_test = rel_path.endswith((".test.ts", ".test.tsx", "_test.py", ".test.js"))
    if rel_path.startswith("extensions" + os.sep):
        return (EXT_SOFT, TEST_HARD if is_test else EXT_HARD)
    if rel_path.startswith("src" + os.sep):
        return (SRC_SOFT, TEST_HARD if is_test else SRC_HARD)
    if rel_path.startswith("scripts" + os.sep) and rel_path.endswith(".py"):
        return (None, PY_HARD)
    return (None, None)


def check_file_sizes(repo_root: Path) -> list[dict]:
    violations: list[dict] = []
    warnings: list[dict] = []

    def _size_file(abs_path: Path, rel_path: str) -> None:
        soft, hard = _classify_file(rel_path)
        if hard is None:
            return
        try:
            with open(abs_path, encoding="utf-8", errors="replace") as f:
                line_count = sum(1 for _ in f)
        except OSError:
            return
        if line_count > hard:
            violations.append({"file": rel_path, "lines": line_count, "soft": soft, "hard": hard, "severity": "error", "kind": "hard"})
        elif soft is not None and line_count > soft:
            warnings.append({"file": rel_path, "lines": line_count, "soft": soft, "hard": hard, "severity": "warning", "kind": "soft"})

    for top in FILE_SIZE_DIRS:
        base = repo_root / top
        if not base.is_dir():
            continue
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in filenames:
                if not (name.endswith((".ts", ".tsx", ".py", ".rs", ".go", ".gd", ".java", ".kt"))):
                    continue
                abs_path = Path(dirpath) / name
                try:
                    rel_path = abs_path.relative_to(repo_root).as_posix()
                except ValueError:
                    continue
                _size_file(abs_path, rel_path)

    violations.sort(key=lambda d: d["lines"], reverse=True)
    warnings.sort(key=lambda d: d["lines"], reverse=True)
    return violations + warnings


def print_file_size_report(size_issues: list[dict]) -> None:
    if not size_issues:
        print("✓ All source files within soft/hard line limits")
        return
    hard_count = sum(1 for i in size_issues if i["kind"] == "hard")
    soft_count = sum(1 for i in size_issues if i["kind"] == "soft")
    print("\n" + "=" * 70)
    print("FILE-SIZE CHECK")
    print("=" * 70)
    for issue in size_issues:
        severity = format_severity(issue["severity"])
        tag = "OVER HARD LIMIT" if issue["kind"] == "hard" else "over soft limit"
        print(f"  {severity}  {issue['file']}  ({issue['lines']} lines, limit {issue['hard'] if issue['kind'] == 'hard' else issue['soft']})  {tag}")
    print("-" * 70)
    print(f"  {hard_count} over hard limit (blocks commit), {soft_count} over soft limit (warning)")
    print("=" * 70)


def _npm_audit_available() -> bool:
    try:
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_npm_audit(repo_root: Path) -> tuple[int, int, list[dict]]:
    if not _npm_audit_available():
        return (0, 0, [])  # Non-blocking if npm not present
    try:
        result = subprocess.run(["npm", "audit", "--json"], capture_output=True, text=True, cwd=str(repo_root), timeout=120)
    except subprocess.TimeoutExpired:
        return (1, 0, [{"name": "(npm)", "severity": "critical", "is_runtime": True, "advisory": "npm audit timed out", "fix_available": False, "effects": []}])
    raw = result.stdout.strip()
    if not raw:
        return (0, 0, [])
    try:
        audit = json.loads(raw)
    except json.JSONDecodeError:
        return (1, 0, [{"name": "(npm)", "severity": "critical", "is_runtime": True, "advisory": "npm audit JSON unparseable", "fix_available": False, "effects": []}])

    pkg_path = repo_root / "package.json"
    runtime_deps: set[str] | None = set()
    try:
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        runtime_deps = set((pkg.get("dependencies") or {}).keys())
    except (OSError, json.JSONDecodeError):
        runtime_deps = None

    vuln_map = audit.get("vulnerabilities") or {}
    issues: list[dict] = []
    for name, info in vuln_map.items():
        severity = str(info.get("severity", "unknown")).lower()
        effects = info.get("effects") or []
        is_runtime = any(eff in (runtime_deps or set()) for eff in effects) if runtime_deps is not None else True
        issues.append({"name": name, "severity": severity, "is_runtime": is_runtime, "advisory": str(info.get("via", ""))[:80], "fix_available": bool(info.get("fixAvailable")), "effects": effects})
    blocking = [i for i in issues if i["is_runtime"] and i["severity"] in ("high", "critical")]
    warning = [i for i in issues if not (i["is_runtime"] and i["severity"] in ("high", "critical"))]
    return len(blocking), len(warning), issues


def print_npm_audit_report(blocking: int, warnings: int, issues: list[dict]) -> None:
    if not issues:
        print("✓ npm audit clean — no vulnerabilities")
        return
    print("\n" + "=" * 70)
    print("NPM AUDIT (runtime HIGH/CRITICAL = blocking; dev-only = warning)")
    print("=" * 70)
    for i in sorted(issues, key=lambda x: (not x["is_runtime"], x["severity"])):
        scope = "RUNTIME" if i["is_runtime"] else "dev-only"
        fix = "fix available" if i["fix_available"] else "NO fix"
        print(f"  {i['severity'].upper():8s} {scope:8s} {i['name']:<32s} {fix}")
    print("-" * 70)
    print(f"  {blocking} blocking | {warnings} warning(s)")
    print("=" * 70)


def run_git_command(args: list[str]) -> tuple[int, str, str]:
    try:
        result = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=Path.cwd())
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


def load_failure_registry(registry_path: Path) -> list[dict]:
    if not registry_path.exists():
        return []
    entries = []
    with open(registry_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    entry = json.loads(line)
                    if entry.get("status") == "active":
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
    return entries


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
                violations.append({"rule_id": rule.get("rule_id"), "name": rule.get("name"), "message": rule.get("message"), "severity": rule.get("severity", "warning"), "suggestion": rule.get("suggestion"), "failure_id": rule.get("failure_id")})
        except re.error:
            continue
    return violations


def format_severity(severity: str) -> str:
    colors = {"critical": "\033[91m", "high": "\033[93m", "medium": "\033[94m", "low": "\033[90m", "error": "\033[91m", "warning": "\033[93m"}
    reset = "\033[0m"
    if sys.stdout.isatty():
        return f"{colors.get(severity.lower(), '')}{severity.upper()}{reset}"
    return severity.upper()


def run_regression_check(registry_path: Path, rules_path: Path, staged: bool = True, unstaged: bool = False, verbose: bool = False) -> tuple[int, list[dict]]:
    issues = []
    failures = load_failure_registry(registry_path)
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
            violations = check_diff_against_patterns(diff, rules)
            if violations:
                file_issues["violations"] = violations
        if file_issues["failures"] or file_issues["violations"]:
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
    parser = argparse.ArgumentParser(description="Check for potential regressions in changed code", formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", "-r", type=Path, default=Path(os.getenv("FAILURE_REGISTRY_PATH", DEFAULT_REGISTRY_PATH)))
    parser.add_argument("--rules", type=Path, default=Path(os.getenv("PREVENTION_RULES_PATH", DEFAULT_RULES_PATH)))
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

    count, issues = run_regression_check(registry_path=args.registry, rules_path=args.rules, staged=staged, unstaged=unstaged, verbose=args.verbose and not args.quiet)

    size_issues: list[dict] = []
    size_hard_count = 0
    if not args.no_file_sizes:
        size_issues = check_file_sizes(Path.cwd())
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
        audit_blocking, audit_warnings, audit_issues = check_npm_audit(Path.cwd())

    if args.json:
        print(json.dumps({"issue_count": count, "size_violations_hard": size_hard_count, "soft_as_hard_blocked": soft_as_hard_count, "npm_audit_blocking": audit_blocking, "npm_audit_warnings": audit_warnings, "issues": issues, "file_sizes": size_issues, "npm_audit": audit_issues}, indent=2))
    else:
        if not args.quiet or count > 0:
            print_report(issues, verbose=args.verbose)
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

    if args.pre_commit and (count > 0 or size_hard_count > 0 or soft_as_hard_count > 0 or audit_blocking > 0):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
