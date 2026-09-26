#!/usr/bin/env python3
"""check_exec_bits.py — shebang'd files must be executable in the git index
(fw-prov-01, R11 of the remediation plan).

core.fileMode=false makes stat-based checks lie: a locally chmod'd script
commits as 100644 and breaks hosted checkouts (this repo hit it — 14 test
failures with PermissionError). This check works on the GIT INDEX, not the
working tree: every tracked file whose first committed line is a shebang
must have mode 100755.

FAIL output names the exact remediation command per file:
  git update-index --chmod=+x <path>

Zero shebang'd files scanned in a repo that has any tracked files = FAIL
(no vacuous green). Negative control: tests commit a shebang file at
100644 in a scratch index and assert the check fires.

Exit: 0 all good; 1 violations found; 2 usage.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

EXIT_OK = 0
EXIT_VIOLATIONS = 1
EXIT_USAGE = 2


def ls_files_with_modes(repo: str) -> list[tuple[str, str]]:
    r = subprocess.run(["git", "ls-files", "--stage"], cwd=repo,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"check-exec-bits: git ls-files failed: {r.stderr}",
              file=sys.stderr)
        sys.exit(EXIT_USAGE)
    out = []
    for line in r.stdout.splitlines():
        meta, _, path = line.partition("\t")
        if path:
            out.append((meta.split()[0], path))  # (mode, path)
    return out


def committed_first_line(repo: str, path: str) -> str | None:
    # Read the INDEX (`:path` = stage 0), not HEAD: pre-commit usage must
    # judge staged content, and a fresh scratch repo may have no commits.
    r = subprocess.run(["git", "show", f":{path}"], cwd=repo,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not r.stdout:
        return None
    return r.stdout.splitlines()[0] if r.stdout.splitlines() else None


def main() -> int:
    ap = argparse.ArgumentParser(prog="check_exec_bits",
                                 description="shebang files must be 100755 "
                                             "in the git index")
    ap.add_argument("--repo", default=".")
    args = ap.parse_args()

    files = ls_files_with_modes(args.repo)
    if not files:
        print("check-exec-bits: FAIL — zero tracked files; nothing checked",
              file=sys.stderr)
        return EXIT_VIOLATIONS

    violations = []
    checked = 0
    for mode, path in files:
        first = committed_first_line(args.repo, path)
        if first is None or not first.startswith("#!"):
            continue
        checked += 1
        if mode != "100755":
            violations.append((path, mode))

    if checked == 0:
        print("check-exec-bits: FAIL — zero shebang'd files found in a "
              "tracked tree; the check scanned nothing (no vacuous green)",
              file=sys.stderr)
        return EXIT_VIOLATIONS

    if violations:
        print(f"check-exec-bits: FAIL — {len(violations)} shebang'd "
              f"file(s) committed without the exec bit:")
        for path, mode in violations:
            print(f"  {path} (mode {mode})")
            print(f"    fix: git update-index --chmod=+x {path}")
        return EXIT_VIOLATIONS

    print(f"check-exec-bits: OK — {checked} shebang'd file(s), all 100755 "
          f"in the index")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
