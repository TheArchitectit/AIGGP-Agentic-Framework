# open-item-aging sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **framework gate maintainer**. Bring a disposable project, the gate revision and an explicit scan scope to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept measured scope, diagnostic and exit disposition. |
| S2. Luna writer | Use a dated backlog and triage ledger to test active, expired, malformed and empty inventories. Record which record controlled each decision. Start at [scripts/open_item_aging_check.py](../../../scripts/open_item_aging_check.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for measured scope, diagnostic and exit disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`oia-01`](../../specs/open-item-aging/spec.md#requirement-an-aged-open-item-must-carry-a-triage-disposition) An aged open item must carry a triage disposition | 70-day-old untriaged item / invalid disposition |
| [`oia-02`](../../specs/open-item-aging/spec.md#requirement-deferral-expires-and-carries-a-reason) Deferral expires and carries a reason | expired deferral / open-ended deferral |
| [`oia-03`](../../specs/open-item-aging/spec.md#requirement-an-unparseable-age-fails-rather-than-defaulting) An unparseable age fails rather than defaulting | row with no date |
| [`oia-04`](../../specs/open-item-aging/spec.md#requirement-a-vacuous-scan-is-never-a-pass) A vacuous scan is never a pass | empty backlog |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

[Published specification](../../specs/open-item-aging/spec.md) and [sprint dispatch](../../SPRINTS.md).
