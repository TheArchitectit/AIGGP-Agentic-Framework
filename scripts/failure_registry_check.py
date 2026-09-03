#!/usr/bin/env python3
"""
failure_registry_check.py — hygiene gate for .guardrails/failure-registry.jsonl.

Verifies the registry is well-formed and self-consistent without requiring any
particular language or tooling (only git for fix_commit validation). Language-
agnostic: DevGate's own registry is the canonical reference.

Exit codes:
    0  — clean
    1  — findings (parse errors, missing fields, duplicates, invalid status,
          non-existent paths, broken fix_commits)

Environment:
    FAILURE_REGISTRY_PATH   override the default registry path

Supports both shapes of `affected_files` seen in DevGate's own registry:
    * a JSON list  e.g. ["a.go", "b.go"]
    * a comma-joined string  e.g. "a.go,b.go,go/internal/c.go"
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Sentinel SHA values that are allowed without git verification.
DUMMY_COMMITS = frozenset({"pending", "a1b2c3d", "0000000"})

REQUIRED_FIELDS = frozenset({
    "failure_id", "timestamp", "category", "severity",
    "error_message", "root_cause", "affected_files",
    "fix_commit", "regression_pattern", "prevention_rule", "status",
})

VALID_STATUSES = frozenset({"active", "resolved", "deprecated"})


def _find_project_root() -> Path:
    """Walk up from CWD to find a project root marker."""
    cwd = Path.cwd()
    for d in [cwd] + list(cwd.parents):
        if (d / ".git").exists():
            return d
    return cwd


def _default_registry_path() -> Path:
    """Resolve the default registry relative to the DevGate scripts dir."""
    scripts_dir = Path(__file__).resolve().parent
    devgate_root = scripts_dir.parent
    return devgate_root / ".guardrails" / "failure-registry.jsonl"


def _git_cat_file_t(repo_root: Path, sha: str) -> bool:
    """Return True when `git cat-file -t <sha>` exits 0 in repo_root."""
    try:
        result = subprocess.run(
            ["git", "cat-file", "-t", sha],
            capture_output=True, text=True,
            cwd=str(repo_root), timeout=10,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _parse_affected_files(raw) -> list[str]:
    """Normalise `affected_files` to a list regardless of its original shape.

    Handles three shapes seen in the wild:
      * ["a.go", "b.go"]                — plain list
      * "a.go,b.go"                      — comma-joined string
      * ["a.go,b.go,c.go"]               — list whose element(s) are comma-joined
    """
    if isinstance(raw, str):
        return [f.strip() for f in raw.split(",") if f.strip()]
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            out.extend(f.strip() for f in str(item).split(",") if f.strip())
        return out
    return []


def _load_entries(registry_path: Path) -> tuple[list[dict], list[str]]:
    """Parse JSONL registry, skipping blank lines and # comments.

    Returns (entries, parse_errors). parse_errors contains one-line summaries
    for lines that could not be decoded.
    """
    entries: list[dict] = []
    parse_errors: list[str] = []
    if not registry_path.exists():
        parse_errors.append(f"registry not found: {registry_path}")
        return entries, parse_errors
    with open(registry_path, encoding="utf-8", errors="replace") as fh:
        for lineno, raw in enumerate(fh, 1):
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                entries.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                parse_errors.append(
                    f"line {lineno}: JSON parse error — {exc}"
                )
    return entries, parse_errors


def check(registry_path: Path | None = None) -> tuple[int, list[str]]:
    """Run all hygiene checks.

    Returns (exit_code, findings).  findings are one-line messages for stdout/stderr.
    Exit 0 means clean; exit 1 means at least one ERROR was emitted.
    Warnings (stale affected_files paths) are included in findings but do not
    affect the exit code.
    """
    errors: list[str] = []
    warnings: list[str] = []
    registry_path = registry_path or _default_registry_path()

    # 1. JSONL parse
    entries, parse_errors = _load_entries(registry_path)
    errors.extend(parse_errors)
    if parse_errors:
        return 1, errors + warnings

    # 2. Required fields + duplicate failure_id
    seen_ids: set[str] = set()
    for lineno, entry in enumerate(entries, 1):
        eid = entry.get("failure_id", "")
        if not eid:
            errors.append(f"line {lineno}: missing or empty failure_id")
        elif eid in seen_ids:
            errors.append(f"line {lineno}: duplicate failure_id '{eid}'")
        else:
            seen_ids.add(eid)

        missing = REQUIRED_FIELDS - set(entry.keys())
        if missing:
            errors.append(
                f"line {lineno} [{eid or '?'}]: missing field(s): {', '.join(sorted(missing))}"
            )

    # 3. status enum
    for lineno, entry in enumerate(entries, 1):
        status = entry.get("status", "")
        if status not in VALID_STATUSES:
            errors.append(
                f"line {lineno} [{entry.get('failure_id','?')}]: "
                f"invalid status '{status}' — expected one of {sorted(VALID_STATUSES)}"
            )

    # 4. fix_commit via git
    repo_root = _find_project_root()
    for lineno, entry in enumerate(entries, 1):
        fix = (entry.get("fix_commit") or "").strip()
        if not fix:
            errors.append(
                f"line {lineno} [{entry.get('failure_id','?')}]: empty fix_commit"
            )
        elif fix in DUMMY_COMMITS:
            pass  # allowed dummy
        elif len(fix) == 40 and all(c in "0123456789abcdefABCDEF" for c in fix):
            # looks like a SHA; verify it exists
            if not _git_cat_file_t(repo_root, fix):
                errors.append(
                    f"line {lineno} [{entry.get('failure_id','?')}]: "
                    f"fix_commit '{fix}' not found in git history"
                )
        # else: unusual value — accept but don't validate

    # 5. affected_files: path existence (WARN only — stale paths are not errors)
    for lineno, entry in enumerate(entries, 1):
        raw = entry.get("affected_files")
        if raw is None:
            continue  # caught as missing-field above
        paths = _parse_affected_files(raw)
        for p in paths:
            abs_path = repo_root / p
            if not abs_path.exists():
                warnings.append(
                    f"line {lineno} [{entry.get('failure_id','?')}]: "
                    f"affected_files path not found: '{p}'  (warning — stale entry)"
                )

    findings = errors + warnings
    return (0 if not errors else 1), findings


def main() -> int:
    env_path = os.getenv("FAILURE_REGISTRY_PATH", "")
    registry_path = Path(env_path) if env_path else None
    exit_code, findings = check(registry_path)
    for f in findings:
        print(f, file=sys.stderr if "not found" in f or "not found in git" in f else sys.stdout)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
