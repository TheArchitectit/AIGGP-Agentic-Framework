# DG-02 evidence review batch 010

**DG02-U-109 through DG02-U-120 remain UNPROVEN.** Three Luna agents collected evidence. The lead independently reviewed the requirements, source, cited Git ranges and tests at `8f5233d880cf5920c474345bbe79379248bbf6b9`. No row-specific historical accepted bundle and digest were found. Canonical requirement validation was NOT_RUN and no lifecycle transition was made.

The [dispositions](batch-010-disposition.jsonl) bind the evidence and missing proof for each row. The [test receipt](test-receipt.json) records 147 passing Python tests and 70 passing subtests, plus the parser comparison and adapter controls. The receipt is current-tree evidence and does not prove historical closure.

| Row | Requirement | Observation | Remaining proof |
| --- | --- | --- | --- |
| DG02-U-109 | `spec-fmt-01` | The OpenSpec CLI and marker parser agreed on requirement IDs for 67 main capabilities at the reviewed revision. | Exercise malformed specs and missing IDs through the CI gate and retain requirement-specific historical proof. |
| DG02-U-110 | `spec-fmt-02` | Traceability tests cover active-change structure; current source and tests were inspected. | The reviewed tests do not establish the full archive, publication and revalidation lifecycle. |
| DG02-U-111 | `spec-fmt-03` | The current AGENTS instructions describe active-change authority and archive publication. | The reviewed tests do not establish stacked-change dependencies and publication order in both proposals. |
| DG02-U-112 | `coh-3d-01` | Synthetic 3D tests validate six part kinds and composite digest sensitivity to one-byte changes. | The historical claim lacks an accepted row-specific evidence bundle and digest. |
| DG02-U-113 | `coh-3d-02` | A synthetic repair fixture evaluates a new subject and refuses old attestations for its digest. | Bind the requirement to accepted historical evidence and qualify the actual downstream promotion consumer. |
| DG02-U-114 | `coh-3d-03` | Synthetic code and 3D results pass the same schema and have the same result keys. | Demonstrate one consumer decision path and applicable advisory policy end to end. |
| DG02-U-115 | `coh-3d-04` | Synthetic captures carry configuration digests and evaluator tests reject subprocess execution. | The cited historical claim lacks an accepted requirement-specific evidence bundle. |
| DG02-U-116 | `fleet-007-01` | Synthetic adapters using **digest or **registration_ref were accepted as satisfying those required names; an unnamed **kwargs adapter was rejected. | Reject catch-all parameter kinds for required names. The historical record has no cited implementation path or accepted bundle. |
| DG02-U-117 | `fleet-007-02` | Adapter tests exercise the closed error kinds, credential-shaped detail refusal and type-only exception classification. | The historical record has no cited implementation path or accepted bundle; current tests do not repair that provenance. |
| DG02-U-118 | `fleet-007-03` | Image tests exercise digest-only references, tag rejection and the standard quadlet pin. | The historical record has no cited implementation path or accepted bundle; current tests do not establish a historical run. |
| DG02-U-119 | `fleet-007-04` | Warm-pool and ephemeral-command tests cover used stock, bounds, image identity and command shape. | The historical record has no cited implementation path or accepted bundle; qualify actual runtime lifecycle separately. |
| DG02-U-120 | `fleet-004-01` | The channel import test checks the module for a fixed set of imports. | The historical record has no cited implementation path or accepted bundle; prove the host-initiated path and runtime boundary. |

The first 120 of 182 rows have detailed reviews. The next 62 begin at `DG02-U-121`. Rows 116-120 have rejected provenance because their historical citations are empty. The [remediation change](../../../qualify-dg02-spec-3d-fleet-gaps/proposal.md) tracks the observed gap and outstanding controls.

## Verify the batch

```sh
python3 scripts/evidence-validate.py \
  openspec/changes/dg-02-evidence-ledger-reconciliation/batches/batch-010/evidence \
  --expected sha256:b4156064ba176bf3b1d2cc758f57f1798392adb7834b01eab35d4a04b2c6f121
```

The manifest binds the exact test receipt and a finding for every row. Each finding hashes its disposition with the two review evidence link fields removed, using sorted compact ASCII JSON.
