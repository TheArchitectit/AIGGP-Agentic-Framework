# tracked-executable-integrity sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **framework gate maintainer**. Bring a disposable project, the gate revision and an explicit scan scope to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept measured scope, diagnostic and exit disposition. |
| S2. Luna writer | Read Git index modes for every tracked executable entry point. Test a missing executable bit in a disposable index and retain the named path. Start at [scripts/check_exec_bits.py](../../../scripts/check_exec_bits.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for measured scope, diagnostic and exit disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`fw-ci-04`](../../specs/tracked-executable-integrity/spec.md#requirement-tracked-shebang-entry-points-match-their-index-mode) Tracked shebang entry points match their index mode | shebang test entry point is committed non-executable / drift test entry point has executable index mode |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

[Published specification](../../specs/tracked-executable-integrity/spec.md) and [sprint dispatch](../../SPRINTS.md).
