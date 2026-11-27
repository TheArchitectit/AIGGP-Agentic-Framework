# DG-02 evidence review batch 011

**DG02-U-121 through DG02-U-132 remain UNPROVEN.** Three Luna agents collected evidence. The lead independently reviewed the requirements, current source and tests at `39ccf6fdd8a99df96b5b473ff62026d8d6948644`. All 12 historical citations were empty, so no cited Git ranges could be reviewed. No row-specific historical accepted bundle and digest were found. Canonical requirement validation was NOT_RUN and no lifecycle transition was made.

The [dispositions](batch-011-disposition.jsonl) bind the evidence and missing proof for each row. The [test receipt](test-receipt.json) records 123 passing Python tests and 72 passing subtests, plus reproducible synthetic operation controls. The receipt is current-tree evidence and does not prove historical closure.

| Row | Requirement | Observation | Remaining proof |
| --- | --- | --- | --- |
| DG02-U-121 | `fleet-004-02` | Channel tests exercise bound enrollment, expiration, one-time use and key uniqueness. | The historical citation is empty; accepted row-specific evidence and persistence-boundary proof are missing. |
| DG02-U-122 | `fleet-004-03` | Channel tests exercise canonical signed bytes, forged reports and verifier failures using a deterministic test double. | The historical citation is empty; verifier integration and an accepted row-specific bundle remain unproven. |
| DG02-U-123 | `fleet-004-04` | Channel tests exercise replay rejection, sequence gaps, nonce reuse and verification-before-state-update. | The historical citation is empty; accepted row evidence and the intended persistence boundary remain unproven. |
| DG02-U-124 | `fleet-004-05` | Channel tests exercise overlapping rotation, expiration and revocation for active and retiring credentials. | The historical citation is empty; accepted row-specific historical evidence is missing. |
| DG02-U-125 | `fleet-005-01` | Synthetic operations rejected command names; a malformed value produced a generic type refusal, and an earlier permitted value was inspected before a later command name. | Validate all forbidden names before values and name forbidden parameters even with malformed values. |
| DG02-U-126 | `fleet-005-02` | Capability tests exercise default deny, adapter presence, read-only work and explicit cancellation policy. | The historical citation is empty and no accepted requirement-specific bundle was found. |
| DG02-U-127 | `fleet-005-03` | Operation and receipt tests exercise secret-shaped value refusal, opaque references and bounded details. | The historical citation is empty and no accepted requirement-specific bundle was found. |
| DG02-U-128 | `fleet-005-04` | Ledger tests exercise issued-key and host binding, evidence requirements, idempotency and conflicting receipts. | The historical citation is empty; accepted historical proof and the intended persistence boundary remain unproven. |
| DG02-U-129 | `fleet-005-05` | Ledger and migration tests exercise manager-built receipts, contract mapping and enrollment option coverage. | The historical citation is empty; accepted requirement-specific historical proof is missing. |
| DG02-U-130 | `repo-002-01` | Boundary tests exercise undeclared files, declared paths and changed forbidden roots. | The historical citation is empty and no accepted requirement-specific historical bundle was found. |
| DG02-U-131 | `repo-002-02` | Boundary tests exercise malformed manifests and separate-grant rejection. | The historical citation is empty; direct proof of every license and README clause remains unbound. |
| DG02-U-132 | `repo-002-03` | Boundary tests exercise rejected core imports and allowed boundary-to-core imports. | The historical citation is empty; historical CI enforcement and accepted row-specific evidence remain unproven. |

The first 132 of 182 rows have detailed reviews. The next 50 begin at `DG02-U-133`. Rows 121-132 have rejected provenance because their historical citations are empty. The [remediation change](../../../qualify-dg02-agent-operations-boundary-gaps/proposal.md) tracks the observed gap and outstanding controls.

## Verify the batch

```sh
python3 scripts/evidence-validate.py \
  openspec/changes/dg-02-evidence-ledger-reconciliation/batches/batch-011/evidence \
  --expected sha256:dbfc962b838b0b692895e521ab9addac49f8c134bbc50ce50bd00e4cde645c2d
```

The manifest binds the exact test receipt and a finding for every row. Each finding hashes its disposition with the two review evidence link fields removed, using sorted compact ASCII JSON.
