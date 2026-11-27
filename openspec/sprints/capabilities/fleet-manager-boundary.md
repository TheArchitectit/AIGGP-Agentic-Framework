# fleet-manager-boundary sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **fleet manager maintainer and the operator for any live lane**. Bring disposable fleet records or a boundary package with declared inputs to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept package behavior and any separate operator-owned claim. |
| S2. Luna writer | Run the boundary checker on clean, conflicting and unusable manifests. Bind the push CI checkout and the actual changed-path comparison range. Start at [tests/test_check_boundary.py](../../../tests/test_check_boundary.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for package behavior and any separate operator-owned claim. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`repo-002-01`](../../specs/fleet-manager-boundary/spec.md#requirement-product-tiers-code-lives-only-under-the-declared-root) Product-tiers code lives only under the declared root | an undeclared directory appears under the boundary / product-tiers code is placed outside the boundary |
| [`repo-002-02`](../../specs/fleet-manager-boundary/spec.md#requirement-the-boundary-carries-a-manifest-and-a-license-notice) The boundary carries a manifest and a license notice | the manifest claims a separate license grant / the manifest is missing or malformed |
| [`repo-002-03`](../../specs/fleet-manager-boundary/spec.md#requirement-open-core-code-does-not-import-the-boundary) Open-core code does not import the boundary | an open-core module imports boundary code / boundary code imports open-core code |
| [`repo-002-04`](../../specs/fleet-manager-boundary/spec.md#requirement-the-boundary-gate-fails-closed) The boundary gate fails closed | the gate is run against a clean tree |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-130, DG02-U-131, DG02-U-132, DG02-U-133. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-dg02-agent-operations-boundary-gaps](../../changes/qualify-dg02-agent-operations-boundary-gaps/sprint-plan.md), [qualify-dg02-boundary-contract-domain-gaps](../../changes/qualify-dg02-boundary-contract-domain-gaps/sprint-plan.md).

[Published specification](../../specs/fleet-manager-boundary/spec.md) and [sprint dispatch](../../SPRINTS.md).
