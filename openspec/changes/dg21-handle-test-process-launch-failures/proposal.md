# Handle per-file test process launch failures

## Why

On `2bf84ddab55695340e91ceb026b319fcae7de3e4`, the main CI
per-file test job exited on an unhandled `spawn python3 EAGAIN` error. The
runner aborted before it could account for the active file, finish the rest
of the queue, or run its existing solo adjudication. The comparable promotion
PR's test job passed. The main CI retry reported 2,569 passing tests across 173 files in the first runner step. Its non-vacuity step invoked the runner again and failed with the same launch error. [First attempt](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/45720189050/job/139576313889) [Retry](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/45720189050/job/139585805765)

## What changes

- Route a child-process spawn error through the existing per-file failure
  result, with the affected file and a diagnostic identifying the launch error.
- Complete discovery, scheduling, and the existing solo adjudication. A
  persistent launch failure leaves the run failed even when other files pass.
- Use the completed runner's same-job report for the non-vacuity assertion.
  Preserve the runner exit status and reject an absent or zero file count.
- Exercise the real per-file runner and the workflow's receipt check with
  controlled fixtures.

## Impact

This applies to the framework and consumers that use `scripts/run-tests.mjs`.
The existing pool size, timeouts, test engine selection, and success criteria
continue to govern completed test processes.
