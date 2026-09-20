#!/usr/bin/env python3
"""multi_solver.py — independent / multi-strategy evaluation (fw-ms-*).

Runs the SAME benchmark task through multiple solver strategies on isolated
copies of the same starting repository, then compares REPOSITORY OUTCOMES
(hidden verification), never prose. Strategies that fail differently expose
blind spots a single strategy systematically misses; strategies that fail
IDENTICALLY expose architecture, not models (anti-correlation analysis).

A shipped GAMING strategy (strategies/hardcode_t02.py) doubles as an
evaluator-integrity negative control: it must FAIL the strengthened hidden
checks. If it passes, the hidden verification got weaker — fix the task.

Usage:
  python3 .benchmarks/multi_solver.py --task t01-off-by-one \
      --strategy golden=... --strategy noop="true"
  python3 .benchmarks/multi_solver.py --all --strategy golden="..."

Exit codes: 0 all outcomes as expected by the matrix; 1 discrepancies.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))

from harness import discover_tasks, run_task  # noqa: E402

EXIT_OK = 0
EXIT_DISCREPANCY = 1
EXIT_USAGE = 30


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="multi_solver",
        description="compare solver strategies by repository outcomes")
    ap.add_argument("--task")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--strategy", action="append", required=True,
                    metavar="NAME=COMMAND",
                    help="solver strategy; {repo_dir}/{task_dir}/"
                         "{task_description} substituted")
    ap.add_argument("--gaming-demo", action="store_true",
                    help="run the shipped gaming negative control on t02")
    ap.add_argument("--timeout", type=float, default=300.0)
    args = ap.parse_args()

    strategies = {}
    for s in args.strategy:
        name, _, cmd = s.partition("=")
        if not cmd:
            print(f"multi_solver: --strategy needs NAME=COMMAND, got {s!r}",
                  file=sys.stderr)
            return EXIT_USAGE
        strategies[name] = cmd

    tasks = discover_tasks()
    if args.all:
        selected = tasks
    elif args.task:
        selected = [(d, m) for d, m in tasks
                    if m.get("id") == args.task or d.name == args.task]
        if not selected:
            print(f"multi_solver: unknown task {args.task!r}", file=sys.stderr)
            return EXIT_USAGE
    else:
        ap.error("one of --task / --all / --gaming-demo is required")

    if args.gaming_demo:
        strategies["GAMING-hardcode"] = \
            f"python3 {BENCH}/strategies/hardcode_t02.py {{repo_dir}}"
        if not selected:
            selected = [(d, m) for d, m in tasks
                        if m.get("id") == "t02-feature-env-bool"]

    # outcomes[task][strategy] = status
    outcomes = {}
    for task_dir, meta in selected:
        tid = meta.get("id", task_dir.name)
        outcomes[tid] = {}
        for name, cmd in strategies.items():
            r = run_task(task_dir, meta, cmd, args.timeout)
            outcomes[tid][name] = r["status"]
            print(f"  {tid:26s} {name:20s} -> {r['status']}")

    # --- analysis ----------------------------------------------------------
    discrepancies = []

    # 1. Consistency: identical input, different outcomes per strategy are
    #    information (strategy X fails where Y succeeds); note them.
    print("\ncomparison matrix (repository outcomes):")
    for tid, per in outcomes.items():
        print(f"  {tid}: " +
              ", ".join(f"{n}={s}" for n, s in per.items()))
        statuses = set(per.values())
        if len(statuses) > 1:
            passed = [n for n, s in per.items() if s == "PASS"]
            failed = [n for n, s in per.items() if s != "PASS"]
            print(f"    -> strategy divergence: {'/'.join(passed) or '-'} "
                  f"pass where {'/'.join(failed) or '-'} fail "
                  f"(failure-diversity signal)")

    # 2. Anti-correlation: a task failing under EVERY strategy is systemic —
    #    the problem is the task or the architecture, not any one solver.
    for tid, per in outcomes.items():
        if per and all(s != "PASS" for s in per.values()):
            discrepancies.append(
                f"{tid} fails under EVERY strategy — systemic: inspect the "
                f"task/verifier or the shared architecture before blaming "
                f"any solver")

    # 3. Gaming controls must never pass.
    for tid, per in outcomes.items():
        for n, s in per.items():
            if n.startswith("GAMING-") and s == "PASS":
                discrepancies.append(
                    f"{tid}: GAMING strategy {n} PASSED — the hidden "
                    f"verification accepted gaming; strengthen the task")

    if discrepancies:
        print("\nmulti-solver findings:")
        for d in discrepancies:
            print(f"  ✗ {d}")
        return EXIT_DISCREPANCY
    print("\nmulti-solver: no systemic failures; gaming controls (if run) "
          "correctly rejected")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
