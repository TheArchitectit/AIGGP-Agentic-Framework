# Tasks

## 1. Establish the review baseline — November 25

- [x] 1.1 Record current main SHA, each PR head SHA, base SHA, draft/open state,
  changed-file scope, and exact-head workflow/check receipts in the handoff.
- [x] 1.2 Keep the PR set explicit: #32, #33, #46, #47, and #48. Do not infer
  readiness from a different commit, a local-only run, or a prior workflow.

## 2. Reconcile historical requests — November 26 UTC

- [x] 2.1 For #32, verify the archived result and trace its commits against
  current main. Record whether any follow-up is still required without
  recreating already-completed work.
- [x] 2.2 For #33, preserve the historical blocker and later owner decision;
  resolve the conflict against current main by ancestry and document any
  decision that still needs the owner. Do not discard history to make the
  branch appear conflict-free.
- [x] 2.3 Confirm the resulting disposition for #32 and #33, including whether
  either has remaining work or a merge action. Record exact refs and evidence.

## 3. Review the independent proposals — November 26 UTC

- [x] 3.1 For #46, verify the exact head's green CI and conflict-free scope.
  Keep the outcome limited to the approved-release plan; do not execute or
  publish a release as part of this coordination work.
- [x] 3.2 For #47, verify the exact head's green CI and provenance artifact
  integrity. Preserve all 182 `UNPROVEN` dispositions and the open row-specific
  evidence/sealing work; do not describe the PR as closing DG-02.
- [x] 3.3 For #48, complete the targeted test-process launch fix, rerun the
  affected tests and required workflow on the exact updated head, and preserve
  both the initial failed receipt and the later successful receipt. The initial
  registry-hygiene failure was corrected before merge.
- [x] 3.4 Run the DG-22 release coverage rehearsal on disposable Git fixture
  repositories and record the results for the active upstream release plan.
- [x] 3.5 Publish the public readiness audit and proposed OpenSpec changes
  to upstream PR #49. Verify that its exact head joins the gate check queue.

## 4. Record merge readiness and merges — November 26 UTC

- [x] 4.1 Before merging each PR, verify its base/head refs, conflict-free
  status, completed review, and required gates green on that exact head.
- [x] 4.2 Record a per-PR merge-ready decision only after its ancestry,
  evidence, and gate conditions are satisfied. Keep any unmet condition
  explicit; do not convert a historical or local result into a green receipt.
- [x] 4.3 After applicable gates were green and each PR was conflict-free,
  perform the authorized direct merges individually after checking the exact
  PR head and its required workflow receipts. Do not publish a release.

## 5. Close the coordination record

- [x] 5.1 Update this task list with exact outcomes and evidence links; keep
  unresolved decisions open.
- [x] 5.2 Run strict OpenSpec validation for this local package and record the
  result. No capability delta or upstream policy change is introduced.
- [x] 5.3 Record final merged state, merge timestamps, exact merge commits, and
  the upstream verification SHA; preserve the November 25 intake as history.
