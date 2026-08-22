#!/usr/bin/env python3
"""regression_sizes.py — file-size limits + severity formatting.

Helper module for scripts/regression_check.py, split out to keep every file
under DevGate's own 500-line hard limit (this gate must pass its own check).
Language-agnostic: limits apply to whatever source extensions exist in whatever
source directories the project happens to have.

Configure the limits here:

    SRC_SOFT = 300    # soft limit (lines) — warning
    SRC_HARD = 500    # hard limit (lines) — blocks commit
    TEST_HARD = 600   # test files hard limit

Hard-limit breaches are classified by whether the diff under review TOUCHES the
file: touched files are blocking errors (new and modified code must obey the
limit), while pre-existing oversize files the diff never touched stay warnings,
so legacy debt cannot block an unrelated release.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

FILE_SIZE_SKIP_PARTS = ("node_modules", "dist", ".claude", "target", "__pycache__",
                        ".devgate", "vendor", "build", "out", ".next", ".nuxt",
                        "venv", ".venv", "worktrees", "egg-info")
FILE_SIZE_SKIP_SUFFIXES = (".d.ts", ".min.js", ".min.mjs", ".map")

# File-size limits — configurable. These apply to ALL source file types.
SRC_SOFT = 300
SRC_HARD = 500
TEST_HARD = 600

# Source file extensions to check (language-agnostic)
SOURCE_EXTENSIONS = (".ts", ".tsx", ".py", ".rs", ".go", ".gd", ".java", ".kt",
                     ".rb", ".php", ".js", ".jsx", ".swift", ".c", ".cpp", ".h", ".cs")


def format_severity(severity: str) -> str:
    """Colourize a severity label when stdout is a TTY."""
    colors = {"critical": "\033[91m", "high": "\033[93m", "medium": "\033[94m",
              "low": "\033[90m", "error": "\033[91m", "warning": "\033[93m"}
    reset = "\033[0m"
    if sys.stdout.isatty():
        return f"{colors.get(severity.lower(), '')}{severity.upper()}{reset}"
    return severity.upper()


def _classify_file(rel_path: str) -> tuple[int | None, int | None]:
    """Return (soft, hard) line limits for a repo-relative path."""
    parts = rel_path.split(os.sep)
    for skip in FILE_SIZE_SKIP_PARTS:
        if skip in parts:
            return (None, None)
    for suf in FILE_SIZE_SKIP_SUFFIXES:
        if rel_path.endswith(suf):
            return (None, None)
    is_test = rel_path.endswith((".test.ts", ".test.tsx", ".test.js", ".spec.ts",
                                 ".spec.js", "_test.py", "test_*.py", "_test.go",
                                 ".test.rs", ".test.gd"))
    if is_test:
        return (None, TEST_HARD)
    return (SRC_SOFT, SRC_HARD)


def check_file_sizes(repo_root: Path, source_dirs: list[str],
                     touched: set[str] | None = None) -> list[dict]:
    """Size every source file; classify hard-limit breaches by touched-ness.

    A file OVER the hard limit that this diff actually touches is an ERROR
    (kind='hard'). A pre-existing oversize file the diff never touched stays a
    WARNING (kind='hard-untouched'). Passing touched=None preserves the original
    behaviour of treating every breach as blocking.
    """
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
            edited = (touched is None
                      or rel_path in touched
                      or rel_path.replace("/", os.sep) in touched)
            if edited:
                violations.append({"file": rel_path, "lines": line_count, "soft": soft,
                                   "hard": hard, "severity": "error", "kind": "hard"})
            else:
                warnings.append({"file": rel_path, "lines": line_count, "soft": soft,
                                 "hard": hard, "severity": "warning",
                                 "kind": "hard-untouched"})
        elif soft is not None and line_count > soft:
            warnings.append({"file": rel_path, "lines": line_count, "soft": soft,
                             "hard": hard, "severity": "warning", "kind": "soft"})

    for top in source_dirs:
        base = repo_root / top
        if not base.is_dir():
            continue
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in filenames:
                if not name.endswith(SOURCE_EXTENSIONS):
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
    untouched_count = sum(1 for i in size_issues if i["kind"] == "hard-untouched")
    soft_count = sum(1 for i in size_issues if i["kind"] == "soft")
    print("\n" + "=" * 70)
    print("FILE-SIZE CHECK")
    print("=" * 70)
    for issue in size_issues:
        severity = format_severity(issue["severity"])
        if issue["kind"] == "hard":
            tag = "OVER HARD LIMIT"
            limit = issue["hard"]
        elif issue["kind"] == "hard-untouched":
            tag = "over hard limit (pre-existing; not touched by this diff)"
            limit = issue["hard"]
        else:
            tag = "over soft limit"
            limit = issue["soft"]
        print(f"  {severity}  {issue['file']}  ({issue['lines']} lines, "
              f"limit {limit})  {tag}")
    print("-" * 70)
    print(f"  {hard_count} over hard limit (blocks commit), "
          f"{untouched_count} pre-existing oversize (warning), "
          f"{soft_count} over soft limit (warning)")
    print("=" * 70)
