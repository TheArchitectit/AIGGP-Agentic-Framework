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

`base-own-01` splits the two path/commit verdicts by SOURCE, not by severity:
a BUNDLED (baseline) entry must reference only this repository's paths and
bugs, so a stale path or a fix_commit absent from this repo's history there is
an ERROR ("a hygiene gate SHALL fail when a bundled entry references a path
absent from this tree"). A project OVERLAY entry keeps the older lenient rule —
its paths warn, and its short fix_commits are not resolved — because an overlay
legitimately goes stale as the project renames files, and the overlay is the
thing the project refreshes.

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

# Project root by LAYOUT CONTRACT (root-anchor-01/-03) — identical reasoning to
# regression_check.py and scene_inventory.py. The old _find_project_root() walked
# up from Path.cwd() for the first .git it found, so this gate's overlay
# resolution was both cwd-dependent and free to escape to a parent directory
# above the checkout. This file is not an optional helper: ci.yml runs it on every
# push, which is what makes the shared-contract conformance load-bearing here.
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from project_root import project_root_for  # noqa: E402  # guardrails-allow PREVENT-024: shared root-contract module defined in scripts/lib/project_root.py, not an external package
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_common import read_jsonl_registry  # noqa: E402

PROJECT_ROOT = project_root_for(Path(__file__).resolve().parent.parent)

# Sentinel SHA values that are allowed without git verification.
DUMMY_COMMITS = frozenset({"pending", "a1b2c3d", "0000000"})

REQUIRED_FIELDS = frozenset({
    "failure_id", "timestamp", "category", "severity",
    "error_message", "root_cause", "affected_files",
    "fix_commit", "regression_pattern", "prevention_rule", "status",
})

VALID_STATUSES = frozenset({"active", "resolved", "deprecated"})


def _git_cat_file_t(repo_root: Path, sha: str) -> bool:
    """Return True when `git cat-file -t <sha>` exits 0 in repo_root."""
    try:
        result = subprocess.run(
            ["git", "cat-file", "-t", sha],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(repo_root), timeout=10,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


_SHA_CHARS = frozenset("0123456789abcdefABCDEF")


def _looks_like_sha(value: str) -> bool:
    """True when `value` is a git SHA prefix (7-40 hex chars).

    Short prefixes count. Every foreign entry the 2026-10-25 `base-own-01`
    sweep found carried a 7-char SHA, which a 40-hex-only rule never resolved.
    """
    return 7 <= len(value) <= 40 and all(c in _SHA_CHARS for c in value)


def _is_git_repo(repo_root: Path) -> bool:
    """True when `git rev-parse --git-dir` succeeds in repo_root.

    Separates "this SHA is absent from the repo" (a finding) from "there is no
    git history here to ask" (a copy/tarball install, which may only warn).
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
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
    """Parse JSONL registry. Shared semantics in gate_common.read_jsonl_registry."""
    return read_jsonl_registry(registry_path)


def check(registry_path: Path | None = None, *,
          devgate_root: Path | None = None,
          project_root: Path | None = None) -> tuple[int, list[str]]:
    """Run all hygiene checks over the EFFECTIVE registry — bundled baseline +
    project overlay merged by failure_id (the overlay entry replacing a same-id
    baseline entry is the overlay contract, not a duplicate; duplicates are
    only errors WITHIN one source file). An explicit registry_path checks that
    one file only.

    `devgate_root` / `project_root` are injectable for tests; they default to
    this file's checkout and the root-anchor contract.

    Returns (exit_code, findings).  findings are one-line messages for stdout/stderr.
    Exit 0 means clean; exit 1 means at least one ERROR was emitted.

    `base-own-01` decides which findings are errors: a BUNDLED ("devgate") entry
    with a stale affected_files path or a fix_commit absent from this repo's
    history is an ERROR; the same findings on a project overlay entry are
    WARNINGS, because an overlay goes stale as its project renames files.

    Every entry is validated against the repo that OWNS it (DevGate entries
    against .devgate's git history and files, project entries against the
    project's) — merged entries reference commits/paths in different repos.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if project_root is None:
        project_root = PROJECT_ROOT
    if devgate_root is None:
        devgate_root = Path(__file__).resolve().parent.parent

    if registry_path is not None:
        # An EXPLICITLY named registry that does not exist is a configuration
        # error, never a skip (audit finding: a typo'd FAILURE_REGISTRY_PATH
        # yielded zero entries, zero errors, exit 0 — a vacuous green from the
        # hygiene gate itself). The old guard only covered the "devgate" label.
        if not registry_path.exists():
            return 1, [f"registry not found: {registry_path}"]
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

    # 4. fix_commit via git — in the repo that owns the entry.
    # A bundled entry's bug must be THIS repository's bug (base-own-01), so its
    # SHA is resolved here whether it is written long or short; an overlay entry
    # keeps the older rule and only has a full 40-char SHA resolved.
    for entry, owner, label, lineno in merged:
        fix = (entry.get("fix_commit") or "").strip()
        if not fix:
            errors.append(
                f"{label}:line {lineno} [{entry.get('failure_id','?')}]: empty fix_commit"
            )
        elif fix in DUMMY_COMMITS:
            pass  # allowed dummy
        elif _looks_like_sha(fix):
            if label != "devgate" and len(fix) != 40:
                continue  # overlay short SHA — not resolved (documented leniency)
            if label == "devgate" and not _is_git_repo(owner):
                warnings.append(
                    f"{label}:line {lineno} [{entry.get('failure_id','?')}]: "
                    f"fix_commit '{fix}' unverified — no git history at {owner}"
                )
            elif not _git_cat_file_t(owner, fix):
                errors.append(
                    f"{label}:line {lineno} [{entry.get('failure_id','?')}]: "
                    f"fix_commit '{fix}' not found in git history of {owner}"
                )
        # else: unusual value — accept but don't validate

    # 5. affected_files: path existence. base-own-01 makes a stale path in the
    # BUNDLED baseline an error ("a hygiene gate SHALL fail when a bundled entry
    # references a path absent from this tree"); an overlay keeps the warning.
    for entry, owner, label, lineno in merged:
        raw = entry.get("affected_files")
        if raw is None:
            continue  # caught as missing-field above
        paths = _parse_affected_files(raw)
        for p in paths:
            abs_path = owner / p
            if abs_path.exists():
                continue
            message = (
                f"{label}:line {lineno} [{entry.get('failure_id','?')}]: "
                f"affected_files path not found: '{p}'"
            )
            if label == "devgate":
                errors.append(
                    message + "  (base-own-01 — bundled entry references a path"
                              " absent from this tree)"
                )
            else:
                warnings.append(message + "  (warning — stale entry)")

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
