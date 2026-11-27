# art-creation-contract sprint plan

At `cb2205c` the index recorded **UNKNOWN**. Start by locating the implementation and a measurable entry point. Record missing or externally held evidence before selecting an implementation change.

Route acceptance to the **art workflow and consuming-product owners**. Bring a synthetic asset manifest, target declaration and rights or capture records where applicable to intake.

**Session adapters.** Use the native entry point. Add a carrier-specific run only if a change also affects session startup. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept asset-specific evidence and outstanding external acceptance. |
| S2. Luna writer | Trace a synthetic asset from approved brief through provenance and target-specific checks. Request owner-supplied engine receipts for fidelity, retention and rights claims. Start at [scripts/test_art_creation_scan.py](../../../scripts/test_art_creation_scan.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for asset-specific evidence and outstanding external acceptance. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`art-done-01`](../../specs/art-creation-contract/spec.md#requirement-one-definition-of-done) one definition of done | file written is not done / a counter is not done |
| [`art-brief-01`](../../specs/art-creation-contract/spec.md#requirement-art-brief-before-generation) art brief before generation | generation with no brief |
| [`art-brief-02`](../../specs/art-creation-contract/spec.md#requirement-shape-language-names-a-rule-per-class) shape language names a rule per class | a concept outside its class rule / acceptance with no rule named |
| [`art-stage-01`](../../specs/art-creation-contract/spec.md#requirement-every-stage-names-its-consumer) every stage names its consumer | terminal artifact with no reader / consumer path does not exist |
| [`art-ledger-01`](../../specs/art-creation-contract/spec.md#requirement-provenance-ledger-is-the-inventory) provenance ledger is the inventory | asset outside the ledger / a published count disagrees with the ledger |
| [`art-bytes-01`](../../specs/art-creation-contract/spec.md#requirement-bytes-are-versioned-and-replicated) bytes are versioned and replicated | cleanup deletes the only copy / restore has never been run |
| [`art-accept-01`](../../specs/art-creation-contract/spec.md#requirement-fidelity-gate) fidelity gate | automated score without a verdict / perfect retention on the wrong shape |
| [`art-accept-02`](../../specs/art-creation-contract/spec.md#requirement-retention-measured-beside-the-verdict) retention measured beside the verdict | a measurement with no threshold |
| [`art-draw-01`](../../specs/art-creation-contract/spec.md#requirement-every-target-must-draw) every target must draw | a platform that clears a buffer / a DCC preview offered as evidence |
| [`art-rights-01`](../../specs/art-creation-contract/spec.md#requirement-rights-recorded-at-generation) rights recorded at generation | blank rights field |
| [`art-qty-01`](../../specs/art-creation-contract/spec.md#requirement-quantity-gates-run-last) quantity gates run last | floor met, fidelity failing / floor not met, every verdict green |
| [`art-evolve-01`](../../specs/art-creation-contract/spec.md#requirement-the-contract-grows-from-the-failure-registry) the contract grows from the failure registry | a new failure class appears / a class already covered |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

Coordinate overlapping work with [dg-06-art-evolution-external-proof](../../changes/dg-06-art-evolution-external-proof/sprint-plan.md).

[Published specification](../../specs/art-creation-contract/spec.md) and [sprint dispatch](../../SPRINTS.md).
