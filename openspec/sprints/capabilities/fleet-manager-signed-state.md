# fleet-manager-signed-state sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **fleet manager maintainer and the operator for any live lane**. Bring disposable fleet records or a boundary package with declared inputs to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept package behavior and any separate operator-owned claim. |
| S2. Luna writer | Verify the signed document, named audience and freshness constraints at a known revision. Retain separate reconciliation receipts from two synthetic hosts. Start at [fleet-manager/tests/test_state_v1.py](../../../fleet-manager/tests/test_state_v1.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for package behavior and any separate operator-owned claim. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`fleet-006-01`](../../specs/fleet-manager-signed-state/spec.md#requirement-a-desired-state-is-a-signed-document-and-cannot-carry-a-command) A desired state is a signed document and cannot carry a command | a body that is not a desired state / a body that is not its own canonical text / a signature provider fails / a verifier that is not certain |
| [`fleet-006-02`](../../specs/fleet-manager-signed-state/spec.md#requirement-a-signed-state-names-exactly-one-audience) A signed state names exactly one audience | a state meant for another host / a redirected state with a bad signature |
| [`fleet-006-03`](../../specs/fleet-manager-signed-state/spec.md#requirement-a-state-is-fresh-and-cannot-be-replayed) A state is fresh and cannot be replayed | a captured state replayed / an older state arriving late / a state is missing from the stream / an expired state / a state from the future / a forged envelope is offered first |
| [`fleet-006-04`](../../specs/fleet-manager-signed-state/spec.md#requirement-two-test-hosts-reconcile-signed-no-op-desired-state) Two test hosts reconcile signed no-op desired state | the two-host world is already converged / a revoked host tries to speak / a revoked host tries to return |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-161, DG02-U-162, DG02-U-163, DG02-U-164. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

[Published specification](../../specs/fleet-manager-signed-state/spec.md) and [sprint dispatch](../../SPRINTS.md).
