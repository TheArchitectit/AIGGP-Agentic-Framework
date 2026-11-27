# spec-state-ledger sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **framework gate maintainer**. Bring a disposable project, the gate revision and an explicit scan scope to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept measured scope, diagnostic and exit disposition. |
| S2. Luna writer | Reconcile an isolated transition against its two bounding commits, row-specific source, expected seal and validator output. Keep row decisions and aggregate review seals separate. Start at [scripts/spec_state_gate.py](../../../scripts/spec_state_gate.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for measured scope, diagnostic and exit disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`spec-state-01`](../../specs/spec-state-ledger/spec.md#requirement-state-transitions-are-recorded-in-an-append-only-ledger) State transitions are recorded in an append-only ledger | closure cell edited without a ledger row / ledger row added without a state edit |
| [`spec-state-02`](../../specs/spec-state-ledger/spec.md#requirement-the-gate-derives-transitions-from-the-diff-not-from-prose) The gate derives transitions from the diff, not from prose | status line edited by hand |
| [`spec-state-03`](../../specs/spec-state-ledger/spec.md#requirement-bounding-commits-resolve-are-ordered-and-are-distinct) Bounding commits resolve, are ordered, and are distinct | single-commit declaration / unresolvable citation |
| [`spec-state-04`](../../specs/spec-state-ledger/spec.md#requirement-work-must-land-at-the-requirements-declared-location) Work must land at the requirement's declared location | unrelated commit cited |
| [`spec-state-05`](../../specs/spec-state-ledger/spec.md#requirement-terminal-closure-requires-verifiable-evidence) Terminal closure requires verifiable evidence | asserted but unexercised |
| [`spec-state-06`](../../specs/spec-state-ledger/spec.md#requirement-a-spec-is-terminal-only-when-every-requirement-is-exercised) A spec is terminal only when every requirement is exercised | partial closure declared complete / heading-only spec |
| [`spec-state-07`](../../specs/spec-state-ledger/spec.md#requirement-the-published-index-is-generated-and-drift-fails) The published index is generated, and drift fails | hand-edited index |
| [`spec-state-08`](../../specs/spec-state-ledger/spec.md#requirement-migration-proves-what-is-provable-and-marks-the-rest) Migration proves what is provable and marks the rest | history merged from another repository |
| [`spec-state-09`](../../specs/spec-state-ledger/spec.md#requirement-enforcement-placement-is-stated-honestly) Enforcement placement is stated honestly | overclaimed enforcement / reviewed remote protection / host configuration is unavailable / local hook is bypassable |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

Coordinate overlapping work with [dg-02-evidence-ledger-reconciliation](../../changes/dg-02-evidence-ledger-reconciliation/sprint-plan.md).

[Published specification](../../specs/spec-state-ledger/spec.md) and [sprint dispatch](../../SPRINTS.md).
