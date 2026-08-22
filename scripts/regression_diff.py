#!/usr/bin/env python3
"""regression_diff.py — hunk-accurate diff parsing + failure-registry matching.

Helper module for scripts/regression_check.py, split out to keep both files
under DevGate's own 500-line hard limit. Language-agnostic: nothing here assumes
a language, package manager, or directory layout.

What lives here:

  * parse_diff / get_added_lines — extract ADDED lines from a unified diff as
    (path, new_line_number, text). Hunk-accurate, so findings report the REAL
    line number rather than an offset into a concatenated blob.
  * compile_registry_patterns / check_added_against_registry — compile each
    failure-registry entry's `regression_pattern` and match it against added
    lines, honouring the entry's optional `file_glob` scoping. DevGate has
    always STORED regression_pattern; this is what reads it.
  * load_failure_registry / load_active_failures — registry loading split by
    status: patterns are enforced for active AND resolved entries (a resolved
    bug is exactly the one that must not come back), while the affected-files
    advisory stays active-only.

Only ADDED lines are ever scanned, so pre-existing legitimate code is never
flagged — only new introductions.
"""

from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path

# Files that DEFINE the regression patterns. Scanning their own added lines
# would self-match every pattern they declare, so they are skipped.
SELF_REFERENTIAL = (
    ".guardrails/failure-registry.jsonl",
    ".guardrails/prevention-rules/pattern-rules.json",
)

# Registry statuses whose regression_pattern is compiled and enforced.
SCANNED_STATUSES = ("active", "resolved")


def parse_diff(diff: str) -> list[tuple[str, int, str]]:
    """Extract ADDED lines from a unified diff as (path, new_line_number, text).

    Hunk-accurate: '+++' headers set the current file and '@@' headers reset the
    new-file line counter, so a violation is reported at its REAL line number
    instead of an offset into a concatenated blob. Context lines advance the
    counter; removed lines do not (they don't exist in the new file).
    """
    added: list[tuple[str, int, str]] = []
    path = ""
    lineno = 0
    for raw in diff.split("\n"):
        if raw.startswith("+++ "):
            target = raw[4:].strip()
            path = "" if target == "/dev/null" else re.sub(r"^b/", "", target)
            continue
        if raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            lineno = int(m.group(1)) if m else 0
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            if path:
                added.append((path, lineno, raw[1:]))
            lineno += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            continue
        elif raw.startswith(" "):
            lineno += 1
    return added


def resolve_all_base(run_git) -> str:
    """Base ref for --all: the most recent tag, else HEAD~20.

    An EMPTY range is legitimate (the tag IS HEAD) and must NOT trigger a
    fallback: rescanning released history would flag long-standing code as newly
    added. Only when NO tag exists do we fall back to HEAD~20.
    """
    rc, stdout, _ = run_git(["describe", "--tags", "--abbrev=0"])
    base = stdout.strip() if rc == 0 and stdout.strip() else ""
    return base or "HEAD~20"


def get_added_lines(run_git, staged: bool = True, unstaged: bool = False,
                    all_scope: bool = False) -> list[tuple[str, int, str]]:
    """Collect ADDED diff lines with accurate line numbers for the given scope.

    `run_git` is injected (regression_check.run_git_command) so this module
    stays free of subprocess/cwd assumptions and is trivially testable.
    """
    added: list[tuple[str, int, str]] = []
    if staged:
        rc, stdout, _ = run_git(["diff", "--cached"])
        if rc == 0:
            added += parse_diff(stdout)
    if unstaged:
        rc, stdout, _ = run_git(["diff"])
        if rc == 0:
            added += parse_diff(stdout)
    if all_scope:
        base = resolve_all_base(run_git)
        rc, stdout, _ = run_git(["diff", f"{base}...HEAD"])
        if rc == 0:
            added += parse_diff(stdout)
    return added


def glob_matches(path: str, globs: list[str]) -> bool:
    """True when the basename OR the repo-relative path matches any glob."""
    base = path.rsplit("/", 1)[-1]
    return any(
        fnmatch.fnmatch(base, g) or fnmatch.fnmatch(path, g) for g in globs or []
    )


def compile_registry_patterns(entries: list[dict]) -> tuple[list[dict], list[str]]:
    """Compile each entry's `regression_pattern` into a matcher.

    An invalid regex is reported as a warning, never fatal — one malformed
    pattern must not take the whole gate down.
    """
    compiled: list[dict] = []
    warnings: list[str] = []
    for entry in entries:
        pattern = (entry.get("regression_pattern") or "").strip()
        if not pattern:
            continue
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            warnings.append(
                f"invalid regression_pattern in {entry.get('failure_id', '?')} "
                f"({exc}): {pattern}"
            )
            continue
        compiled.append({"entry": entry, "rx": rx,
                         "file_glob": entry.get("file_glob") or []})
    return compiled, warnings


def check_added_against_registry(added: list[tuple[str, int, str]],
                                 compiled: list[dict]) -> list[dict]:
    """Match compiled registry patterns against ADDED lines.

    A hit means a previously fixed bug's signature is being re-added. Entries
    scoped with a `file_glob` only fire for matching files, so a doc or helper
    script may quote a pattern without tripping the gate.
    """
    violations: list[dict] = []
    for path, lineno, text in added:
        if path in SELF_REFERENTIAL:
            continue
        for item in compiled:
            if item["file_glob"] and not glob_matches(path, item["file_glob"]):
                continue
            if not item["rx"].search(text):
                continue
            entry = item["entry"]
            violations.append({
                "file": path,
                "line": lineno,
                "failure_id": entry.get("failure_id", "?"),
                "severity": entry.get("severity", "high"),
                "error_message": entry.get("error_message", ""),
                "prevention_rule": entry.get("prevention_rule", ""),
                "pattern": entry.get("regression_pattern", ""),
                "added": text.strip()[:120],
            })
    return violations


def load_failure_registry(registry_path: Path) -> list[dict]:
    """Load registry entries whose status is scanned (active or resolved).

    A RESOLVED entry is exactly the one whose pattern must not come back, so
    both statuses are loaded.
    """
    if not registry_path.exists():
        return []
    entries = []
    with open(registry_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    entry = json.loads(line)
                    if entry.get("status") in SCANNED_STATUSES:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
    return entries


def load_active_failures(entries: list[dict]) -> list[dict]:
    """The subset used for the affected-files cross-reference (active only).

    Preserves DevGate's original behaviour: only ACTIVE failures produce the
    "this file has known bug history" advisory, so resolved bugs don't spam the
    report for every file they ever touched.
    """
    return [e for e in entries if e.get("status") == "active"]
