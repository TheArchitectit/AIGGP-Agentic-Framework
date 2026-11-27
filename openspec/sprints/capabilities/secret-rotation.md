# secret-rotation sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **security control owner and service maintainer**. Bring approved defensive fixtures, a sanitized record and a scoped test boundary to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept the specified control outcome and evidence disclosure limits. |
| S2. Luna writer | Verify synthetic detection and revocation records against the required date and evidence reference. Keep raw credential material outside every receipt. Start at [scripts/secret_rotation_check.py](../../../scripts/secret_rotation_check.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for the specified control outcome and evidence disclosure limits. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`sr-01`](../../specs/secret-rotation/spec.md#requirement-scrubbing-a-secret-from-head-is-not-revoking-it) Scrubbing a secret from HEAD is not revoking it | scrubbed but never revoked / still committed |
| [`sr-02`](../../specs/secret-rotation/spec.md#requirement-a-revocation-must-carry-date-and-evidence) A revocation must carry date and evidence | claimed revocation with no record / revocation with a pointer |
| [`sr-03`](../../specs/secret-rotation/spec.md#requirement-a-malformed-row-cannot-be-partially-trusted) A malformed row cannot be partially trusted | missing required field |
| [`sr-04`](../../specs/secret-rotation/spec.md#requirement-an-empty-ledger-passes-an-unparseable-one-does-not) An empty ledger passes; an unparseable one does not | empty file / comments only |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

[Published specification](../../specs/secret-rotation/spec.md) and [sprint dispatch](../../SPRINTS.md).
