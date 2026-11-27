# Sprint plan — DG-19 fail-closed enrollment token handoff

**Scope:** finish the defensive handoff boundary review without real credentials or live enrollment.
Tasks 1.1–1.3 are recorded complete. Task 2.1’s workflow-authored fixtures pass, but issuer-owned `GITHUB_OUTPUT`/`GITHUB_STATE` acceptance remains open; task 2.2 also awaits independent review and final gates.

## Sequence

### S1 — intake/baseline

- Recheck the pinned issuer action, workflow contract, local checkpoint, and exact focused test receipts: workflow 6 passed, reconciler 18 passed.
- Keep the distinction explicit: those tests use synthetic values, a fake reconciler, and do not invoke the issuer or mint a live token.

### S2 — implementation or evidence collection

- For task 2.1, review missing-pair, empty-token, and valid synthetic handoff through the actual workflow/process boundary; verify captured output and written artifacts contain no raw values.
- Resolve the issuer-owned output/state question using a bounded, inert fixture or authoritative transport disposition. If it cannot be qualified without real credentials, record NOT_RUN and leave task 2.1 open.
- For task 2.2, verify the input/trigger contract and rerun the focused enrollment suites and pinned repository gates on the candidate revision.

### S3 — independent qualification

- A distinct audit session checks workflow and process-boundary assertions, secret redaction, issuer boundary disposition, exact test identity, and source revision; it must not rely on the writer’s receipt alone.
- Stop on unexpected token persistence, raw-value leakage, missing issuer ownership, or a test that depends on real credentials/network access.

### S4 — integration/closeout

- Lead reconciles the audit and integration gates, signs off only the locally proven handoff behavior, and records issuer transport as open/NOT_RUN if unresolved.
- No real App credential, enrollment request, or workflow run is authorized by this plan; update task status only for evidence actually accepted.

## Bounded roles

- Lead: acceptance design, independent-review reconciliation, and sign-off. Luna: collect synthetic workflow receipts and rerun defensive tests.
- Issuer/action owner must disposition its runner-managed output/state boundary; a separate auditor verifies that evidence. DG-05 remains the owner for reconciler evidence.

## Sources

- [Proposal](proposal.md) · [Tasks](tasks.md) · [Baseline and local evidence](evidence.md)
- [Local token handoff checkpoint](local-token-handoff-verification.md) · [Global sprint plan](../../SPRINTS.md)

Use the package’s native acceptance path. If the session interface changes, assign its carrier-specific work through the [five-adapter matrix](../../SPRINTS.md#session-adapter-matrix).
