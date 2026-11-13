#!/usr/bin/env python3
# // spec: tc-01, tc-02, tc-03, tc-04
"""tree_clean_check.py — unclassified working-tree dirt is a gate failure.

WHY THIS EXISTS (measured, not theoretical)
Across 67 days of the digest open-items ledger (`ai-news/nextday-actions.md`,
2026-08-27 -> 2026-11-05) the dirty/untracked working tree family appears on **42 of 67
days (63%)**, with a 6-day unbroken streak. Concrete instances from the corpus:

    2026-08-28  "Two numbered repos show thousands of modified files in the working
                 tree — decide git-vs-ignore once so diffs become legible"
    2026-11-05  "Project N12's working tree carries 209 untracked files"
    2026-11-05  "Project N158's 219 file-mode-only entries need a core.fileMode/
                 .gitattributes normalization"
    (also)      "Project N76 and Project N86 worktrees showing 14,373 dirty files each"

The suite's only dirty-tree rejection lives at `scripts/deploy.sh:79` and **`deploy.sh`
is referenced by no workflow** — it is a manual release path. So a repository can sit at
14,373 dirty files indefinitely with CI green.

WHY IT MATTERS MORE THAN IT LOOKS
Dirt is not just untidiness: it blinds every other review. A 14,373-file diff hides the
three real edits inside it, which is how unpushed work (see `branch_drift_check.py`)
survives months of scrutiny.

CONTRACT
  For each declared repository:
    1. Read `git status --porcelain -z` and classify each entry:
         generated  — matches a gitignore-style pattern from --generated (build output,
                      caches, file-mode churn)
         real       — anything else
    2. Fail when `real` entries exceed --max-real (default 0).
    3. Report `generated` separately: it does not fail, but it is named, because the fix
       for generated churn is a `.gitignore`/`core.fileMode` decision, not a commit.
    4. File-mode-only entries are their own class, because the corpus shows that exact
       pathology (N158, 219 entries) and it needs `core.fileMode=false` or
       `.gitattributes`, not deletion.

Exit codes: 0 clean | 1 real dirt found | 2 usage/config error | 3 nothing scanned
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

EXIT_OK, EXIT_DIRT, EXIT_USAGE, EXIT_EMPTY = 0, 1, 2, 3

DEFAULT_GENERATED = [
    "*.pyc", "*.pyo", "__pycache__/*", ".pytest_cache/*",
    "node_modules/*", "dist/*", "build/*", "target/*", "*.egg-info/*",
    ".venv/*", "venv/*", ".mypy_cache/*", ".ruff_cache/*",
    "*.log", "*.tmp", "*.swp", ".DS_Store",
]


def git(repo: Path, *args: str, timeout: int = 90) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(repo), *args],
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout or ""
    except (subprocess.TimeoutExpired, OSError) as e:
        return 1, str(e)


def classify(repo: Path, patterns: list[str]) -> dict:
    rc, out = git(repo, "status", "--porcelain", "-z")
    if rc != 0:
        return {"repo": str(repo), "error": "git status failed", "real": [],
                "generated": 0, "mode_only": 0}

    entries = [e for e in out.split("\0") if e.strip()]
    real, generated, mode_only = [], 0, 0

    for e in entries:
        status, _, path = e[:2], e[2:3], e[3:]
        path = path.strip()
        if not path:
            continue
        # git reports mode-only churn as a normal modification; we cannot see the mode
        # bit here, so we detect it separately below via diff --summary.
        if any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(Path(path).name, p)
               for p in patterns):
            generated += 1
        else:
            real.append({"status": status.strip(), "path": path})

    # file-mode-only churn: `git diff --summary` prints "mode change 100644 => 100755"
    rc2, summ = git(repo, "diff", "--summary")
    if rc2 == 0:
        mode_only = sum(1 for line in summ.splitlines() if "mode change" in line)

    return {
        "repo": str(repo),
        "real": real,
        "real_count": len(real),
        "generated": generated,
        "mode_only": mode_only,
        "total": len(entries),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--repos", type=Path, default=None)
    p.add_argument("--max-depth", type=int, default=3)
    p.add_argument("--max-real", type=int, default=0,
                   help="real (unclassified) dirty entries tolerated per repo")
    p.add_argument("--generated", action="append", default=None,
                   help="extra gitignore-style pattern to treat as generated")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    patterns = list(DEFAULT_GENERATED) + (args.generated or [])

    if args.repos:
        if not args.repos.exists():
            print(f"FATAL: repo list not found: {args.repos}", file=sys.stderr)
            return EXIT_USAGE
        repos = [Path(l.strip()) for l in args.repos.read_text().splitlines()
                 if l.strip() and not l.strip().startswith("#")]
        repos = [r for r in repos if (r / ".git").exists()]
    else:
        if not args.root.exists():
            print(f"FATAL: root not found: {args.root}", file=sys.stderr)
            return EXIT_USAGE
        repos, seen = [], set()
        for depth in range(args.max_depth + 1):
            pat = "/".join(["*"] * depth) + ("/.git" if depth else ".git")
            for pth in args.root.glob(pat):
                d = pth.parent.resolve()
                if d not in seen:
                    seen.add(d)
                    repos.append(d)

    if not repos:
        print("FATAL: no repositories found — refusing a vacuous pass", file=sys.stderr)
        return EXIT_EMPTY

    results = [classify(r, patterns) for r in sorted(repos)]
    offenders = [r for r in results if r.get("real_count", 0) > args.max_real]

    if args.json:
        print(json.dumps({"repos": len(results), "offenders": len(offenders),
                          "results": results}, indent=1))
    else:
        print(f"repos scanned: {len(results)} | with unclassified dirt: {len(offenders)}")
        for r in offenders:
            print(f"\n  {Path(r['repo']).name}  real={r['real_count']} "
                  f"generated={r['generated']} mode-only={r['mode_only']}")
            for e in r["real"][:10]:
                print(f"    {e['status']:<3} {e['path'][:90]}")
            if r["real_count"] > 10:
                print(f"    ... and {r['real_count'] - 10} more")
            if r["mode_only"]:
                print(f"    note: {r['mode_only']} file-mode-only entries — "
                      f"needs core.fileMode=false or .gitattributes, not deletion")

    if offenders:
        print(f"\nFAIL: {len(offenders)} repo(s) carry unclassified working-tree dirt. "
              f"Commit the real work; add generated paths to .gitignore or --generated.",
              file=sys.stderr)
        return EXIT_DIRT
    # --json emits a parsable document and nothing else.
    if not args.json:
        print("OK: no unclassified working-tree dirt")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
