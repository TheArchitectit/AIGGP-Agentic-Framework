# evaluation-context sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **coherence service maintainer**. Bring pinned context, subject, policy and evaluator artifacts to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept the subject identity, decision and sealed evidence. |
| S2. Luna writer | Compare replay and fresh promotion for the same subject under two trusted contexts. Record cache identity, issuer and bound external facts. Start at [tests/test_hub_coherence_cache.py](../../../tests/test_hub_coherence_cache.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for the subject identity, decision and sealed evidence. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`coh-ctx-01`](../../specs/evaluation-context/spec.md#requirement-versioned-evaluation-context) versioned evaluation context | context is a decision input / caller cannot pick the clock |
| [`coh-ctx-02`](../../specs/evaluation-context/spec.md#requirement-trusted-context-issuance) trusted context issuance | repository requests weaker stage / stale context reuse |
| [`coh-ctx-03`](../../specs/evaluation-context/spec.md#requirement-replay-versus-fresh-promotion) replay versus fresh promotion | replay does not authorize / expiry evaluated at decision time |
| [`coh-ctx-04`](../../specs/evaluation-context/spec.md#requirement-bound-external-facts) bound external facts | captured fact changes |
| [`coh-ctx-05`](../../specs/evaluation-context/spec.md#requirement-cache-key-completeness) cache key completeness | partial key match |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-047, DG02-U-048, DG02-U-049, DG02-U-050, DG02-U-051. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

Coordinate overlapping work with [define-consumer-evidence-boundary](../../changes/define-consumer-evidence-boundary/sprint-plan.md).

[Published specification](../../specs/evaluation-context/spec.md) and [sprint dispatch](../../SPRINTS.md).
