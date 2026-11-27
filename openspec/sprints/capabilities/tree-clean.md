# tree-clean sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **framework gate maintainer**. Bring a disposable project, the gate revision and an explicit scan scope to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept measured scope, diagnostic and exit disposition. |
| S2. Luna writer | Classify a clean working tree, generated churn, mode-only changes and unclassified edits in disposable checkouts. Record discovery count and each disposition. Start at [scripts/tree_clean_check.py](../../../scripts/tree_clean_check.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for measured scope, diagnostic and exit disposition. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`tc-01`](../../specs/tree-clean/spec.md#requirement-unclassified-working-tree-dirt-fails-the-gate) Unclassified working-tree dirt fails the gate | untracked source file / thousands of dirty files |
| [`tc-02`](../../specs/tree-clean/spec.md#requirement-generated-churn-is-reported-not-failed) Generated churn is reported, not failed | cache noise only |
| [`tc-03`](../../specs/tree-clean/spec.md#requirement-file-mode-only-churn-is-its-own-class) File-mode-only churn is its own class | mode flip after a copy |
| [`tc-04`](../../specs/tree-clean/spec.md#requirement-no-repositories-scanned-is-never-a-pass) No repositories scanned is never a pass | empty root |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

[Published specification](../../specs/tree-clean/spec.md) and [sprint dispatch](../../SPRINTS.md).
