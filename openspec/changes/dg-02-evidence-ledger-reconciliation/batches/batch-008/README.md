# DG-02 evidence review batch 008

**DG02-U-085 through DG02-U-096 remain UNPROVEN.** Three Luna agents collected evidence. The lead independently reviewed the requirements, source, cited Git ranges and tests at `febe1ef2fa10f131fb7955db4171e77e670f4c50`. No row-specific historical accepted bundle and digest were found. Canonical requirement validation was NOT_RUN and no lifecycle transition was made.

The [dispositions](batch-008-disposition.jsonl) bind the evidence and missing proof for each row. The [test receipt](test-receipt.json) records 202 passing tests and seven passing subtests. The receipt is current-tree evidence and does not prove historical closure.

| Row | Requirement | Observation | Remaining proof |
| --- | --- | --- | --- |
| DG02-U-085 | `coh-pkg-01` | Package resolution and expected digest tests exercised package loading and rejection. | Missing-package adoption-policy and moving-reference end-to-end scenarios need row-bound proof. |
| DG02-U-086 | `coh-pkg-02` | Package and planning tests exercise unsupported input, duplicate IDs, reference validation, and cycles. | Two normative files with identical versus conflicting IDs and declared approval state require package-level proof. |
| DG02-U-087 | `coh-pkg-03` | Normative tests exercise stable digests after informative-only changes and a changed digest after reclassification. | The full archive digest behavior and historical accepted evidence are not established. |
| DG02-U-088 | `coh-pkg-04` | A nonexistent declared import with a syntactically present digest was accepted by package.resolve; an import lacking a digest was rejected. | Resolve and verify imported content and detect import cycles before evaluation; the probe does not exercise the full service. |
| DG02-U-089 | `coh-pkg-05` | A requirement-bearing JSON file classified informative was accepted by package.resolve and excluded from the returned normative inventory. | Classifier rejection and authenticated-approval handling need implementation and independent controls. |
| DG02-U-090 | `rel-upload-01` | The isolated PyPI publish branch attempted one upload on success. When the first upload was simulated to fail, it built and retried, then exited zero. | The failed-upload abort requirement conflicts with the observed retry; the isolated branch does not establish whole-pipeline behavior. |
| DG02-U-091 | `rel-artifact-01` | The deploy sandbox test rejects an empty must_contain list. | Missing-field and absent-contract skip scenarios need row-bound controls. |
| DG02-U-092 | `rel-fixcommit-01` | Tests reject nonexistent bundled short SHAs and accept local short SHAs. The overlay short-SHA test expects an unresolved value to pass. | Verify 7–40 character overlay fix commits against the owner repository; missing history is currently only a warning for bundled entries. |
| DG02-U-093 | `rel-target-01` | Deployment dispatch fixtures exercise schema failure and skip behavior in a consumer layout. | Prove all release gates target the consumer diff and exercise a dirty submodule independently. |
| DG02-U-094 | `rel-audit-01` | Fixture audit tests classify direct runtime and dependent-path HIGH findings as blocking and dev-only findings as warnings. | The cited historical claim lacks a sealed row-bound receipt for the required pre-commit exit behavior. |
| DG02-U-095 | `rule-truth-01` | The hygiene implementation checks enabled semantic rule IDs against registered checkers and validates pattern schema. | The cited scoping tests do not establish hygiene failure for an enabled unknown checker or complete all-shipped-rule enforcement. |
| DG02-U-096 | `rule-behavior-01` | The template test checks extracted-rules absence and the skills directory exists. | A per-former-rule mapping from documentation to a covering skill template remains unverified. |

The first 96 of 182 rows have detailed reviews. The next 86 begin at `DG02-U-097`. The [remediation change](../../../qualify-dg02-package-release-rule-gaps/proposal.md) tracks the observed gaps and outstanding controls.

## Verify the batch

```sh
python3 scripts/evidence-validate.py \
  openspec/changes/dg-02-evidence-ledger-reconciliation/batches/batch-008/evidence \
  --expected sha256:5838339bd6017885acb943ee9d87d3a6ff6f383938408920ee70943c848d2cb4
```

The manifest binds the exact test receipt and a finding for every row. Each finding hashes its disposition with the two review evidence link fields removed, using sorted compact ASCII JSON.
