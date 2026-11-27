# Sprint plan — gate scope honesty

Use the [sprint dispatch guide](../../SPRINTS.md) with this package’s [tasks](tasks.md) and [proposal](proposal.md).

Exercise the native entry point for this change. A change to session startup or manifest handling also needs a carrier-specific receipt. [Session adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Roles

- Lead: coordinate the consumer handoff, review scope semantics, and sign off on evidence.
- Luna: collect release and consumer-run receipts and prepare any authorized consumer-side change.
- Independent auditor: separate session verifies outputs and the consumer diff directly.
- Accountable owners: DevGate maintainer owns the upstream fixes; NeonDash repository/CI owner owns tasks 4.1–4.3.

## S1 — intake and baseline

- Treat tasks 1.1–1.3, 2.1–2.3, and 3.1–3.4 as completed upstream behavior; do not rewrite them without a failing control.
- Record the released DevGate revision containing the denominator, registry scope-line, and declared-anchor fixes.
- For task 4.1, confirm the NeonDash owner can select and approve the `.devgate` revision; do not assume upstream release availability.
- Inspect the consumer's registry guard and traceability ratchet alongside the measured `.guardrails/scope.json` declaration recorded in task 4.3.
- Exit when consumer repo/revision, accountable owner, release pin, and baseline outputs are recorded.

## S2 — consumer integration and evidence

- Task 4.1: owner-approved `.devgate` bump; record exact upstream and consumer SHAs.
- Task 4.2: replace YAML line counting with an assertion on the tool-owned scope line and raise the ratchet floor atomically with the denominator change.
- Task 4.3 records the measured `scripts`, `tools` and `data` roots in `.guardrails/scope.json`. Carry that completed result into the replay for 4.1 and 4.2.
- Run clean, missing-registry, merged-input, and declared-anchor consumer cases; retain stdout, exit status, and nonzero input counts.
- Exit when tasks 4.1 and 4.2 have reviewable consumer-side evidence or an explicit owner-blocked record.

## S3 — independent qualification

- Auditor checks the pinned tool behavior and consumer workflow assertions from the recorded trees, including fail-closed malformed/escaping scope behavior.
- Auditor verifies denominator numerator units, statement-level failure behavior, and ratchet change are consistent.
- Lead reconciles any consumer layout or release mismatch; no evidence from the framework-only tests substitutes for consumer execution.

## S4 — integration and closeout

- Lead records task outcomes and consumer revision links; preserve upstream implementation evidence separately from consumer adoption evidence.
- Run applicable consumer gates and the OpenSpec strict/traceability checks for any changed package artifacts.
- Handoff: release pin, consumer diff, scope-line receipts, anchor configuration and results, auditor verdict, and unresolved owner decisions.
- Boundary: NeonDash changes require its owner's participation; do not claim consumer adoption or deployment from upstream results.
