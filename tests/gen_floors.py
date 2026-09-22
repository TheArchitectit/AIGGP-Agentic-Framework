#!/usr/bin/env python3
"""Regenerate tests/expected-counts.json from the current suite (--update)."""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "tests" / "expected-counts.json"


def collect():
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/",
                        "--collect-only", "-q"], cwd=str(REPO),
                       capture_output=True, text=True)
    counts = {}
    for line in r.stdout.splitlines():
        if "::" in line and ".py" in line:
            tf = line.split("::")[0].replace("tests/", "").replace(".py", "")
            counts[tf] = counts.get(tf, 0) + 1
    return counts


def main() -> int:
    update = "--update" in sys.argv
    doc = json.loads(OUT.read_text()) if OUT.exists() else {}
    counts = collect()
    problems = []
    for suite, floor in (doc.get("floors") or {}).items():
        got = counts.get(suite, 0)
        if got < floor:
            problems.append(f"{suite}: {got} collected < floor {floor}")
    total = sum(counts.values())
    total_floor = doc.get("total_floor", 0)
    if total < total_floor:
        problems.append(f"TOTAL: {total} < floor {total_floor}")
    if update:
        floors = {k: max(1, int(v * 0.9)) for k, v in sorted(counts.items())}
        OUT.write_text(json.dumps(
            {"note": doc.get("note", ""), "floors": floors,
             "total_floor": int(total * 0.9)}, indent=1) + "\n")
        print(f"floors regenerated: {len(floors)} suites, total {total}")
        return 0
    if problems:
        print("test-floor: FAIL — silent suite shrinkage:")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"test-floor: OK — {len(counts)} suites, {total} tests "
          f"(floors hold)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
