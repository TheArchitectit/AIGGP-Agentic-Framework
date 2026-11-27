# DG-02 evidence review batch 012

**DG02-U-133 through DG02-U-144 remain UNPROVEN.** Three Luna agents collected evidence. The lead independently reviewed the requirements, source and tests at `90cd3673bae8a13a643481dd55815b0a1997a424`. All twelve historical citations were empty. No accepted historical bundle and expected digest were found for these claims. Canonical requirement validation was NOT_RUN and no lifecycle transition was made.

The [dispositions](batch-012-disposition.jsonl) bind the evidence and missing proof for each row. The [test receipt](test-receipt.json) records 74 passing Python tests and 18 passing subtests. Separate controls run the 24-test contract suite against three fixtures in an extracted package. The receipt measures the reviewed revision.

| Row | Requirement | Observation | Remaining proof |
| --- | --- | --- | --- |
| DG02-U-133 | `repo-002-04` | Boundary tests exercise exit 0 on a clean fixture, 1 on violations and 2 on an unusable manifest. The push workflow invokes the script. | Bind the historical invocation and the push change range to this requirement. |
| DG02-U-134 | `repo-003-01` | The v1 tests read closed schemas, accept the request fixture and refuse undeclared fields and missing versions. | Qualify versioned shape changes and recover historical schema and test provenance. |
| DG02-U-135 | `repo-003-02` | Version tests accept v1 and reject missing, string and future versions. The future-major case returns a single version diagnostic. | Bind the version-first diagnostics to the historical implementation and accepted evidence. |
| DG02-U-136 | `repo-004-01` | In an extracted package all 24 contract tests passed. Adding a missing required path failed the suite. Adding an unsupported required reason code left all 24 passing. | The producer must satisfy every reason code required by the consumer fixture. |
| DG02-U-137 | `repo-004-02` | Decision and receipt builders refuse inconsistent outputs, and the decision builder rejects a malformed request before returning a decision. | Recover the historical producer tests and accepted requirement-specific evidence. |
| DG02-U-138 | `repo-004-03` | Tests reject a refusal without a reason, a completion without evidence and a malformed digest. The v1 schema scan checks commercial field names. | Bind the closed reason enum, conditional evidence rule and schema inventory to historical evidence. |
| DG02-U-139 | `repo-004-04` | The package import test pins the current module set and compares it with the extraction build inputs. | Retain a measured rejection of an added undeclared dependency with the historical qualification. |
| DG02-U-140 | `fleet-001-01` | Tests check revision increments, preservation of the input state, refusal of an observation as desired state and separation of the two modules. | Bind the historical implementation and behavioral results to the immutable-state claim. |
| DG02-U-141 | `fleet-001-02` | Pool tests name missing and unknown fields and reject persistent mode, invalid bounds and an unpinned image. | Measure the complete required-field inventory and recover accepted historical evidence. |
| DG02-U-142 | `fleet-001-03` | Model tests reject synthetic secret-shaped keys by path, check that the diagnostic omits the test value and accept a valid profile reference. | Bind these diagnostic and reference checks to the historical claim. |
| DG02-U-143 | `fleet-001-04` | Host eligibility tests cover runtime, architecture, pool allow-list and active state, and accept an eligible assignment. | Recover the original source and accepted evidence for the eligibility decision. |
| DG02-U-144 | `fleet-001-05` | Transition tests exercise slot accounting, release, a drain with outstanding work and rollout digest validation, rollback and revision updates. | Bind the historical capacity, drain and rollout transitions to accepted evidence. |

This batch brings detailed review to 144 of 182 rows. The remaining 38 begin at `DG02-U-145`. The [remediation change](../../../qualify-dg02-boundary-contract-domain-gaps/proposal.md) tracks the observed gap and outstanding controls.

## Verify the batch

```sh
python3 scripts/evidence-validate.py \
  openspec/changes/dg-02-evidence-ledger-reconciliation/batches/batch-012/evidence \
  --expected sha256:bf8fc918229affdcc2540277a06d11aab2fd15de33364354f3b8206f363a4aac
```

The manifest binds the exact test receipt and a finding for every row. Each finding hashes its disposition with the two review evidence link fields removed, using sorted compact ASCII JSON.

The [CI receipt for the batch commit](ci-receipt.md) pairs every AI02 App check with its UCS03 job and records the two failures.
