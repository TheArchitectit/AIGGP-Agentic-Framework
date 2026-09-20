# Benchmarks — coding-agent evaluation harness

A permanent, repeatable corpus of realistic engineering tasks plus a harness
that runs an actual solver (an agent CLI, a patch, a human) against isolated
copies and scores **repository outcomes, not prose**.

## Layout

```
.benchmarks/
├── harness.py      # runner: isolate -> control-check -> solve -> hidden verify
├── metrics.py      # aggregate JSONL into pass rates + failure taxonomy
└── tasks/<id>/     # one directory per task
    ├── task.json   # id, category, description, verify_cmd, verify_timeout_sec
    ├── repo/       # the (broken) starting repository — the ONLY thing a
    │               #   solver ever sees
    ├── verify/     # HIDDEN behavioral checks — never shown to the solver
    └── solution/   # golden solution (demo solver; proves the loop works)
```

## Evaluator-integrity rules

1. **Control validation.** Before scoring any solver, the harness runs the
   hidden verifier against the *unsolved* repo. A verifier that passes on
   the broken state invalidates the task (`VERIFY_PASSED_ON_BROKEN`) —
   results are refused rather than reported.
2. **Isolation.** Each run gets a fresh copy of `repo/`; runs cannot
   contaminate each other, and the task definition cannot be edited by the
   solver (it is outside the copy).
3. **Repositories, not prose.** The only success signal is the hidden
   verifier's exit status. Solver output is logged, never interpreted.
4. **Verifier contract.** Hidden checks receive the repo under test as
   `argv[1]` — grading a tree by relative-position guesswork silently
   verified the wrong tree once already (that bug is why the contract
   exists).

## Usage

```bash
# List the corpus
python3 .benchmarks/harness.py --list

# Validate the loop with the golden solutions (all tasks must PASS)
python3 .benchmarks/harness.py --all \
    --solver "python3 {task_dir}/solution/solve.py {repo_dir}"

# Prove the corpus detects work: a no-op solver must fail every task
python3 .benchmarks/harness.py --all --solver "true"

# Run your agent
python3 .benchmarks/harness.py --all \
    --solver "your-agent-cli --workdir {repo_dir} --goal {task_description}" \
    --jsonl-out results/$(date -u +%Y%m%dT%H%M%SZ).jsonl

# Aggregate
python3 .benchmarks/metrics.py results/20260920T….jsonl
```

## Corpus

| task | category | defect class |
|------|----------|--------------|
| t01-off-by-one | bug_fix | boundary/off-by-one in pagination |
| t02-feature-env-bool | feature | implement to spec, strict validation |
| t03-refactor-dedupe | refactoring | deduplicate, preserve behavior |
| t04-path-traversal | security | containment check on file serving |
| t05-bounded-retry | reliability | unbounded retry loop (hangs when broken) |
| t06-cli-exit-codes | bug_fix | CLI contract: exit codes |
| t07-counter-race | reliability | lost updates: unlocked read-modify-write (deterministic contention window) |
| t08-config-precedence | bug_fix | merge order: env must beat file; empty-string env still counts |
| t09-idempotent-apply | reliability | retry compounding via caller-dict mutation; idempotency-state contract |
| t10-command-injection | security | shell interpolation -> argv list + name whitelist |
| t11-corrupt-state-recovery | reliability | tolerate a truncated TRAILING journal line, never mid-file corruption |
| t12-multifile-ratelimiter | feature | new module + wiring into existing client (multi-file) |

Adding a task: create `tasks/<id>/repo/` (broken), `tasks/<id>/verify/check.py`
(argv[1] = repo; exit 0 = requirement met), `task.json`. Then prove both
directions: the no-op solver run must fail it, the golden solution must pass.

Isolation contract (fw-bench-02): the harness gives EVERY phase a fresh
copy — control, solve, and verify never share a tree, because a broken
implementation or a solver can leave side effects that would otherwise
poison the next phase's verdict.
