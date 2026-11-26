# Tasks

## 1. Verify and specify

- [x] 1.1 Record the main CI failure and verify the new gate-execution contract with the pinned strict OpenSpec CLI. **Evidence:** `evidence.md`.
- [x] 1.2 Reproduce the unhandled child-process launch error with a controlled local fixture at the reviewed baseline. **Evidence:** `evidence.md`.

## 2. Implement and test

- [x] 2.1 Route child launch errors through the existing per-file failure, cleanup, and solo adjudication. **Evidence:** `evidence.md`.
- [x] 2.2 Verify the revised runner reports a launch failure accurately, continues healthy files, and exits nonzero for a persistent launch failure. Verify the successful scenario and guard against vacuous solo adjudication. **Evidence:** `evidence.md`.
- [x] 2.3 Use the first runner step's job-local completion report for the non-vacuity assertion. Verify one invocation, a positive report, absent or zero count, and a failed runner whose output cannot make the step pass.
- [x] 2.4 Run the targeted test-runner tests and relevant local repository gates. Record exact commands, outcomes, and any pending hosted evidence.

## 3. Review and archive

- [ ] 3.1 Independently review evidence, scope and test behavior. Promote the reviewed delta and run strict validation and traceability with the archive candidate.
