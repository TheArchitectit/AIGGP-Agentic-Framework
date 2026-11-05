#!/usr/bin/env python3
"""secret_rotation_check.py — a scrubbed secret is not a revoked secret.

WHY THIS EXISTS (measured, not theoretical)
The suite detects secrets three ways and all three are wired: `secret-scan.sh` (push
path), `secret-scan-declared.sh`, `secret-scan-fleet.sh`. Detection is not the gap.

The gap is what happens *after* detection. Across 67 days of the digest open-items
ledger (`ai-news/nextday-actions.md`, 2026-08-27 -> 2026-11-05) the secret/key family
appears on **26 of 67 days (39%)**, and the corpus names the exact failure:

    2026-09-01  "Verify the vision API key scrubbed from Project N34 was rotated/revoked
                 at the provider, and check git history for the old value."
    2026-09-03  "Rotate and revoke the vision API key scrubbed from Project N34 —
                 removing it from HEAD leaves it in git history."

That is the whole argument. Removing a key from `HEAD` does two things it does not do:
it does not revoke the key at the provider, and it does not remove it from history. A
repo can be scan-clean and still hold a live credential in a reachable commit.

Grep confirms the absence: `grep -rlniE 'rotate|revoke' scripts/secret-scan*.sh` returns
nothing. Rotating credentials is tracked only in prose, in a markdown backlog.

CONTRACT
  An append-only rotation ledger (`secret-rotation.jsonl`) records, per detection:
    id             stable identifier (fingerprint of the secret family + first-seen)
    family         e.g. "openai-key", "aws-access-key", "generic-bearer"
    first_seen     commit sha + date where found
    removed_from_head   bool
    revoked            bool
    revoked_at         date revoked at the provider
    evidence           pointer to the revocation record (ticket, console screenshot id)
    history_purged     bool

  The gate fails when:
    1. `removed_from_head` is true but `revoked` is false and first_seen is older than
       --max-unrevoked-days (default 7). Scrubbing without revoking is the exact N34 bug.
    2. `revoked` is true but `revoked_at` or `evidence` is missing. An unrecorded
       revocation is indistinguishable from a claimed one.
    3. `removed_from_head` is false for any entry older than --max-unrevoked-days: the
       secret is still committed.
    4. A required field is absent — a malformed row cannot be partially trusted.
    5. Zero entries is fine (nothing detected yet). Zero *parsed* lines from a non-empty
       file is a failure.

Exit codes: 0 pass | 1 violation | 2 usage/config error | 3 nothing scanned
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

EXIT_OK, EXIT_VIOLATION, EXIT_USAGE, EXIT_EMPTY = 0, 1, 2, 3
REQUIRED = ("id", "family", "first_seen", "removed_from_head", "revoked")


def load(path: Path) -> list[dict]:
    entries = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            raise SystemExit(f"FATAL: line {lineno} is not JSON: {e}")
        missing = [k for k in REQUIRED if k not in rec]
        if missing:
            raise SystemExit(f"FATAL: line {lineno} missing required field(s): {missing}")
        rec["_line"] = lineno
        entries.append(rec)
    return entries


def as_date(v, field: str, lineno: int) -> dt.date:
    try:
        return dt.date.fromisoformat(str(v))
    except (ValueError, TypeError):
        raise SystemExit(f"FATAL: line {lineno} has unparseable {field}: {v!r}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ledger", type=Path, help="secret-rotation.jsonl")
    p.add_argument("--max-unrevoked-days", type=int, default=7)
    p.add_argument("--today", default=None)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if not args.ledger.exists():
        print(f"FATAL: ledger not found: {args.ledger}", file=sys.stderr)
        return EXIT_USAGE
    raw = args.ledger.read_text(encoding="utf-8")
    if not raw.strip():
        print("OK: empty rotation ledger — no detections recorded yet")
        return EXIT_OK

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    entries = load(args.ledger)
    if not entries:
        print("FATAL: ledger is non-empty but no rows parsed — refusing a vacuous pass",
              file=sys.stderr)
        return EXIT_EMPTY

    violations = []
    stats = {"total": len(entries), "unrevoked": 0, "still_committed": 0,
             "missing_evidence": 0}

    for e in entries:
        eid = e["id"]
        seen = as_date(e["first_seen"], "first_seen", e["_line"])
        age = (today - seen).days
        removed = bool(e["removed_from_head"])
        revoked = bool(e["revoked"])

        if not removed and age > args.max_unrevoked_days:
            stats["still_committed"] += 1
            violations.append(
                f"{eid}: still in HEAD after {age}d — the secret is live in the tree")
            continue

        if removed and not revoked:
            if age > args.max_unrevoked_days:
                stats["unrevoked"] += 1
                violations.append(
                    f"{eid}: scrubbed from HEAD {age}d ago but never revoked at the "
                    f"provider — scrubbing is not revocation (N34 pattern)")
            continue

        if revoked:
            missing = [f for f in ("revoked_at", "evidence") if not e.get(f)]
            if missing:
                stats["missing_evidence"] += 1
                violations.append(
                    f"{eid}: revoked=true but missing {missing} — an unrecorded "
                    f"revocation cannot be distinguished from a claimed one")
                continue
            try:
                dt.date.fromisoformat(str(e["revoked_at"]))
            except ValueError:
                violations.append(f"{eid}: revoked_at unparseable ({e['revoked_at']!r})")

    if args.json:
        print(json.dumps({"stats": stats, "violations": violations}, indent=1))
    else:
        print(f"entries: {stats['total']} | unrevoked: {stats['unrevoked']} "
              f"| still committed: {stats['still_committed']} "
              f"| missing evidence: {stats['missing_evidence']}")
        if violations:
            print(f"\n{len(violations)} violation(s):", file=sys.stderr)
            for v in violations:
                print(f"  {v}", file=sys.stderr)

    return EXIT_VIOLATION if violations else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
