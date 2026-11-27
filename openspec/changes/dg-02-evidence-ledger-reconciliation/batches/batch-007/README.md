# DG-02 evidence review batch 007

**DG02-U-073 through DG02-U-084 remain UNPROVEN.** Three Luna agents collected evidence. The lead independently reviewed the requirements, source, cited Git ranges and tests at `5df1164e039084475c03683b15607fbca07b34c6`. No row-specific historical accepted bundle and digest were found. Canonical requirement validation was NOT_RUN and no lifecycle transition was made.

The [dispositions](batch-007-disposition.jsonl) bind the evidence and missing proof for each row. The [test receipt](test-receipt.json) records 199 passing tests and 107 passing subtests. The receipt is current-tree evidence and does not prove historical closure.

| Row | Requirement | Observation | Remaining proof |
| --- | --- | --- | --- |
| DG02-U-073 | `mon-hub-01` | Configuration, startup and service tests exercise parts of the hub. | No reviewed test establishes one deployment and hub-only peer configuration for every runner. |
| DG02-U-074 | `mon-channels-01` | Monitor tests exercise API checks and heartbeat paths. | No reviewed control demonstrates API checks for a registered repository runner without a heartbeat and independently establishes heartbeat-only stale detection. |
| DG02-U-075 | `mon-registry-01` | Registry tests cover schema, placeholder example, and credential revocation. | Persistent volume deployment and complete committed host-data hygiene need row-bound evidence. |
| DG02-U-076 | `mon-deadman-01` | Watchdog tests cover unreachable, stale, disabled and malformed health responses. | The cited window does not establish installed systemd failure or hosted-runner exclusion. |
| DG02-U-077 | `mon-local-01` | Config defaults to loopback, but HUB_BIND_HOST=0.0.0.0 is accepted and server binds the configured value. | The local-only listener requirement needs enforced and independently tested address boundaries. |
| DG02-U-078 | `coh-int-01` | Wrapper and template tests cover invocation and pinned runtime. | Equivalent end-to-end canonical results across actual local and CI adapters need row-bound evidence. |
| DG02-U-079 | `coh-int-02` | Monitor and coherence tests exercise fleet reports and alert behavior. | Preservation of all five required advisory and identity fields through reporting needs proof. |
| DG02-U-080 | `coh-int-03` | 3D slice tests cover changed subject and attestation refusal. | Consumer-level PASS and centrally approved ADVISORY promotion policy needs proof. |
| DG02-U-081 | `coh-int-04` | OAP tests exercise schema and signature validation. | The signed-but-unevaluated upstream artifact needs an explicit decision-level rejection control. |
| DG02-U-082 | `coh-int-05` | Wrapper and monitor tests cover error and nonpassing behavior. | A row-bound timeout and malformed canonical result receipt is missing. |
| DG02-U-083 | `coh-int-06` | Workflow template tests exercise explicit skip branches and nonzero outcome. | The reviewed receipt does not demonstrate the entire CI-to-hub nonpassing path. |
| DG02-U-084 | `coh-int-07` | Runbook and monitor tests cover parts of repository and branch monitoring. | A two-repository isolation control, including empty watched branches, needs row-bound proof. |

The first 84 of 182 rows have detailed reviews. The next 98 begin at `DG02-U-085`. The [remediation change](../../../qualify-dg02-hub-integration-gaps/proposal.md) tracks the configuration gap and behavioral evidence work.

## Verify the batch

```sh
python3 scripts/evidence-validate.py \
  openspec/changes/dg-02-evidence-ledger-reconciliation/batches/batch-007/evidence \
  --expected sha256:c3208e61de610df2e3152f86916528f32c52ea11ba74c0c197e6dfc58efedda0
```

The manifest binds the exact test receipt and a finding for every row. Each finding hashes its disposition with the two review evidence link fields removed, using sorted compact ASCII JSON.
