#!/usr/bin/env python3
"""branch_drift_check.py — no commit may exist only on local disk.

WHY THIS EXISTS (measured, not theoretical)
Across 67 days of the daily-digest open-items ledger (`ai-news/nextday-actions.md`,
2026-08-27 -> 2026-11-05), the single largest recurring deficiency family is unpushed
or local-only work: **51 of 67 days (76%)**. It is also the only family where a disk
failure destroys real work rather than merely exposing a process gap.

The corpus contains a two-month worked example. Project Epsilon was flagged on 33 of
67 days; 28 of its 34 mentions ask the same thing:

    2026-09-03  "Push or prune Project Epsilon's stranded work — large unpushed delta"
    2026-09-04  "feature/3d-game-development is ~180 commits unpushed and diverged"
    2026-09-06  "N21 and Project Epsilon have divergent local states across hosts"
    2026-09-09  "Push or archive the unpushed mountains — the 3D-game port branch"

Nothing in the AIGGP suite could ever have detected this. Grep for
`unpushed|ahead of origin|local-only|ls-remote.*ahead` across `scripts/` and `hub/`
returns only incidental hits — `deploy.sh` (a release precondition, and not wired
into any workflow), `regression_diff.py` (diff parsing), `hub-watchdog.sh` (runner
liveness). No gate asks "does every ref on disk exist on a remote?"

CONTRACT
  For each declared repository:
    1. Enumerate local refs and their tip commits.
    2. Ask the remote which of those tips it actually has (`git ls-remote`).
    3. A local ref whose tip is reachable from no remote ref is DRIFT — unless it
       carries an explicit archive tag, which is this repo's existing convention
       (e.g. `archive/allowlist-testutil-db-20261020`) and converts "unpushed work"
       into "deliberately parked work".
    4. Report per-repo counts, so the operator sees scale (Epsilon at ~180 commits
       ahead is a different problem from one stray commit).

Exit codes: 0 clean | 1 drift found | 2 usage/config error | 3 nothing scanned
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

EXIT_OK, EXIT_DRIFT, EXIT_USAGE, EXIT_EMPTY = 0, 1, 2, 3
ARCHIVE_PREFIX = "archive/"


def git(repo: Path, *args: str, timeout: int = 60) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(repo), *args],
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (subprocess.TimeoutExpired, OSError) as e:
        return 1, str(e)


def local_refs(repo: Path) -> dict:
    """refname -> tip sha, for branches and tags."""
    out = {}
    rc, txt = git(repo, "for-each-ref", "--format=%(refname:short) %(objectname)",
                          "refs/heads", "refs/tags")
    if rc != 0:
        return out
    for line in txt.splitlines():
        parts = line.split()
        if len(parts) == 2:
            out[parts[0]] = parts[1]
    return out


def remote_tips(repo: Path) -> tuple[set, str]:
    """Set of shas the remote advertises, plus its default branch name if known."""
    rc, txt = git(repo, "ls-remote", "origin", timeout=120)
    if rc != 0:
        return set(), "unreachable"
    shas = set()
    for line in txt.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            shas.add(parts[0])
    # resolve the remote default branch head too
    rc2, def_branch = git(repo, "symbolic-ref", "--quiet", "--short",
                          "refs/remotes/origin/HEAD")
    return shas, (def_branch.strip() if rc2 == 0 else "")


def ahead_count(repo: Path, ref: str) -> int:
    """How many commits on ref are not on any remote-tracking ref."""
    rc, txt = git(repo, "rev-list", "--count", ref, "--not", "--remotes")
    if rc != 0:
        return -1
    try:
        return int(txt.strip() or 0)
    except ValueError:
        return -1


def check_repo(repo: Path) -> dict:
    refs = local_refs(repo)
    rshas, _defb = remote_tips(repo)

    # An archive tag converts "unpushed work" into "deliberately parked work".
    # Match by COMMIT, not by ref name: the convention tags the commit
    # (e.g. `archive/allowlist-testutil-db-20261020` pointing at a branch tip),
    # so the branch keeps its own name and the tag records the decision.
    archived_shas = {sha for name, sha in refs.items()
                     if name.startswith(ARCHIVE_PREFIX)}
    drift, parked = [], []
    for name, sha in sorted(refs.items()):
        if name.startswith(ARCHIVE_PREFIX) or sha in archived_shas:
            parked.append(name)
            continue
        if sha in rshas:
            continue
        n = ahead_count(repo, name)
        drift.append({"ref": name, "sha": sha[:12], "ahead": n})

    return {
        "repo": str(repo),
        "remote_reachable": bool(rshas),
        "local_refs": len(refs),
        "archived_refs": len(parked),
        "drift": drift,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, default=Path.cwd(),
                   help="directory to walk for .git repositories")
    p.add_argument("--repos", type=Path, default=None,
                   help="optional file listing repo paths, one per line")
    p.add_argument("--max-depth", type=int, default=3)
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args()

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
            g = args.root.glob("/".join(["*"] * depth) + ("/.git" if depth else ".git"))
            for pth in g:
                d = pth.parent.resolve()
                if d not in seen:
                    seen.add(d)
                    repos.append(d)

    if not repos:
        print("FATAL: no repositories found — refusing a vacuous pass", file=sys.stderr)
        return EXIT_EMPTY

    results, total_drift, unreachable = [], 0, 0
    for r in sorted(repos):
        res = check_repo(r)
        results.append(res)
        if not res["remote_reachable"]:
            unreachable += 1
        total_drift += len(res["drift"])

    if args.json:
        print(json.dumps({"repos": len(results), "drift_refs": total_drift,
                          "unreachable": unreachable, "results": results}, indent=1))
    else:
        print(f"repos scanned: {len(results)} | drift refs: {total_drift} "
              f"| unreachable remotes: {unreachable}")
        for res in results:
            if not res["drift"]:
                continue
            name = Path(res["repo"]).name
            print(f"\n  {name}  ({len(res['drift'])} ref(s) on no remote, "
                  f"{res['archived_refs']} archived)")
            for d in res["drift"][:12]:
                ahead = f"{d['ahead']} ahead" if d["ahead"] >= 0 else "unknown ahead"
                print(f"    {d['ref']:<44} {d['sha']}  {ahead}")
            if len(res["drift"]) > 12:
                print(f"    ... and {len(res['drift']) - 12} more")

    if total_drift:
        print(f"\nFAIL: {total_drift} ref(s) exist only on local disk. Push them, or "
              f"tag {ARCHIVE_PREFIX}<name>-<date> to declare them deliberately parked.",
              file=sys.stderr)
        return EXIT_DRIFT
    print("OK: every local ref is present on its remote or explicitly archived")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
