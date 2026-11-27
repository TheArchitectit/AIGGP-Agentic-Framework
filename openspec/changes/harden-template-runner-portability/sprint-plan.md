# Sprint plan — template runner portability

Use the [sprint dispatch guide](../../SPRINTS.md) with this package’s [tasks](tasks.md) and [proposal](proposal.md).

Exercise the native entry point for this change. A change to session startup or manifest handling also needs a carrier-specific receipt. [Session adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Roles

- Lead: maintain the template/spec mapping, review the pilot boundary, and sign off.
- Luna: arrange the consumer run and collect workflow/job receipts for task 4.1.
- Independent auditor: separate session verifies the chosen workflow revision and native receipts.
- Accountable owners: AIGGP tooling maintainer owns shipped templates; consumer CI owner and fleet runner operator own adoption evidence.

## S1 — intake and baseline

- Accept tasks 1.1–1.2, 2.1–2.2, and 3.1–3.3 as the recorded framework-side baseline; inspect the exact template and test revision.
- Confirm the consumer actually adopted the secret-validation and drift-scan templates and identify the fleet runner/workflow owner.
- For task 4.1, record the consumer repository, workflow revision, runner class, and permission to run a controlled pilot.
- Exit when the adopted template SHA, expected scanner pin, and runner eligibility are known; otherwise report NOT_RUN for consumer proof.

## S2 — consumer run and evidence

- Run the adopted workflows on the consumer's eligible fleet runner; capture actual workflow/job URLs, checkout SHA, tool pin, conclusions, and inputs.
- Verify the scanner is available through the runner-temporary path and the drift workflow resolves its runner array and completes a scheduled/manual execution.
- Include bounded negative controls in disposable or approved fixtures for denied install placement and unusable runner declaration; retain diagnostics and ref state.
- Task 4.1 exit: receipts show the published workflow ran on the intended runner and both template behaviors completed; no hosted-only result is labeled fleet evidence.

## S3 — independent qualification

- Auditor checks the workflow and runner identities, exact source/tool SHAs, nonzero scanned inputs, negative-control outcomes, and no accidental workflow skips.
- Auditor compares results with tasks 3.1–3.2 and records PASS/FAIL/NOT_RUN for each behavior.
- Lead reconciles discrepancies and obtains the consumer CI owner's acceptance of the support scope.

## S4 — integration and closeout

- Add task 4.1's run IDs and outcome to package evidence; keep framework suite and consumer fleet execution distinct.
- Run strict OpenSpec and traceability at the resulting review head; archive only after the consumer receipt is accepted.
- Handoff: template/tool SHAs, runner classification, native run receipts, negative-control evidence, auditor verdict, and support limitations.
- Boundary: no additional runner class or forge is supported without its own receipt and owner acceptance.
