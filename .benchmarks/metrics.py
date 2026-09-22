#!/usr/bin/env python3
"""metrics.py — aggregate benchmark JSONL records into an honest summary.

Reads the JSONL emitted by harness.py (--jsonl-out) and reports:
  - per-task pass/fail counts and consistency across repeated runs
  - the failure-taxonomy breakdown (repositories, not prose)
  - wall-clock statistics

Honesty rules (fw-bench-*):
  - "A task that succeeds once is not a reliably solved task": pass_rate is
    reported alongside trial counts, and consistency flags tasks with
    mixed outcomes instead of averaging them away.
  - Invalid tasks (verifier passed on broken state) poison the corpus:
    they are surfaced at the top, never folded into the rate.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_records(path: str) -> list:
    records = []
    with open(path, encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"metrics: skipping line {ln}: {e}", file=sys.stderr)
    return records


def summarize(records: list) -> dict:
    by_task = {}
    for r in records:
        by_task.setdefault(r["task"], []).append(r)

    invalid = sorted(t for t, rs in by_task.items()
                     if any(x["status"] == "VERIFY_PASSED_ON_BROKEN"
                            for x in rs))
    tasks = {}
    for task, rs in sorted(by_task.items()):
        passes = sum(1 for x in rs if x["status"] == "PASS")
        walls = [x["wall_sec"] for x in rs if "wall_sec" in x]
        taxonomy = {}
        for x in rs:
            cls = x.get("classification", "unknown")
            taxonomy[cls] = taxonomy.get(cls, 0) + 1
        tasks[task] = {
            "trials": len(rs),
            "passes": passes,
            "pass_rate": round(passes / len(rs), 3) if rs else 0.0,
            "consistent": passes in (0, len(rs)),
            "taxonomy": taxonomy,
            "wall_sec_avg": round(sum(walls) / len(walls), 3) if walls else None,
        }

    total = sum(t["trials"] for t in tasks.values())
    passes = sum(t["passes"] for t in tasks.values())
    return {
        "runs": len(records),
        "tasks": len(tasks),
        "invalid_tasks": invalid,
        "overall_pass_rate": round(passes / total, 3) if total else 0.0,
        "per_task": tasks,
    }


def main() -> int:
    ap = argparse.ArgumentParser(prog="metrics",
                                 description="aggregate benchmark JSONL")
    ap.add_argument("jsonl", help="records file from harness.py --jsonl-out")
    ap.add_argument("--json", action="store_true", help="emit JSON summary")
    args = ap.parse_args()
    if not Path(args.jsonl).is_file():
        print(f"metrics: no such file: {args.jsonl}", file=sys.stderr)
        return 30
    summary = summarize(load_records(args.jsonl))
    if args.json:
        print(json.dumps(summary, indent=1))
    else:
        print(f"runs: {summary['runs']}  tasks: {summary['tasks']}  "
              f"overall pass rate: {summary['overall_pass_rate']:.1%}")
        if summary["invalid_tasks"]:
            print(f"INVALID TASKS (fix their hidden verifiers): "
                  f"{', '.join(summary['invalid_tasks'])}")
        for task, t in summary["per_task"].items():
            flag = "" if t["consistent"] else "  [INCONSISTENT across trials]"
            tax = " ".join(f"{k}={v}" for k, v in sorted(t["taxonomy"].items()))
            print(f"  {task:28s} {t['passes']}/{t['trials']} passed "
                  f"({t['wall_sec_avg']}s avg)  {tax}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
