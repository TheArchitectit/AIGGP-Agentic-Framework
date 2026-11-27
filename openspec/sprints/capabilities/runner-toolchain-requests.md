# runner-toolchain-requests sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **monitor service owner and lab operator**. Bring an isolated registry, synthetic runner identities and a known clock to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept service behavior and environment-specific readback. |
| S2. Luna writer | Trace a synthetic request from runner capability gap to accountable operator decision and fulfillment evidence. Verify lane identity and the permitted state sequence. Start at [tests/test_hub_toolchain_requests.py](../../../tests/test_hub_toolchain_requests.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for service behavior and environment-specific readback. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`mon-tc-01`](../../specs/runner-toolchain-requests/spec.md#requirement-a-runner-reports-a-capability-gap-drawn-from-a-closed-vocabulary) A runner reports a capability gap drawn from a closed vocabulary | an entry is matched exactly against the vocabulary / a probe has a fixed definition / a submitted list is rejected whole / the bounds are fixed, not configured / the vocabulary count is derived, never asserted / a profile is spec-governed data / the lane-to-profile assignment is reviewed elsewhere / the host PATH is not a source / a lane's profile requires a tool its image lacks / the image has everything the profile requires / a probe cannot complete / a probe proves a dependency / a value outside the vocabulary / `g++` survives every channel |
| [`mon-tc-02`](../../specs/runner-toolchain-requests/spec.md#requirement-the-hub-is-the-system-of-record-and-lane-identity-is-explicit) The hub is the system of record, and lane identity is explicit | the request set carries what a row needs / a heartbeat without the field / a queue renders a row from the read alone / a row whose lane has never enrolled / five identical reports / concurrent identical reports / Mission Control restarts / the hub is unreachable / a request for a lane MC has not linked |
| [`mon-tc-03`](../../specs/runner-toolchain-requests/spec.md#requirement-decisions-are-attributable-and-cannot-be-made-by-a-runner) Decisions are attributable and cannot be made by a runner | a credential class is not an authorization / a decision note is too long / the history record format is fixed / the human-to-credential binding belongs to Mission Control / a runner attempts to decide / an operator approves / a replayed nonce |
| [`mon-tc-04`](../../specs/runner-toolchain-requests/spec.md#requirement-request-state-changes-only-through-a-guarded-transition) Request state changes only through a guarded transition | two writes against one version / the transition table is normative / approving one tool of three / two operators decide at once / a repeated identical decision / a toolchain reappears after fulfillment / a denied lane keeps reporting |
| [`mon-tc-05`](../../specs/runner-toolchain-requests/spec.md#requirement-fulfillment-requires-evidence-from-a-trusted-builder-and-a-later-convergence) Fulfillment requires evidence from a trusted builder and a later convergence | nothing installs software on a runner / the evaluator image fields are not this capability's / approval with no build / build reported, probe still failing / a digest offered under the wrong credential / a heartbeat omits the evaluator image field |
| [`mon-tc-06`](../../specs/runner-toolchain-requests/spec.md#requirement-absence-is-never-reported-as-health) Absence is never reported as health | the coverage states are distinguished by evidence / the windows are fixed numbers, in one place / an approved request is never built / a lane that never reported / a stale lane / a probe that failed last run |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-173, DG02-U-174, DG02-U-175, DG02-U-176, DG02-U-177, DG02-U-178. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

[Published specification](../../specs/runner-toolchain-requests/spec.md) and [sprint dispatch](../../SPRINTS.md).
