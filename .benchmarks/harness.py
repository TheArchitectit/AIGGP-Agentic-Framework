#!/usr/bin/env python3
"""harness.py — coding-agent benchmark harness (fw-bench-*).

Runs a SOLVER (any command that edits a repository directory: an agent CLI,
a patch applier, a human following instructions) against an isolated copy of
a task repository, then applies HIDDEN behavioral verification that lives
outside the repository the solver saw.

Evaluator-integrity rules baked into the runner:
  1. CONTROL VALIDATION — before scoring any solver, the harness runs the
     hidden verifier against the UNSOLVED repository. A task whose verifier
     passes on the broken state is an INVALID task (it cannot detect work);
     the harness refuses to score it.
  2. ISOLATION — the solver works on a fresh copy per run; runs cannot
     contaminate each other or the task definition.
  3. MEASURE REPOSITORIES, NOT PROSE — the only success signal is the
     hidden verifier's exit status plus recorded metrics. Solver stdout is
     logged for debugging, never interpreted.

Usage:
  python3 .benchmarks/harness.py --list
  python3 .benchmarks/harness.py --task t01-off-by-one \
      --solver "git apply {patch}" --patch reference.patch
  python3 .benchmarks/harness.py --all --solver "<agent-cli> {repo_dir}"

Solver command contract: `{repo_dir}` (and optionally `{task_description}`)
are substituted; the command runs with cwd=the isolated repo copy and must
leave its changes on disk there.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BENCH_ROOT = Path(__file__).resolve().parent
TASKS_ROOT = BENCH_ROOT / "tasks"

EXIT_OK = 0
EXIT_TASK_FAILED = 1
EXIT_INVALID_TASK = 2
EXIT_USAGE = 30

# Failure taxonomy (fw-bench-taxonomy): every non-pass is classified.
TAXONOMY = {
    "VERIFY_PASSED_ON_BROKEN": "invalid-task",
    "SOLVER_COMMAND_FAILED": "solver-failure",
    "VERIFY_FAILED": "implementation-failure",
    "VERIFY_TIMEOUT": "resource-failure",
    "VERIFY_CRASHED": "evaluator-failure",
}


def discover_tasks() -> list:
    out = []
    if not TASKS_ROOT.is_dir():
        return out
    for task_dir in sorted(TASKS_ROOT.iterdir()):
        spec = task_dir / "task.json"
        if spec.is_file():
            try:
                meta = json.loads(spec.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                print(f"harness: skipping {task_dir.name}: bad task.json: {e}",
                      file=sys.stderr)
                continue
            out.append((task_dir, meta))
    return out


def run_verifier(verify_cmd: list, repo: Path, timeout: float):
    """Run hidden verification against the repo copy.

    The repo under test is passed as argv[1]: a verifier that resolves the
    repo by its own relative position would silently grade the ORIGINAL
    task tree instead of the isolated copy — verdicts that look meaningful
    and are not (found by this harness's own control validation).
    """
    cmd = verify_cmd + [str(repo)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, cwd=str(repo))
    except subprocess.TimeoutExpired:
        return "TIMEOUT", f"verifier exceeded {timeout}s"
    except OSError as e:
        return "CRASHED", str(e)
    if r.returncode == 0:
        return "PASS", "hidden verification passed"
    detail = (r.stderr or r.stdout or "").strip().splitlines()
    return "FAIL", detail[-1][:200] if detail else f"exit {r.returncode}"


def load_verify_cmd(task_dir: Path, meta: dict) -> list:
    """Resolve the hidden verifier into an executable command.

    Relative paths resolve against the TASK dir (the verifier lives outside
    the repo copy so the solver never sees it). A .py entry point is executed
    with the current interpreter — task definitions must not depend on the
    exec bit or a shebang.
    """
    cmd = meta.get("verify_cmd")
    if not cmd:
        raise ValueError(f"{task_dir.name}: task.json missing verify_cmd")
    resolved = []
    for i, part in enumerate(cmd):
        if i == 0 and not Path(part).is_absolute():
            p = task_dir / part
            resolved.append(str(p))
        else:
            resolved.append(part)
    if resolved[0].endswith(".py"):
        resolved = [sys.executable] + resolved
    return resolved


def run_task(task_dir: Path, meta: dict, solver_cmd: str, timeout: float,
             keep: bool = False) -> dict:
    """One benchmark run: isolate -> solve -> verify -> metrics."""
    t0 = time.monotonic()
    workdir = Path(tempfile.mkdtemp(prefix=f"bench-{task_dir.name}-"))
    record = {
        "task": meta.get("id", task_dir.name),
        "category": meta.get("category", "uncategorized"),
        "solver": solver_cmd,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        repo = workdir / "repo"
        shutil.copytree(task_dir / "repo", repo)

        verify_cmd = load_verify_cmd(task_dir, meta)
        # Per-task verifier timeout (verify_timeout_sec): tasks whose broken
        # behavior HANGS (runaway loops, deadlocks) would otherwise burn the
        # full default timeout during control validation.
        vtimeout = float(meta.get("verify_timeout_sec", timeout))

        # CONTROL: the hidden verifier must FAIL on the unsolved repo.
        # The control runs on ITS OWN copy: a broken implementation can
        # leave side effects (created files, partial state), and those must
        # never leak into the phase that grades the solver.
        control_repo = workdir / "repo-control"
        shutil.copytree(task_dir / "repo", control_repo)
        control_status, control_detail = run_verifier(
            verify_cmd, control_repo, vtimeout)
        record["control_status"] = control_status
        if control_status == "PASS":
            record["status"] = "VERIFY_PASSED_ON_BROKEN"
            record["classification"] = TAXONOMY["VERIFY_PASSED_ON_BROKEN"]
            record["detail"] = ("hidden verifier cannot detect the defect; "
                                "task is invalid")
            return record
        if control_status == "CRASHED":
            record["status"] = "VERIFY_CRASHED"
            record["classification"] = TAXONOMY["VERIFY_CRASHED"]
            record["detail"] = control_detail
            return record

        # SOLVE: the command edits the repo copy; stdout is logged, never
        # interpreted (fw-bench-noprose).
        cmd = (solver_cmd
               .replace("{repo_dir}", str(repo))
               .replace("{task_dir}", str(task_dir))
               .replace("{task_description}",
                        meta.get("description", "").replace("'", "")))
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True,
                               text=True, timeout=timeout, cwd=str(repo))
            record["solver_exit"] = r.returncode
            record["solver_output_tail"] = \
                (r.stdout + r.stderr).strip()[-400:]
            solver_ok = r.returncode == 0
        except subprocess.TimeoutExpired:
            solver_ok = False
            record["solver_exit"] = "TIMEOUT"
        if not solver_ok:
            record["status"] = "SOLVER_COMMAND_FAILED"
            record["classification"] = TAXONOMY["SOLVER_COMMAND_FAILED"]
            record["detail"] = "solver command did not complete cleanly"
            return record

        # VERIFY: hidden behavioral check on the solved copy.
        status, detail = run_verifier(verify_cmd, repo, vtimeout)
        record["verify_status"] = status
        record["detail"] = detail
        if status == "PASS":
            record["status"] = "PASS"
            record["classification"] = "pass"
        elif status == "TIMEOUT":
            record["status"] = "VERIFY_TIMEOUT"
            record["classification"] = TAXONOMY["VERIFY_TIMEOUT"]
        else:
            record["status"] = "VERIFY_FAILED"
            record["classification"] = TAXONOMY["VERIFY_FAILED"]
        record["wall_sec"] = round(time.monotonic() - t0, 3)
        return record
    finally:
        if keep:
            print(f"harness: workdir kept at {workdir}", file=sys.stderr)
        else:
            shutil.rmtree(workdir, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(prog="harness",
                                 description="coding-agent benchmark harness")
    ap.add_argument("--task", help="task id to run")
    ap.add_argument("--all", action="store_true", help="run every task")
    ap.add_argument("--solver", required=True,
                    help="solver command; {repo_dir} and {task_description} "
                         "are substituted")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--keep", action="store_true",
                    help="keep the isolated workdir for debugging")
    ap.add_argument("--jsonl-out", help="append one JSON record per run")
    args = ap.parse_args()

    tasks = discover_tasks()
    if args.list:
        for task_dir, meta in tasks:
            print(f"{meta.get('id', task_dir.name):32s} "
                  f"{meta.get('category', '?'):12s} "
                  f"{meta.get('description', '')[:60]}")
        return EXIT_OK
    if not tasks:
        print("harness: no tasks found", file=sys.stderr)
        return EXIT_USAGE

    if args.all:
        selected = tasks
    elif args.task:
        selected = [(d, m) for d, m in tasks
                    if m.get("id") == args.task or d.name == args.task]
        if not selected:
            print(f"harness: unknown task {args.task!r}", file=sys.stderr)
            return EXIT_USAGE
    else:
        ap.error("one of --task / --all / --list is required")

    invalid = 0
    failed = 0
    out_fp = open(args.jsonl_out, "a") if args.jsonl_out else None
    try:
        for task_dir, meta in selected:
            record = run_task(task_dir, meta, args.solver, args.timeout,
                              keep=args.keep)
            line = json.dumps(record)
            if out_fp:
                out_fp.write(line + "\n")
            print(line)
            if record["status"] in ("VERIFY_PASSED_ON_BROKEN", "VERIFY_CRASHED"):
                invalid += 1
            elif record["status"] != "PASS":
                failed += 1
    finally:
        if out_fp:
            out_fp.close()

    if invalid:
        print(f"harness: {invalid} INVALID task(s) — fix the hidden "
              f"verifier; results are not meaningful", file=sys.stderr)
        return EXIT_INVALID_TASK
    return EXIT_OK if failed == 0 else EXIT_TASK_FAILED


if __name__ == "__main__":
    sys.exit(main())
