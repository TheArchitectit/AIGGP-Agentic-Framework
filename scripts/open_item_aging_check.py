#!/usr/bin/env python3
"""open-item-aging-check.py — no open item may live forever untriaged.

WHY THIS EXISTS (measured, not theoretical)
Measured 2026-11-05 against `ai-news/nextday-actions.md` (the canonical append-only
per-day ledger written by the digest before promotion):

  * 67 unique date blocks, 2026-08-27 -> 2026-11-05, 550 items.
  * 61 of 67 days emitted **exactly 7** items. The count is model-authored
    (`grep '^NEXTDAY:'` in the generated script), not a coded quota — so the
    per-day count carries no information about defect density.
  * The same deficiency families recur on most days:
      verify/not-verified      59/67 days (88%)  longest streak 19
      unpushed/local-only      51/67 days (76%)  longest streak  8
      dirty/untracked tree     42/67 days (63%)  longest streak  6
  * One entity, Project Epsilon, was flagged on 33 of 67 days; 28 of those 34
    mentions asked the *same* thing ("push or archive its unpushed branches").

Nothing in the suite measures whether a finding is ever **retired**. Every family
above is re-discovered daily because manual detection has no memory and no gate.
`failure_registry_check.py` applies this discipline to fix commits; this gate applies
the same discipline to open items.

CONTRACT
  Input: a markdown backlog with `- [ ]`, `- [~]`, `- [!]`, `- [x]` rows that carry a
  source date, plus optionally a JSONL triage ledger of explicit dispositions.

  Rules:
    1. Every open row older than --max-age-days must carry an explicit triage
       disposition (fixed / deferred-with-reason / not-actionable) in the triage
       ledger, or the gate fails naming it.
    2. A `deferred` disposition carries a review-by date; past it, the item fails
       again. Deferral is a decision with an expiry, never a permanent state.
    3. A row with no parseable source date is a failure, not a default: an item whose
       age cannot be established cannot be aged out and becomes permanent by accident.
    4. Zero rows parsed is a failure (nothing_scanned), never green.

Exit codes: 0 pass | 1 violations | 2 usage/config error | 3 nothing scanned
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

EXIT_OK, EXIT_VIOLATION, EXIT_USAGE, EXIT_EMPTY = 0, 1, 2, 3

ROW_RE = re.compile(r"^\s*-\s*\[(?P<mark>[ x~!])\]\s*(?P<body>.+)$")
ID_RE = re.compile(r"\b([A-Z]+-\d{3})\b")
# a source date is required to age an item; accepted shapes seen in the real corpus
DATE_PATTERNS = [
    re.compile(r"source:\s*digest\s+(\d{4}-\d{2}-\d{2})", re.I),
    re.compile(r"\((\d{4}-\d{2}-\d{2})\)"),
    re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b"),
]


def parse_rows(path: Path) -> tuple[list[dict], list[str]]:
    """Return (rows, problems). Problems cover unparseable ages."""
    rows, problems = [], []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = ROW_RE.match(line)
        if not m:
            continue
        mark, body = m.group("mark"), m.group("body").strip()
        if mark == "x":
            continue  # closed rows are not aged
        ident = ID_RE.search(body)
        when = None
        for pat in DATE_PATTERNS:
            dm = pat.search(body)
            if dm:
                try:
                    when = dt.date.fromisoformat(dm.group(1))
                except ValueError:
                    when = None
                if when:
                    break
        rows.append({
            "line": lineno,
            "id": ident.group(1) if ident else None,
            "mark": mark,
            "date": when,
            "text": body[:120],
        })
        if when is None:
            problems.append(f"line {lineno}: open row has no parseable source date "
                            f"({body[:60]!r}) — cannot be aged, will become permanent")
    return rows, problems


def load_triage(path: Path | None) -> dict:
    """triage ledger: one JSON object per line, keyed by id."""
    if path is None or not path.exists():
        return {}
    out = {}
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            raise SystemExit(f"FATAL: triage ledger line {lineno} is not JSON: {e}")
        key = rec.get("id")
        if not key:
            raise SystemExit(f"FATAL: triage ledger line {lineno} has no 'id'")
        out[key] = rec
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("backlog", type=Path,
                   help="markdown backlog with - [ ] / [~] / [!] rows")
    p.add_argument("--triage", type=Path, default=None,
                   help="JSONL triage ledger (id, disposition, reason, review_by)")
    p.add_argument("--max-age-days", type=int, default=14,
                   help="age beyond which an open item needs a triage disposition")
    p.add_argument("--today", default=None,
                   help="override today's date (ISO) for deterministic tests")
    args = p.parse_args()

    if not args.backlog.exists():
        print(f"FATAL: backlog not found: {args.backlog}", file=sys.stderr)
        return EXIT_USAGE

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    rows, problems = parse_rows(args.backlog)
    if not rows and not problems:
        print("FATAL: no open rows parsed — refusing to report a vacuous pass",
              file=sys.stderr)
        return EXIT_EMPTY

    triage = load_triage(args.triage)
    violations = list(problems)
    stats = {"open": len(rows), "aged": 0, "triaged": 0, "expired_deferral": 0}

    for r in rows:
        if r["date"] is None:
            continue  # already reported
        age = (today - r["date"]).days
        if age <= args.max_age_days:
            continue
        stats["aged"] += 1
        key = r["id"]
        rec = triage.get(key) if key else None
        if not rec:
            violations.append(
                f"{key or 'line ' + str(r['line'])}: open {age}d > {args.max_age_days}d "
                f"with no triage disposition — {r['text']}")
            continue
        disp = (rec.get("disposition") or "").lower()
        if disp not in ("fixed", "deferred", "not-actionable"):
            violations.append(
                f"{key}: invalid disposition {disp!r} "
                f"(expected fixed|deferred|not-actionable)")
            continue
        stats["triaged"] += 1
        if disp == "deferred":
            review_by = rec.get("review_by")
            if not review_by:
                violations.append(
                    f"{key}: deferred without review_by — deferral must expire")
                continue
            try:
                rb = dt.date.fromisoformat(str(review_by))
            except ValueError:
                violations.append(f"{key}: deferred with unparseable review_by "
                                  f"{review_by!r}")
                continue
            if rb < today:
                stats["expired_deferral"] += 1
                violations.append(
                    f"{key}: deferred review_by {rb} has passed — re-triage required")
            if not rec.get("reason"):
                violations.append(f"{key}: deferred without a reason")

    print(f"open rows: {stats['open']} | aged >{args.max_age_days}d: {stats['aged']} "
          f"| triaged: {stats['triaged']} | expired deferrals: {stats['expired_deferral']}")

    if violations:
        print(f"\n{len(violations)} violation(s):", file=sys.stderr)
        for v in violations[:60]:
            print(f"  {v}", file=sys.stderr)
        if len(violations) > 60:
            print(f"  ... and {len(violations) - 60} more", file=sys.stderr)
        return EXIT_VIOLATION

    print("OK: every aged open item carries a live triage disposition")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
