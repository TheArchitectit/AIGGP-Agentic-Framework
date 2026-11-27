# spec-status-disposition sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **framework gate maintainer**. Bring a disposable project, the gate revision and an explicit scan scope to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept measured scope, diagnostic and exit disposition. |
| S2. Luna writer | Trace each unknown or external-owner disposition to its recorded scope and missing evidence. Require explicit owner authority for a deferred lifecycle decision. Start at [openspec/UNKNOWN-DISPOSITIONS.md](../../UNKNOWN-DISPOSITIONS.md). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for measured scope, diagnostic and exit disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`spec-state-10`](../../specs/spec-status-disposition/spec.md#requirement-unknown-specs-have-an-explicit-evidence-disposition) Unknown specs have an explicit evidence disposition | unreviewed unknown capability / evidence is insufficient |
| [`spec-state-11`](../../specs/spec-status-disposition/spec.md#requirement-external-owner-disposition-remains-distinct-from-deferred-lifecycle-status) External-owner disposition remains distinct from deferred lifecycle status | external consumer owns implementation |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

Coordinate overlapping work with [dg-02-evidence-ledger-reconciliation](../../changes/dg-02-evidence-ledger-reconciliation/sprint-plan.md).

[Published specification](../../specs/spec-status-disposition/spec.md) and [sprint dispatch](../../SPRINTS.md).
