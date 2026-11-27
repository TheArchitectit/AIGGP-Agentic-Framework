# security-boundaries sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **security control owner and service maintainer**. Bring approved defensive fixtures, a sanitized record and a scoped test boundary to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept the specified control outcome and evidence disclosure limits. |
| S2. Luna writer | Review configured containment, credential handling, shutdown and immutable references using existing defensive tests and sanitized fixtures. Record any unsupported platform or integration claim. Start at [tests/test_hub_boundary_validation.py](../../../tests/test_hub_boundary_validation.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for the specified control outcome and evidence disclosure limits. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`coh-sec-01`](../../specs/security-boundaries/spec.md#requirement-repository-supplied-paths-are-contained) Repository-supplied paths are contained | inventory traversal / selector exfiltration |
| [`mon-sec-01`](../../specs/security-boundaries/spec.md#requirement-hub-request-and-shutdown-contracts) Hub request and shutdown contracts | oversized body / signal shutdown / concurrent duplicate enrollment |
| [`mon-sec-02`](../../specs/security-boundaries/spec.md#requirement-tokens-are-not-stored-or-logged-in-plaintext) Tokens are not stored or logged in plaintext | volume read / enroll output |
| [`ci-sec-01`](../../specs/security-boundaries/spec.md#requirement-template-actions-and-images-are-immutably-referenced) Template actions and images are immutably referenced | template audit / secrets drop-in parses |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-105, DG02-U-106, DG02-U-107, DG02-U-108. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [gate-scope-honesty](../../changes/gate-scope-honesty/sprint-plan.md), [qualify-dg02-monitor-scanner-security-gaps](../../changes/qualify-dg02-monitor-scanner-security-gaps/sprint-plan.md).

[Published specification](../../specs/security-boundaries/spec.md) and [sprint dispatch](../../SPRINTS.md).
