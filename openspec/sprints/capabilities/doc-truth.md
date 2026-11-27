# doc-truth sprint plan

At `cb2205c` the index recorded **CLOSED**. Use this plan for maintenance when the published behavior or its release inputs change. Keep the existing closure evidence pinned.

Route acceptance to the **release owner**. Bring a named candidate and disposable packaging or release fixtures to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept version, target, artifacts and owner disposition. |
| S2. Luna writer | Recheck the published version against its tag, changelog and documented overlay instructions after a release or documentation change. Retain the existing accepted ledger evidence. Start at [tests/test_check_version_truth.py](../../../tests/test_check_version_truth.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for version, target, artifacts and owner disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`doc-version-01`](../../specs/doc-truth/spec.md#requirement-version-artifacts-agree) Version artifacts agree | reconstructed history |
| [`doc-overlay-01`](../../specs/doc-truth/spec.md#requirement-instructions-follow-the-overlay-contract) Instructions follow the overlay contract | custom rules / stated rule counts |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

[Published specification](../../specs/doc-truth/spec.md) and [sprint dispatch](../../SPRINTS.md).
