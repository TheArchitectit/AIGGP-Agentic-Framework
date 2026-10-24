#!/usr/bin/env python3
# spec: repo-002-01, repo-002-02, repo-002-03, repo-002-04, repo-005-03
"""check_boundary.py — the fleet-manager package boundary gate (REPO-002).

The tree is one open repository plus a declared product-tiers root
(`fleet-manager/`, OD-002). Three things can go wrong silently, and each is a
one-way door once a commercial line of work has started:

  - a file appears under the boundary that nobody declared (the boundary stops
    being a declaration and becomes whatever happens to be in the directory);
  - open-core code imports the boundary (the boundary can no longer be
    extracted, and the open core stops building without it);
  - product-tiers code appears somewhere else entirely (the "license
    spaghetti" failure the program's risk register names).

Exit: 0 the boundary agrees; 1 a violation (named); 2 usage or manifest error.
Exit 2 is deliberate: a gate that cannot read its own declaration must never
report a clean boundary (the same fail-closed rule SGA-11 uses for the tier
file).

What this gate is NOT: an import resolver. See the change design doc for the
stated limits — a dynamically computed module name is not detected, and only
code files are scanned, because a gate that reds on prose gets muted.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_USAGE = 2

BOUNDARY_DIRNAME = "fleet-manager"
MANIFEST_NAME = "manifest.json"

# Extensions the dependency scan reads. Prose (.md) and data (.json, .lock,
# .txt) are excluded on purpose: documentation may name the boundary freely.
CODE_SUFFIXES = {
    ".py", ".sh", ".bash", ".rs", ".js", ".mjs", ".cjs", ".ts", ".tsx",
    ".yml", ".yaml",
}
# Directories never worth walking — consumed from the shared scope contract
# (.guardrails/scope.json), never redeclared (fw-scope-01). This gate shipped
# its own four-entry literal until the scope-contract test caught it; a private
# list drifts from the other gates and then "clean" means "clean in here".
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_common import load_skip_dirs  # noqa: E402

SKIP_DIRS = load_skip_dirs()

# One pattern for "this line references the boundary": the Python module name,
# or a filesystem path into the root. Word boundaries keep `fleet_managerx`
# (a different module) out.
BOUNDARY_REF = re.compile(r"\bfleet_manager\b|fleet-manager/")


def die(msg: str) -> int:
    print(f"[boundary] {msg}", file=sys.stderr)
    return EXIT_USAGE


def load_manifest(repo: Path) -> tuple[dict | None, int]:
    path = repo / BOUNDARY_DIRNAME / MANIFEST_NAME
    if not path.is_file():
        return None, die(f"manifest missing: {path} — a boundary with no "
                         f"declaration cannot be reported clean")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, die(f"manifest unreadable or not JSON: {path}: {exc}")
    if not isinstance(doc, dict):
        return None, die(f"manifest is not a JSON object: {path}")

    root = doc.get("boundary_root")
    if root != BOUNDARY_DIRNAME:
        return None, die(f"manifest boundary_root is {root!r}, expected "
                         f"{BOUNDARY_DIRNAME!r} (OD-002 names the root once)")
    license_block = doc.get("license") or {}
    if license_block.get("spdx") != "BSD-3-Clause":
        return None, die("manifest license must be BSD-3-Clause (OD-001: no "
                         "commercial split in Phase 1)")
    if license_block.get("separate_grant") is not False:
        return None, die("manifest claims a separate license grant "
                         "(separate_grant must be false under OD-001)")
    if not license_block.get("file"):
        return None, die("manifest license.file is empty — name the file that "
                         "carries the grant (the repository root LICENSE)")
    patterns = doc.get("paths")
    if not isinstance(patterns, list) or not patterns:
        return None, die("manifest paths must be a non-empty list")
    for pat in patterns:
        if not isinstance(pat, str) or not pat.startswith(BOUNDARY_DIRNAME + "/"):
            return None, die(f"declared path is not inside the boundary root: "
                             f"{pat!r}")
        if ".." in Path(pat).parts:
            return None, die(f"declared path escapes the boundary root: {pat!r}")
    forbidden = doc.get("forbidden_roots") or []
    if not isinstance(forbidden, list):
        return None, die("manifest forbidden_roots must be a list")
    exempt = doc.get("exempt_paths") or []
    if not isinstance(exempt, list):
        return None, die("manifest exempt_paths must be a list")
    # Invocation sites: files allowed to NAME the boundary because they start
    # its tests or gates, without being allowed to import from it. CI has to
    # run the boundary's own suite; a static scanner cannot tell "run its
    # tests" from "import its internals", so the allowance is a declared,
    # reviewed list instead of a blanket silence. Kept separate from
    # exempt_paths so the reason a file is skipped is written down.
    invoke = doc.get("invocation_paths") or []
    if not isinstance(invoke, list):
        return None, die("manifest invocation_paths must be a list")
    for rel in invoke:
        if not isinstance(rel, str) or not rel or rel.startswith("/"):
            return None, die(f"invocation site is not a repo-relative path: "
                             f"{rel!r}")
        if ".." in Path(rel).parts:
            return None, die(f"invocation site escapes the repository: {rel!r}")
        if rel.startswith(BOUNDARY_DIRNAME + "/"):
            return None, die(f"invocation site is inside the boundary, where "
                             f"the rule does not apply: {rel!r}")
    return doc, EXIT_OK


def covers(patterns: list[str], rel: str) -> bool:
    """True when `rel` (repo-relative, POSIX) is matched by a declared pattern.

    `dir/**` is a prefix rule, which fnmatch cannot express, so it is handled
    before fnmatch sees the pattern.
    """
    for pat in patterns:
        if pat.endswith("/**"):
            if rel.startswith(pat[:-3] + "/") or rel == pat[:-3]:
                return True
        elif fnmatch.fnmatchcase(rel, pat):
            return True
    return False


def walk_files(repo: Path):
    for path in sorted(repo.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(repo).parts):
            continue
        yield path


def check_coverage(repo: Path, patterns: list[str]) -> list[str]:
    violations = []
    boundary = repo / BOUNDARY_DIRNAME
    if not boundary.is_dir():
        return [f"{BOUNDARY_DIRNAME}/: boundary root does not exist"]
    for path in walk_files(boundary):
        rel = path.relative_to(repo).as_posix()
        if not covers(patterns, rel):
            violations.append(f"{rel}: under the boundary but matched by no "
                              f"declared path (declare it in {BOUNDARY_DIRNAME}/"
                              f"{MANIFEST_NAME})")
    return violations


def check_dependency_direction(repo: Path, exempt: set[str]) -> list[str]:
    violations = []
    boundary_prefix = BOUNDARY_DIRNAME + "/"
    for path in walk_files(repo):
        rel = path.relative_to(repo).as_posix()
        if rel.startswith(boundary_prefix) or rel in exempt:
            continue
        if path.suffix not in CODE_SUFFIXES:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            violations.append(f"{rel}: unreadable ({exc})")
            continue
        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue
            if BOUNDARY_REF.search(line):
                violations.append(
                    f"{rel}:{lineno}: open-core code references the boundary "
                    f"({BOUNDARY_REF.search(line).group(0)!r}); the allowed "
                    f"direction is boundary -> core only")
    return violations


def changed_paths(repo: Path, base: str) -> list[str] | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "diff", "--name-only", f"{base}...HEAD"],
            capture_output=True, text=True, timeout=120, check=True)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"[boundary] --changed-base {base!r} could not be resolved: {exc}",
              file=sys.stderr)
        return None
    return [l for l in out.stdout.splitlines() if l.strip()]


def check_forbidden_roots(changed: list[str], forbidden: list[str]) -> list[str]:
    violations = []
    for rel in changed:
        for root in forbidden:
            root = root.strip("/")
            if rel == root or rel.startswith(root + "/"):
                violations.append(
                    f"{rel}: product-tiers code outside the declared boundary "
                    f"root (forbidden root {root!r}; it belongs under "
                    f"{BOUNDARY_DIRNAME}/)")
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="fleet-manager boundary gate")
    ap.add_argument("--repo", default=".", help="repository root (default .)")
    ap.add_argument("--changed-base", default=None,
                    help="git ref to diff against for the scattered-code check")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        return die(f"{repo} is not a git repository")

    doc, rc = load_manifest(repo)
    if doc is None:
        return rc

    patterns = doc["paths"]
    exempt = set(doc.get("exempt_paths") or []) | set(
        doc.get("invocation_paths") or [])
    violations = check_coverage(repo, patterns)
    violations += check_dependency_direction(repo, exempt)

    if args.changed_base:
        changed = changed_paths(repo, args.changed_base)
        if changed is None:
            return EXIT_USAGE
        violations += check_forbidden_roots(changed, doc.get("forbidden_roots") or [])

    boundary_files = sum(1 for _ in walk_files(repo / BOUNDARY_DIRNAME))
    if violations:
        print(f"[boundary] FAIL: {len(violations)} violation(s)", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return EXIT_VIOLATION

    print(f"[boundary] OK: {boundary_files} file(s) under {BOUNDARY_DIRNAME}/, "
          f"all declared; no open-core reference to the boundary"
          + (f"; changed paths against {args.changed_base} clean"
             if args.changed_base else ""))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
