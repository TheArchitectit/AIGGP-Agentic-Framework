# evidence-claims sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **framework gate maintainer**. Bring a disposable project, the gate revision and an explicit scan scope to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept measured scope, diagnostic and exit disposition. |
| S2. Luna writer | Create fixture claims with and without the required owner, expiry or evidence reference. Check the reported path and exit, including the empty-scope case. Start at [scripts/evidence_claim_check.py](../../../scripts/evidence_claim_check.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for measured scope, diagnostic and exit disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`evc-01`](../../specs/evidence-claims/spec.md#requirement-a-deferred-marker-must-name-owner-reason-and-expiry) A deferred marker must name owner, reason, and expiry | ownerless deferral / expired deferral |
| [`evc-02`](../../specs/evidence-claims/spec.md#requirement-a-mock-must-point-at-the-real-thing-it-stands-in-for) A mock must point at the real thing it stands in for | mock with source pointer / bare mock |
| [`evc-03`](../../specs/evidence-claims/spec.md#requirement-a-stub-must-reference-a-tracked-issue) A stub must reference a tracked issue | stub with issue / stub with no issue |
| [`evc-04`](../../specs/evidence-claims/spec.md#requirement-a-bare-marker-is-a-violation-but-prose-is-not) A bare marker is a violation, but prose is not | real unfinished work / documentation mentioning the word |
| [`evc-05`](../../specs/evidence-claims/spec.md#requirement-exemptions-are-declared-not-inferred) Exemptions are declared, not inferred | allowlisted fixtures |
| [`evc-06`](../../specs/evidence-claims/spec.md#requirement-no-files-scanned-is-never-a-pass) No files scanned is never a pass | empty root |
| [`evc-07`](../../specs/evidence-claims/spec.md#requirement-evidence-claim-scan-exclusions-are-explicit-and-portable) Evidence-claim scan exclusions are explicit and portable | generated Git metadata contains marker text / reviewed normative examples are exempted / a real marker occurs outside an exact exemption |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

[Published specification](../../specs/evidence-claims/spec.md) and [sprint dispatch](../../SPRINTS.md).
