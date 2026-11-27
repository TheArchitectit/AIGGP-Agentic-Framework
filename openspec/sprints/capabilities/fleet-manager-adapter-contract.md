# fleet-manager-adapter-contract sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **fleet manager maintainer and the operator for any live lane**. Bring disposable fleet records or a boundary package with declared inputs to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept package behavior and any separate operator-owned claim. |
| S2. Luna writer | Exercise the closed adapter interface with inert adapters, typed failures and pinned image identities. Retain cold, warm and already-used instance decisions. Start at [fleet-manager/tests/test_adapters_v1.py](../../../fleet-manager/tests/test_adapters_v1.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for package behavior and any separate operator-owned claim. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`fleet-007-01`](../../specs/fleet-manager-adapter-contract/spec.md#requirement-one-closed-adapter-contract-checked-without-calling-it) One closed adapter contract, checked without calling it | a complete adapter / a missing call / several missing calls / a call with the wrong signature / a catch-all signature / the wrong runtime / checking does not call |
| [`fleet-007-02`](../../specs/fleet-manager-adapter-contract/spec.md#requirement-adapter-failures-are-typed-and-closed) Adapter failures are typed and closed | an unknown kind / a detail that looks like a credential / an unexpected exception / an empty kind argument |
| [`fleet-007-03`](../../specs/fleet-manager-adapter-contract/spec.md#requirement-the-runner-image-is-pinned-by-an-immutable-digest) The runner image is pinned by an immutable digest | a tag instead of a digest / the standard's digest / an instance from another image |
| [`fleet-007-04`](../../specs/fleet-manager-adapter-contract/spec.md#requirement-one-job-per-instance-and-warm-means-never-used) One job per instance, and warm means never used | a used container offered as warm / admitting beyond the ceiling / warm stock from another image / a shortfall below the floor / the ephemeral command |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-116, DG02-U-117, DG02-U-118, DG02-U-119. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-dg02-spec-3d-fleet-gaps](../../changes/qualify-dg02-spec-3d-fleet-gaps/sprint-plan.md).

[Published specification](../../specs/fleet-manager-adapter-contract/spec.md) and [sprint dispatch](../../SPRINTS.md).
