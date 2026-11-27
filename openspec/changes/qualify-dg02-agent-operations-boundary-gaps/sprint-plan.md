# Sprint plan — DG-02 agent operations and boundary gaps

Use the [sprint dispatch guide](../../SPRINTS.md) with this package’s [tasks](tasks.md), [proposal](proposal.md), and [batch 011 review](../dg-02-evidence-ledger-reconciliation/batches/batch-011/README.md).

Exercise the native entry point for this change. A change to session startup or manifest handling also needs a carrier-specific receipt. [Session adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Roles

- Lead: define proof scope, review finding reconciliation, and sign off on any state-gate candidate.
- Luna: implement or collect fixtures and prepare row-level evidence bundles.
- Independent auditor: separate session inspects changed source, tests, receipts, bundle digests, and validator results.
- Accountable owners: fleet channel, operation, receipt, and repository-boundary maintainers; DG-02 evidence owner controls roster reconciliation.

## S1 — intake and baseline

- Treat the batch 011 findings for rows 121–132 as the evidence lead; all twelve historical citations are empty/rejected and remain UNPROVEN.
- Map tasks 1.1–1.4 to `fleet-004-02..05`; tasks 2.1–2.5 to `fleet-005-01..05`; task 3.1 to `repo-002-01..03`.
- Record current source/test revisions, injected verifier and in-memory ledger limitations, relevant QA artifacts, and each row's citation status.
- Exit with bounded test seams, persistence boundary, expected evidence per requirement, and explicit owner for each external interface.

## S2 — implementation and evidence

- Tasks 1.1–1.4: qualify enrollment expiry/revocation, canonical signatures and verifier failure, replay/freshness ordering, and key rotation overlap at the stated persistence boundary.
- Tasks 2.1–2.5: check parameter names before values; qualify capability default-deny, safe references, receipts/idempotency, authoritative construction, and migration mapping.
- Task 3.1: run boundary gate clean/violation/unusable-input cases and verify manifest/license and dependency-direction controls.
- Task 3.2: recover attributable source/test provenance, bind each claim to a row-specific expected digest, and leave unsupported records unchanged.
- Exit with named test results, redacted outputs, range provenance, and candidate bundles for every task actually supported.

## S3 — independent qualification

- Auditor replays the named defensive tests and checks no secret values are emitted; verify verifier-double and memory-only limits remain explicit.
- Auditor validates each bundle against its expected digest and checks provenance range overlaps implementation/tests.
- Lead submits only fully conjunctive candidates to the state gate; no marker or passing current test alone promotes a historical row.

## S4 — integration and closeout

- Run package tests, strict OpenSpec, traceability, bundle validation, and state-gate checks at the final reviewed head.
- Record per-row PASS/FAIL/NOT_RUN and preserve UNPROVEN for missing history, persistence, or accepted evidence.
- Handoff: task-to-row map, source/test ranges, receipts, bundle digests, validator output, auditor verdict, and unresolved owner-boundary decisions.
