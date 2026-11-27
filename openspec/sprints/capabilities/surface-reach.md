# surface-reach sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **framework gate maintainer**. Bring a disposable project, the gate revision and an explicit scan scope to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept measured scope, diagnostic and exit disposition. |
| S2. Luna writer | Compare actual files with the declared surface groups on a bounded change. Record missing surfaces, invalid comparison modes and undersized groups. Start at [scripts/surface_reach_check.py](../../../scripts/surface_reach_check.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for measured scope, diagnostic and exit disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`srch-01`](../../specs/surface-reach/spec.md#requirement-a-change-must-reach-every-declared-surface) A change must reach every declared surface | fix applied to one of two surfaces / all surfaces agree |
| [`srch-02`](../../specs/surface-reach/spec.md#requirement-a-vanished-surface-is-a-failure-not-a-skip) A vanished surface is a failure, not a skip | surface deleted |
| [`srch-03`](../../specs/surface-reach/spec.md#requirement-comparison-mode-is-declared-per-group) Comparison mode is declared per group | generated artifact group |
| [`srch-04`](../../specs/surface-reach/spec.md#requirement-a-group-with-fewer-than-two-surfaces-is-a-configuration-error) A group with fewer than two surfaces is a configuration error | single-path group / empty manifest |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

[Published specification](../../specs/surface-reach/spec.md) and [sprint dispatch](../../SPRINTS.md).
