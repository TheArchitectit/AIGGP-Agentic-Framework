#!/usr/bin/env python3
"""surface_reach_check.py — a fix that reached one surface did not reach them all.

WHY THIS EXISTS (measured, not theoretical)
Across 67 days of the digest open-items ledger (`ai-news/nextday-actions.md`,
2026-08-27 -> 2026-11-05), the verify/not-verified family is the single most persistent:
**59 of 67 days (88%), with a 19-day unbroken streak.** Concrete instances:

    2026-09-01  "Verify Alpha's dashboards fix reached both build surfaces; file the gap
                 if not."
    2026-09-01  "Epsilon keyboard-interaction fix — confirm the sheet surface fix landed
                 in the shared UI component across machines."
    2026-09-01  "Verify the Rho/N2 shared-core mirror pair is in the cross-check harness
                 config coverage."
    2026-09-01  "DevGate vendored mirror — stand up a drift check against the pinned
                 upstream revision."

The pattern is identical in every instance: work is declared done on the surface the
author was looking at, and nothing checks whether the other declared surfaces received it.

`check_manifest_join.py` already proves "declared ⇄ written" for one repo. This gate
generalises it from one surface to N declared surfaces of the same artifact.

WHY IT CANNOT BE FIXED BY DISCIPLINE
Remembering which surfaces exist is exactly the human step that fails 59 days out of 67.
The declaration has to be machine-readable and the comparison mechanical.

CONTRACT
  A surface manifest (`surfaces.json`) declares artifact groups:

    {"groups": [
       {"name": "shared-ui-sheet",
        "paths": ["/mnt/data/git/ui-a/src/Sheet.tsx",
                  "/mnt/data/git/ui-b/src/Sheet.tsx"]},
       {"name": "n2-mirror",
        "paths": ["/mnt/data/git/n2/crates/core/src/lib.rs",
                  "/mnt/data/git/n2-mirror/src/lib.rs"],
        "compare": "hash"}
    ]}

  For each group:
    * every declared path must exist — a missing surface is a failure, not a skip
      (a surface that vanished is the loudest possible "did not reach it")
    * with `"compare": "hash"` (default), every path's content hash must match; a
      mismatch means one surface received the change and another did not
    * with `"compare": "exists"`, presence alone is checked (for generated artifacts)

Exit codes: 0 all surfaces agree | 1 divergence | 2 usage/config error | 3 nothing scanned
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

EXIT_OK, EXIT_DIVERGE, EXIT_USAGE, EXIT_EMPTY = 0, 1, 2, 3


def digest(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("manifest", type=Path, help="surfaces.json")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if not args.manifest.exists():
        print(f"FATAL: manifest not found: {args.manifest}", file=sys.stderr)
        return EXIT_USAGE
    try:
        doc = json.loads(args.manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"FATAL: manifest is not valid JSON: {e}", file=sys.stderr)
        return EXIT_USAGE

    groups = doc.get("groups") or []
    if not groups:
        print("FATAL: manifest declares no groups — refusing a vacuous pass",
              file=sys.stderr)
        return EXIT_EMPTY

    violations, checked = [], 0
    report = []

    for g in groups:
        name = g.get("name") or "(unnamed)"
        paths = [Path(x) for x in (g.get("paths") or [])]
        mode = (g.get("compare") or "hash").lower()
        if len(paths) < 2:
            violations.append(f"{name}: declares {len(paths)} path(s) — a surface "
                              f"comparison needs at least 2")
            continue

        missing = [str(x) for x in paths if not x.exists()]
        if missing:
            violations.append(f"{name}: {len(missing)} declared surface(s) missing: "
                              f"{missing[:3]}")
            report.append({"group": name, "mode": mode, "missing": missing})
            continue

        if mode == "exists":
            checked += len(paths)
            report.append({"group": name, "mode": mode, "paths": len(paths), "ok": True})
            continue

        hashes = {}
        for x in paths:
            try:
                hashes[str(x)] = digest(x)
            except OSError as e:
                violations.append(f"{name}: cannot read {x}: {e}")
        checked += len(hashes)
        distinct = set(hashes.values())
        if len(distinct) > 1:
            # name the odd-one-out so the fix is obvious
            counts = {h: list(hashes.values()).count(h) for h in distinct}
            majority = max(counts, key=counts.get)
            odd = [k for k, v in hashes.items() if v != majority]
            violations.append(
                f"{name}: {len(distinct)} distinct contents across {len(paths)} surfaces "
                f"— not reached: {odd[:3]}")
        report.append({"group": name, "mode": mode, "surfaces": len(paths),
                       "distinct_hashes": len(distinct)})

    if args.json:
        print(json.dumps({"groups": len(groups), "surfaces_checked": checked,
                          "violations": violations, "report": report}, indent=1))
    else:
        print(f"groups: {len(groups)} | surfaces checked: {checked} "
              f"| divergences: {len(violations)}")
        for r in report:
            state = "OK" if not r.get("missing") and r.get("distinct_hashes", 1) == 1 else "!!"
            print(f"  [{state}] {r['group']}: {r.get('surfaces', r.get('paths', 0))} surface(s), "
                  f"mode={r['mode']}"
                  + (f", distinct={r['distinct_hashes']}" if "distinct_hashes" in r else ""))
        if violations:
            print(f"\n{len(violations)} violation(s):", file=sys.stderr)
            for v in violations:
                print(f"  {v}", file=sys.stderr)

    return EXIT_DIVERGE if violations else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
