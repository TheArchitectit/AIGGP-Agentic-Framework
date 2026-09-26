#!/usr/bin/env python3
"""regression_corpus.py — engineering memory: relevance selection and
stale-knowledge detection over the failure registry (fw-mem-*).

The failure registry (.guardrails/failure-registry.jsonl) records every
fixed bug with a regression_pattern and the files it touched. That history
is only an engineering memory if it answers two questions:

  1. RELEVANCE — "this diff touched X; which historical failures could it
     reintroduce?" Selects the registry entries whose affected_files or
     file_glob intersect the changed set, so the tests that guard them can
     be rerun on every related change instead of never.

  2. STALENESS — "is the protection still real?" An entry is stale when
     (a) its affected_files no longer exist (the subsystem was deleted or
     renamed), or (b) its regression_pattern no longer matches anywhere in
     the tree (the code it guards was rewritten away) — meaning the
     recorded protection may be guarding nothing and needs refresh.

Exit codes: 0 ok; 1 (--check) stale entries found; 30 usage error.

Usage:
  python3 scripts/regression_corpus.py --diff HEAD~3            # relevance
  python3 scripts/regression_corpus.py --stale                  # audit
  python3 scripts/regression_corpus.py --stale --strict         # CI gate
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

DEVGATE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = DEVGATE_ROOT / ".guardrails" / "failure-registry.jsonl"

EXIT_OK = 0
EXIT_STALE = 1
EXIT_USAGE = 30


def load_registry(path: Path) -> list:
    if not path.is_file():
        return []
    entries = []
    for ln, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue  # the registry header is comment convention, not data
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"regression-corpus: skipping bad line {ln}",
                  file=sys.stderr)
    return entries


def changed_files(diff_base: str, cwd: str) -> list:
    """Files added/modified in the diff range (union of name-status)."""
    r = subprocess.run(["git", "diff", "--name-only", "--diff-filter=ACMR",
                        diff_base], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError(f"git diff failed: {r.stderr.strip()}")
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def _matches(path: str, entry: dict) -> bool:
    """Does this changed path fall under an entry's watch scope?"""
    if path in (entry.get("affected_files") or []):
        return True
    for glob in entry.get("file_glob") or []:
        if fnmatch.fnmatch(path, glob):
            return True
        # A directory-scope glob ('hub/') also covers everything under it.
        if glob.endswith("/") and path.startswith(glob):
            return True
    return False


def relevant_entries(entries: list, changed: list) -> list:
    hits = []
    for e in entries:
        matched = [p for p in changed if _matches(p, e)]
        if matched:
            hits.append({
                "failure_id": e.get("failure_id"),
                "error_message": (e.get("error_message") or "")[:100],
                "status": e.get("status"),
                "matched_paths": matched[:5],
                "regression_pattern": e.get("regression_pattern") or "",
            })
    return hits


def stale_entries(entries: list, root: Path) -> list:
    """Entries whose recorded protection may be guarding nothing.

    Semantics matter here (an inverted reading would flag healthy entries):
    a regression_pattern matching NOTHING in the current tree is HEALTHY —
    the guarded construct is absent and the pattern stands armed against
    reintroduction in future diffs. The genuine staleness signals are:

      stale path    — affected_files gone from the tree (deleted subsystem
                      or a rename without registry follow-up);
      dead pattern  — the regression_pattern does not compile (it can never
                      fire on any future diff);
      unresolved    — a RESOLVED entry whose pattern still matches its own
                      affected files: either the fix is missing or the
                      pattern is overbroad and will false-positive on every
                      diff touching that file. Either way: review.
    """
    stale = []
    for e in entries:
        fid = e.get("failure_id")
        missing_paths = [p for p in (e.get("affected_files") or [])
                         if not (root / p).exists()]
        dead_pattern = ""
        unresolved_pattern = ""
        pattern = e.get("regression_pattern") or ""
        if pattern:
            try:
                rx = re.compile(pattern)
            except re.error:
                dead_pattern = pattern
                rx = None
            if rx is not None and e.get("status") == "resolved":
                for p in (e.get("affected_files") or []):
                    fp = root / p
                    if not fp.is_file():
                        continue
                    try:
                        text = fp.read_text(encoding="utf-8",
                                            errors="replace")
                    except OSError:
                        continue
                    if rx.search(text):
                        unresolved_pattern = pattern
                        break
        if missing_paths or dead_pattern or unresolved_pattern:
            stale.append({
                "failure_id": fid,
                "missing_paths": missing_paths,
                "dead_pattern": dead_pattern,
                "unresolved_pattern": unresolved_pattern,
            })
    return stale


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="regression_corpus",
        description="relevance selection + staleness audit over the "
                    "failure registry")
    ap.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    ap.add_argument("--diff", help="git diff base for relevance selection")
    ap.add_argument("--stale", action="store_true",
                    help="audit for stale protection")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when stale entries exist (CI gate)")
    args = ap.parse_args()

    registry = Path(args.registry)
    entries = load_registry(registry)
    if not entries:
        print(f"regression-corpus: registry empty or missing: {registry}")
        return EXIT_OK

    rc = EXIT_OK
    if args.diff:
        try:
            changed = changed_files(args.diff, str(DEVGATE_ROOT))
        except RuntimeError as e:
            print(f"regression-corpus: {e}", file=sys.stderr)
            return EXIT_USAGE
        hits = relevant_entries(entries, changed)
        print(f"regression-corpus: {len(changed)} changed path(s), "
              f"{len(hits)} relevant historical failure(s)")
        for h in hits:
            print(f"  ! {h['failure_id']} [{h['status']}] "
                  f"{h['error_message']}")
            print(f"    matched: {', '.join(h['matched_paths'])}")
            if h["regression_pattern"]:
                print(f"    rerun guard pattern: {h['regression_pattern']}")
        if not hits:
            print("  (no historical failure scopes intersect this diff)")

    if args.stale:
        stale = stale_entries(entries, DEVGATE_ROOT)
        print(f"regression-corpus: {len(stale)} stale protection entr(ies)")
        for s in stale:
            why = []
            if s["missing_paths"]:
                why.append(f"paths gone: {', '.join(s['missing_paths'])}")
            if s["dead_pattern"]:
                why.append(f"pattern does not compile: "
                           f"{s['dead_pattern'][:60]}")
            if s["unresolved_pattern"]:
                why.append(f"RESOLVED entry whose pattern still matches "
                           f"its own files: {s['unresolved_pattern'][:60]}")
            print(f"  ! {s['failure_id']}: {'; '.join(why)}")
        if stale and args.strict:
            rc = EXIT_STALE

    if not args.diff and not args.stale:
        ap.error("one of --diff / --stale is required")
        return EXIT_USAGE
    return rc


if __name__ == "__main__":
    sys.exit(main())
