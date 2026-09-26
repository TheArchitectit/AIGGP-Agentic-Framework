#!/usr/bin/env python3
"""allowlist_health.py — watch for "green through accumulated suppression"
(fw-noise-01, R8 of the remediation plan).

Compares an allowlist file against its git merge-base with the target
branch and reports:
  - entries added / removed, per family
  - the share of additions that suppress TEST-file content
  - total growth vs a per-PR budget

Exit contract: 0 within budget (with a NOTICE line); 10 ADVISORY when the
budget or the test-suppression heuristic trips; 1 FAIL on an unparseable
allowlist (never a silent pass); 2 usage. A SHRINK is reported as positive
news, exit 0.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_ADVISORY = 10
EXIT_FAIL = 1
EXIT_USAGE = 2

GO_TEST_FILE = re.compile(r"_test\.go$")


def load_entries(path: Path) -> list:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"allowlist-health: FAIL — cannot parse {path}: {e}",
              file=sys.stderr)
        sys.exit(EXIT_FAIL)
    if not isinstance(doc, dict) or not isinstance(doc.get("entries"), list):
        print("allowlist-health: FAIL — allowlist must be an object with "
              "an 'entries' array", file=sys.stderr)
        sys.exit(EXIT_FAIL)
    return doc["entries"]


def entries_at_ref(repo: Path, ref: str, rel: str) -> list | None:
    """Entries as of `ref`, or None when the file did not exist there."""
    r = subprocess.run(
        ["git", "show", f"{ref}:{rel}"], capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(repo))
    if r.returncode != 0:
        return None
    try:
        doc = json.loads(r.stdout)
    except json.JSONDecodeError:
        print("allowlist-health: FAIL — baseline allowlist at "
              f"{ref} is unparseable", file=sys.stderr)
        sys.exit(EXIT_FAIL)
    return doc.get("entries", []) if isinstance(doc, dict) else []


def key(e: dict) -> tuple:
    return (e.get("file", ""), e.get("marker", ""))


def main() -> int:
    ap = argparse.ArgumentParser(prog="allowlist_health",
                                 description="watch allowlist growth")
    ap.add_argument("--allowlist",
                    default=".guardrails/silent-success-allowlist.json")
    ap.add_argument("--target", default="origin/main",
                    help="branch to compare against (merge-base)")
    ap.add_argument("--budget", type=int, default=25,
                    help="max net NEW entries per change (default 25)")
    ap.add_argument("--test-share", type=float, default=0.5,
                    help="advisory threshold for test-file suppressions "
                         "among additions (default 0.5)")
    args = ap.parse_args()

    repo = Path.cwd()
    rel = args.allowlist
    current = load_entries(repo / rel)
    base_entries = entries_at_ref(repo, args.target, rel)
    if base_entries is None:
        base_entries = []

    base_keys = {key(e) for e in base_entries if isinstance(e, dict)}
    cur_keys = {key(e) for e in current if isinstance(e, dict)}
    added = sorted(cur_keys - base_keys)
    removed = sorted(base_keys - cur_keys)

    test_adds = [a for a in added if GO_TEST_FILE.search(a[0] or "")]
    growth = len(added) - len(removed)
    share = (len(test_adds) / len(added)) if added else 0.0

    print(f"allowlist-health: {len(added)} added, {len(removed)} removed "
          f"(net {growth:+d}; budget +{args.budget}); "
          f"test-file share of additions: {share:.0%}")
    if removed:
        print("  removed (good):")
        for k in removed[:10]:
            print(f"    - {k[0]} :: {str(k[1])[:60]}")
    for k in added[:10]:
        print(f"  + {k[0]} :: {str(k[1])[:60]}")
    if len(added) > 10:
        print(f"  … and {len(added) - 10} more")

    advisories = []
    if growth > args.budget:
        advisories.append(
            f"net growth +{growth} exceeds the +{args.budget} budget — "
            f"green-through-suppression pattern")
    if added and share > args.test_share:
        advisories.append(
            f"{share:.0%} of additions suppress TEST-file content — fix the "
            f"scope (family exclude_globs) instead of the allowlist")
    if advisories:
        print("allowlist-health: ADVISORY")
        for a in advisories:
            print(f"  ::warning::{a}")
        return EXIT_ADVISORY
    if added or removed:
        print("allowlist-health: NOTICE — within budget")
    else:
        print("allowlist-health: no allowlist change")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
