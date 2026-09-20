# DevGate Audit Methodology

The 16-prompt audit methodology — full-system audit, adversarial attack,
production torture, architecture review, autonomy/recovery, release
hardening, capability teardown, evidence architecture, mutation testing,
benchmarks, metamorphic testing, resource governance, regression memory,
multi-solver evaluation, final zero-trust audit — distilled into this
repository as **permanent, executable infrastructure** rather than a
one-time checklist.

## What exists here, permanently

| Phase (prompt) | Permanent artifact in this repo |
|---|---|
| 01 Full audit + repair | `.guardrails/failure-registry.jsonl` + `scripts/log_failure.py` (every fix logged with a regression pattern) |
| 02 Adversarial attack | `scripts/negative_controls.py` (8 hostile-input controls through the real CLI) + CI `evaluator-integrity` job |
| 03 Production torture | `tests/test_resource_governance.py` (timeouts, output bombs, runaway loops) |
| 04 Architecture + integrity | OpenSpec specs + `scripts/spec_traceability.py` + coherence containment tests |
| 05 Autonomy + recovery | `hub/coherence/verification.py` recovery semantics (FAILED → new claim, never edit history) + `tests/test_metamorphic.py` stateful lifecycles |
| 06 Release/performance | `ci.yml` (5 jobs) + `scripts/resource_audit.py` measurement |
| 07 Capability teardown | `.benchmarks/` corpus — measures whether real engineering gets done |
| 08 Evidence & proof | `hub/coherence/verification.py` + `scripts/evidence-validate.py` + `tests/test_evidence_integrity.py` |
| 09 Mutation + evaluator integrity | `scripts/mutation_check.py` (+ `--self-check`) + `scripts/negative_controls.py` |
| 10 Benchmark harness | `.benchmarks/harness.py` + `metrics.py` + 6-task corpus |
| 11 Differential/metamorphic | `tests/test_metamorphic.py` (round-trips, commutation, idempotence, determinism) |
| 12 Resource governance | `hub/coherence/resource_limits.py` (budgets, runaway detection, capped backoff) |
| 13 Regression memory | `scripts/regression_corpus.py` (relevance selection + staleness audit) |
| 14 Multi-solver evaluation | `.benchmarks/multi_solver.py` (+ shipped GAMING negative control) |
| 15 Final zero-trust audit | `orchestrator.md` §14 (run per release) |
| 16 Master Orchestrator | [`orchestrator.md`](./orchestrator.md) |

## The two ideas that make it work

**1. Distinguish implemented → executed → observed → verified.** A green
dashboard, a passing test, or a confident message is never the terminal
state. Anything not independently verified is reported UNVERIFIED. The
claim lifecycle in `hub/coherence/verification.py` makes this mechanical:
`transition(claim, VERIFIED)` raises; only `verify_independently()` — a
check the actor does not own — can set it, and digest drift demotes it
back to UNKNOWN.

**2. Attack the evaluator itself.** The meta-level weakness of every
autonomous system: the agent evaluates its own work with machinery it
helped create, then reports success. Every evaluator here carries its own
negative controls — mutation `--self-check`, the negative-control canary,
the benchmark control phase (a hidden verifier that passes the unsolved
repo invalidates the task), and the GAMING strategy that must stay
rejected. If the evaluator fails to detect an intentionally introduced
defect, that is a defect in the evaluator, and it is treated like one.

## The stopping criterion

Not "100%". Not "all tests pass". Not "coverage is high".

> No known actionable defect + no unexplored high-risk subsystem +
> representative behavioural evidence + evaluator integrity demonstrated +
> regression corpus passing + benchmark battery passing + known limitations
> explicitly recorded.

That is an evidence-based terminal state, reachable and honest.
