#!/usr/bin/env python3
"""resource_audit.py — measure a command's actual resource consumption.

Runs a command as a child process and reports wall time, CPU time (user+sys
of the child), peak RSS, and voluntary/involuntary context switches when the
platform exposes them. Output is a single JSON object on stdout so it can be
consumed by pipelines and budgets.

This is the measurement half of resource governance (fw-res-*): you cannot
cap what you cannot see. Pair it with hub/coherence/resource_limits.py,
which enforces budgets.

Exit codes: the child's exit code (0-255); measurement failures map to 30.

Usage:
  python3 scripts/resource_audit.py -- python3 -m pytest tests/ -q
  python3 scripts/resource_audit.py --budget-seconds 120 -- make test
"""
from __future__ import annotations

import argparse
import json
import resource
import subprocess
import sys
import time

EXIT_USAGE = 30


def measure(cmd: list, timeout: float) -> dict:
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    t0 = time.monotonic()
    stopped = None
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        exit_ = r.returncode
        stdout = (r.stdout or b"")[-2000:].decode("utf-8", errors="replace")
        stderr = (r.stderr or b"")[-2000:].decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as e:
        exit_ = None
        stopped = f"timeout after {timeout}s"
        stdout = (e.stdout or b"")[-2000:].decode("utf-8", errors="replace")
        stderr = ((e.stderr or b"") + b"[timed out]")[-2000:].decode(
            "utf-8", errors="replace")
    wall = time.monotonic() - t0
    after = resource.getrusage(resource.RUSAGE_CHILDREN)

    report = {
        "cmd": cmd,
        "exit": exit_,
        "stopped": stopped,
        "wall_sec": round(wall, 3),
        # RUSAGE_CHILDREN accumulates over ALL waited-for children of this
        # process; the delta isolates the measured child (best available
        # without platform-specific /proc scraping).
        "cpu_user_sec": round(after.ru_utime - before.ru_utime, 3),
        "cpu_sys_sec": round(after.ru_stime - before.ru_stime, 3),
        "peak_rss_kb": after.ru_maxrss,  # cumulative max across children
        "context_switches_voluntary":
            after.ru_nvcsw - before.ru_nvcsw,
        "context_switches_involuntary":
            after.ru_nivcsw - before.ru_nivcsw,
        "stdout_tail": stdout,
        "stderr_tail": stderr,
    }
    return report


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="resource_audit",
        description="measure a command's wall/CPU/memory consumption")
    ap.add_argument("--budget-seconds", type=float, default=600.0,
                    help="hard timeout for the child (default 600)")
    # REMAINDER (not nargs="+"): the child command carries its own flags
    # (e.g. python -c "..."), which argparse would otherwise try to parse.
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="command to measure")
    args = ap.parse_args()

    if not args.cmd:
        print("resource_audit: no command given", file=sys.stderr)
        return EXIT_USAGE

    report = measure(args.cmd, args.budget_seconds)
    print(json.dumps(report, indent=1))
    if report["exit"] is None:
        return EXIT_USAGE  # stopped children are a governance event
    return max(0, min(255, report["exit"]))


if __name__ == "__main__":
    sys.exit(main())
