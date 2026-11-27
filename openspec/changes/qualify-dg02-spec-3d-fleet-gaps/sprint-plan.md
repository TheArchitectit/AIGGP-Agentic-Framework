# Sprint plan — DG-02 spec, 3D, and fleet gaps

Use the [sprint dispatch guide](../../SPRINTS.md) with this package’s [tasks](tasks.md), [proposal](proposal.md), and [batch 010 review](../dg-02-evidence-ledger-reconciliation/batches/batch-010/README.md).

Exercise the native entry point for this change. A change to session startup or manifest handling also needs a carrier-specific receipt. [Session adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Roles

- Lead: coordinate shared promotion policy dependencies, reconcile findings, and sign off.
- Luna: prepare disposable lifecycle/subject fixtures and collect fleet test evidence.
- Independent auditor: separate session reviews source, controlled results, provenance, and bundle validation.
- Accountable owners: spec-platform maintainer, 3D subject/promotion owner, fleet adapter/channel owner, and DG-02 evidence owner.

## S1 — intake and baseline

- Treat batch 010's adapter finding as a lead; map tasks 1.1–1.3 to `spec-fmt-01..03`, tasks 2.1–2.4 to `coh-3d-01..04`, and tasks 3.1–3.4 to `fleet-007-01..04` / `fleet-004-01` and rows 116–120.
- Identify the shared consumer-policy dependency with `qualify-dg02-hub-integration-gaps` task 3.2 before scheduling promotion tests.
- Record current parser/CLI versions, disposable archive tree boundary, subject/config identity, adapter signatures, and row citation status.
- Exit when fixture ownership and evidence mapping are agreed; consumer promotion remains blocked on policy-owner availability.

## S2 — implementation and evidence

- Tasks 1.1–1.3: compare parser inventories, exercise malformed/missing-marker gate behavior, completed archive debt, strict revalidation/traceability, and active/stacked-change ordering.
- Tasks 2.1–2.4: bind composite mutations/digests, repair invalidation and old-attestation rejection, cross-subject result/promotion paths, and pinned capture configuration without rendering/simulation.
- Tasks 3.1–3.3: reject catch-all adapter parameters for all named slots, qualify redaction/pins/warm-stock/ephemeral jobs, and test no-outbound-channel with host-initiated call-in.
- Task 3.4: establish source/test provenance and row-bound bundles for 116–120; keep unsupported proof UNPROVEN.
- Exit with named results, policy-owner approval for consumer scenarios, and no unobserved side effects.

## S3 — independent qualification

- Auditor verifies disposable lifecycle state, exact subject/config digest, adapter signature cases, and negative controls from raw receipts.
- Auditor checks row-specific provenance and evidence-manifest digests; no parser agreement or marker is treated as behavioral proof.
- Lead reconciles shared policy findings with the hub integration plan and submits only complete rows to the state gate.

## S4 — integration and closeout

- Run spec-platform, 3D, and fleet suites; strict OpenSpec, traceability, evidence validation, and state gate at the reviewed head.
- Handoff: parser comparison, disposable archive transcript, subject fixtures, adapter controls, provenance/bundle map, auditor verdict, and policy dependencies.
- Preserve UNPROVEN for missing history or consumer acceptance; do not claim a production promotion path from fixtures.
