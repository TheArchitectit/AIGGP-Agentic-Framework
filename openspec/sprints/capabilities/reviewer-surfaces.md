# reviewer-surfaces sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **consumer integration owner**. Bring a synthetic consumer, a pinned result and a trusted decision point to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept consumer acceptance over the selected subject and policy. |
| S2. Luna writer | Compare a synthetic finding in local output, CI output and the reviewer-facing evidence link. Check document structure and subject identity at each surface. Start at [tests/test_hub_coherence_report.py](../../../tests/test_hub_coherence_report.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for consumer acceptance over the selected subject and policy. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`reviewer-01`](../../specs/reviewer-surfaces/spec.md#requirement-sarif-validity) SARIF validity | SARIF round-trip |
| [`reviewer-02`](../../specs/reviewer-surfaces/spec.md#requirement-local-ci-parity) local-CI parity | divergent local verdict |
| [`reviewer-03`](../../specs/reviewer-surfaces/spec.md#requirement-evidence-linked-review-comments) evidence-linked review comments | comment with evidence |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

[Published specification](../../specs/reviewer-surfaces/spec.md) and [sprint dispatch](../../SPRINTS.md).
