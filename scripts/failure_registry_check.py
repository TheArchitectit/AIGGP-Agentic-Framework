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
    FAILURE_REGISTRY_PATH   check this ONE file only (no bundled+overlay merge)

With no override, the DevGate bundled registry and the project's
.guardrails/failure-registry.jsonl overlay are checked as MERGED (an overlay
entry replacing a same-id baseline entry is the contract, not a duplicate),
and each entry's fix_commit / affected_files are validated against the repo
that owns it. See gate_overlay.py.

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
    """Run all hygiene checks over the EFFECTIVE registry — bundled baseline +
    project overlay merged by failure_id (the overlay entry replacing a same-id
    baseline entry is the overlay contract, not a duplicate; duplicates are
    only errors WITHIN one source file). An explicit registry_path checks that
    one file only.

    Returns (exit_code, findings).  findings are one-line messages for stdout/stderr.
    Exit 0 means clean; exit 1 means at least one ERROR was emitted.
    Warnings (stale affected_files paths) are included in findings but do not
    affect the exit code.

    Every entry is validated against the repo that OWNS it (DevGate entries
    against .devgate's git history and files, project entries against the
    project's) — merged entries reference commits/paths in different repos.
    """
    errors: list[str] = []
    warnings: list[str] = []
    project_root = _find_project_root()
    devgate_root = Path(__file__).resolve().parent.parent

    if registry_path is not None:
        sources = [("registry", registry_path, project_root)]
    else:
        sources = [("devgate", devgate_root / ".guardrails" / "failure-registry.jsonl", devgate_root)]
        overlay = project_root / ".guardrails" / "failure-registry.jsonl"
        if overlay.exists() and overlay.resolve() != sources[0][1].resolve():
            sources.append(("project", overlay, project_root))

    # Parse every source; a source that fails to parse is reported and skipped
    # (like before), but any parse error is still a hard failure at the end.
    # merged: list of (entry, owner_repo, label, lineno), id -> position, with
    # overlay replacing a same-id baseline entry in place.
    merged: list[tuple[dict, Path, str, int]] = []
    pos_by_id: dict[str, int] = {}
    had_parse_error = False
    for label, path, owner in sources:
        if not path.exists():
            if label == "devgate":
                errors.append(f"registry not found: {path}")
                return 1, errors + warnings
            continue
        entries, parse_errors = _load_entries(path)
        errors.extend(f"{label}: {e}" for e in parse_errors)
        if parse_errors:
            had_parse_error = True
            continue
        seen_ids: set[str] = set()
        for lineno, entry in enumerate(entries, 1):
            eid = entry.get("failure_id", "")
            if not eid:
                errors.append(f"{label}:line {lineno}: missing or empty failure_id")
            elif eid in seen_ids:
                errors.append(f"{label}:line {lineno}: duplicate failure_id '{eid}'")
            else:
                seen_ids.add(eid)
            if eid and eid in pos_by_id:
                merged[pos_by_id[eid]] = (entry, owner, label, lineno)  # overlay replaces
            elif eid:
                pos_by_id[eid] = len(merged)
                merged.append((entry, owner, label, lineno))
            else:
                merged.append((entry, owner, label, lineno))
    if had_parse_error:
        return 1, errors + warnings

    # 2. Required fields (+ duplicate failure_id reported at merge time)
    for entry, _owner, label, lineno in merged:
        eid = entry.get("failure_id", "")
        missing = REQUIRED_FIELDS - set(entry.keys())
        if missing:
            errors.append(
                f"{label}:line {lineno} [{eid or '?'}]: missing field(s): {', '.join(sorted(missing))}"
            )

    # 3. status enum
    for entry, _owner, label, lineno in merged:
        status = entry.get("status", "")
        if status not in VALID_STATUSES:
            errors.append(
                f"{label}:line {lineno} [{entry.get('failure_id','?')}]: "
                f"invalid status '{status}' — expected one of {sorted(VALID_STATUSES)}"
            )

    # 4. fix_commit via git — in the repo that owns the entry
    for entry, owner, label, lineno in merged:
        fix = (entry.get("fix_commit") or "").strip()
        if not fix:
            errors.append(
                f"{label}:line {lineno} [{entry.get('failure_id','?')}]: empty fix_commit"
            )
        elif fix in DUMMY_COMMITS:
            pass  # allowed dummy
        elif len(fix) == 40 and all(c in "0123456789abcdefABCDEF" for c in fix):
            # looks like a SHA; verify it exists in the owning repo
            if not _git_cat_file_t(owner, fix):
                errors.append(
                    f"{label}:line {lineno} [{entry.get('failure_id','?')}]: "
                    f"fix_commit '{fix}' not found in git history of {owner}"
                )
        # else: unusual value — accept but don't validate

    # 5. affected_files: path existence (WARN only — stale paths are not errors)
    for entry, owner, label, lineno in merged:
        raw = entry.get("affected_files")
        if raw is None:
            continue  # caught as missing-field above
        paths = _parse_affected_files(raw)
        for p in paths:
            abs_path = owner / p
            if not abs_path.exists():
                warnings.append(
                    f"{label}:line {lineno} [{entry.get('failure_id','?')}]: "
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
