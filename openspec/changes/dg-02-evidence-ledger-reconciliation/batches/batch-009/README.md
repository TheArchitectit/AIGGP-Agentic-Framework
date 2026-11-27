# DG-02 evidence review batch 009

**DG02-U-097 through DG02-U-108 remain UNPROVEN.** Three Luna agents collected evidence. The lead independently reviewed the requirements, source, cited Git ranges and tests at `259a5708e25ebf4222db8cd0525f739ba6f59c77`. No row-specific historical accepted bundle and digest were found. Canonical requirement validation was NOT_RUN and no lifecycle transition was made.

The [dispositions](batch-009-disposition.jsonl) bind the evidence and missing proof for each row. The [test receipt](test-receipt.json) records 159 passing Python tests, two passing subtests, 55 Node assertions and 16 shell assertions. The Python scanner harness also invokes the Node suite, so those counts overlap. The receipt is current-tree evidence and does not prove historical closure.

| Row | Requirement | Observation | Remaining proof |
| --- | --- | --- | --- |
| DG02-U-097 | `rule-marker-01` | Traceability tests cover Python and SQL markers and blocking mode. | Language-specific scaffold syntax and the historical accepted receipt need proof. |
| DG02-U-098 | `mon-online-01` | Tests exercise stale heartbeat and healthy cases using synthetic GitHub responses. | The reviewed tests do not establish the complete real dead-quadlet scenario and its historical receipt. |
| DG02-U-099 | `mon-queue-01` | A 45-minute-old synthetic run generated the same alert with a registered runner and an empty runner list; the detail did not name a label. | Match registered labels, apply per-repository thresholds and include the required alert details. |
| DG02-U-100 | `mon-gates-01` | Tests cover failed and nonpassing check conclusions. A synthetic full SHA was reported as an eight-character prefix. | Prove default-branch selection and unambiguous commit identification alongside a historical receipt. |
| DG02-U-101 | `mon-drift-01` | A synthetic successful run two hours old generated no alert. Source uses 24 hours plus grace. | An hourly-schedule case exceeds one period plus grace; per-workflow schedule handling needs implementation. |
| DG02-U-102 | `gate-tscn-01` | Scene inventory tests exercise connected, nested and orphaned buttons. | The cited historical range lacks a sealed requirement-specific test receipt. |
| DG02-U-103 | `gate-rstest-01` | The Node scanner suite exercises cfg(test) module suppression and a production violation. | The cited historical range lacks a sealed requirement-specific test receipt. |
| DG02-U-104 | `gate-size-01` | File-size tests exercise a 550-line pytest file and test hard limits. | The cited historical range lacks a sealed requirement-specific test receipt. |
| DG02-U-105 | `coh-sec-01` | Containment tests exercise inventory and selector traversal, symlink escape, captured facts and non-disclosure. | Establish named-path and invalid-input exit-class behavior through the complete service and accepted historical evidence. |
| DG02-U-106 | `mon-sec-01` | Hardening tests exercise body-size rejection, idle SIGTERM and concurrent enrollment. | The concurrency test permits 401 as well as the specified already_enrolled result for the losing request. |
| DG02-U-107 | `mon-sec-02` | Registry and isolated enrollment tests exercise hashed verifiers, revocation and a mode-0600 token file without output disclosure. | A local stubbed harness does not establish CI-log behavior or accepted historical evidence. |
| DG02-U-108 | `ci-sec-01` | Template tests audit shipped workflow actions and image references; the historical citation templates/github/workflows/ is absent. | Establish valid commit provenance for templates/github-workflows/ and prove the remaining health-check, adjacent-version and secrets drop-in clauses. |

The first 108 of 182 rows have detailed reviews. The next 74 begin at `DG02-U-109`. Row 108 has rejected provenance because its cited path is absent and is not a commit range. The [remediation change](../../../qualify-dg02-monitor-scanner-security-gaps/proposal.md) tracks the observed gaps and outstanding controls.

## Verify the batch

```sh
python3 scripts/evidence-validate.py \
  openspec/changes/dg-02-evidence-ledger-reconciliation/batches/batch-009/evidence \
  --expected sha256:111a0bc2d2d101c731ffad796787231bab355eb238bcd9d37ff73d0d11e20296
```

The manifest binds the exact test receipt and a finding for every row. Each finding hashes its disposition with the two review evidence link fields removed, using sorted compact ASCII JSON.
