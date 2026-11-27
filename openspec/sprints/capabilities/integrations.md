# integrations sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **consumer integration owner**. Bring a synthetic consumer, a pinned result and a trusted decision point to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept consumer acceptance over the selected subject and policy. |
| S2. Luna writer | Run required and advisory integrations on a pinned synthetic subject. Reconcile missing or skipped upstream evidence to the consumer's own promotion decision. Start at [tests/test_coherence_workflow_template.py](../../../tests/test_coherence_workflow_template.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for consumer acceptance over the selected subject and policy. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`coh-int-01`](../../specs/integrations/spec.md#requirement-stable-ci-integration) stable CI integration | equivalent local and CI invocation |
| [`coh-int-02`](../../specs/integrations/spec.md#requirement-fleet-visibility) fleet visibility | fleet ingests an advisory result |
| [`coh-int-03`](../../specs/integrations/spec.md#requirement-promote-or-halt-contract) promote-or-halt contract | 3D asset candidate passes / repair changes the candidate / vision advice is nondeterministic |
| [`coh-int-04`](../../specs/integrations/spec.md#requirement-no-implicit-trust-from-upstream) no implicit trust from upstream | upstream artifact is signed but unevaluated |
| [`coh-int-05`](../../specs/integrations/spec.md#requirement-adapters-never-weaken-the-contract) adapters never weaken the contract | adapter timeout |
| [`coh-int-06`](../../specs/integrations/spec.md#requirement-gate-runs-or-reports-explicit-skipped) gate runs or reports explicit SKIPPED | coherence gate cannot run |
| [`coh-int-07`](../../specs/integrations/spec.md#requirement-per-repository-fleet-independence) per-repository fleet independence | hub polls a registered repo / watched-branch scope |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-078, DG02-U-079, DG02-U-080, DG02-U-081, DG02-U-082, DG02-U-083, DG02-U-084. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [qualify-dg02-hub-integration-gaps](../../changes/qualify-dg02-hub-integration-gaps/sprint-plan.md), [qualify-consumer-delivery-evidence](../../changes/qualify-consumer-delivery-evidence/sprint-plan.md).

[Published specification](../../specs/integrations/spec.md) and [sprint dispatch](../../SPRINTS.md).
