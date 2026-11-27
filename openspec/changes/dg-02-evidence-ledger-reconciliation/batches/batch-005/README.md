# DG-02 evidence review batch 005

All 12 rows from `DG02-U-049` through `DG02-U-060` remain **UNPROVEN**. The reviewed
framework commit is `383eb4dc4077a44d9e834ef54142d325455ca682`. Batch 005 brings
detailed coverage to 60 of 182 rows. 122 await detailed review, starting at
`DG02-U-061`. The batch records zero lifecycle transitions.

Three Luna agents collected leads. The lead checked each against the source record,
the owning requirement, its enforcement and tests, and the two Git endpoints.
All 12 cited windows are ordered, nonempty and reachable from the reviewed head.
The ledger contained no matching transition. The five checked-in evidence manifests
belonged to doc-truth and batches 001 through 004. No accepted requirement bundle
or expected digest for these claims was found, so the canonical requirement
validator has a `NOT_RUN` disposition for each row.

| Row | Requirement | Observed evidence | Outstanding proof or counterevidence |
| --- | --- | --- | --- |
| DG02-U-049 | `coh-ctx-03` | Replay reproduced the decision and omitted the Stage 2 attestation. An expired exception blocked at Stage 3. | Admission of a historical replay under current promotion authority. |
| DG02-U-050 | `coh-ctx-04` | The loader checked the captured bytes and the evaluator distinguished matching, mismatching and missing facts. | A fresh policy-granted recapture traced to its new digest and recomputed assertion. |
| DG02-U-051 | `coh-ctx-05` | Changing the context, facts or plugins, exceeding TTL or retention, or revoking a signer produced a cache miss. | The consumer completing reevaluation after the partial-key miss. |
| DG02-U-052 | `coh-ev-01` | Two distinct signatures verified over the same decision bytes. The decision schema excluded attestation fields. | An accepted requirement bundle for the cited claim. Both named scenarios have local test coverage. |
| DG02-U-053 | `coh-ev-02` | Two findings sealed and verified. A write refusal raised an error, and an upload retry preserved and resent the sealed bytes. | The applicable stage policy for confirmed remote durability and a full promotion-path write-failure receipt. |
| DG02-U-054 | `coh-ev-03` | A signed, two-finding Stage 2 run passed offline integrity verification. | Reproduction of the finding on a supported replacement runner using the recorded inputs and evaluator. |
| DG02-U-055 | `coh-ev-04` | A separate channel stored the inputs. Missing authorization denied reads, and expired retention invalidated the cache. | A complete reevaluation using re-supplied inputs after expiry. |
| DG02-U-056 | `coh-ev-05` | Verification rejected substituted inputs, revoked keys and expired keys using synthetic authority. | Signer authority at the cited promotion decision. Three isolated tests required the synthetic signer fixture. |
| DG02-U-057 | `coh-ev-06` | A declared secret was removed from the stored finding. A disabled scrubber caused sealing to fail. | Exclusion of unrelated sensitive text already present in an allowed excerpt. |
| DG02-U-058 | `coh-ev-07` | Normative reclassification changed the package digest. Informative-only edits preserved it. | An enforced rejection of D2 when presented with the scoped, time-bound detached approval for D1. |
| DG02-U-059 | `fw-ci-01` | The Python and Node suite ran on UCS03 for the reviewed main push. | The workflow excludes fork PRs. The branch API reported unprotected main and no applicable rules. |
| DG02-U-060 | `fw-ci-02` | The self-gates ran on UCS03. The empty regression range failed with exit 2. | The default pattern scan exited 0 with 50 warnings. The review found no waiver accounting for all 50. |

The [row dispositions](batch-005-disposition.jsonl) identify source locations,
owner-spec references, exact changed paths, test node IDs and remaining gaps.
The marker lists cover implementation files. For rows 059 and 060 the literal
requirement markers appear in the workflow contract test at
`tests/test_template_supply_chain.py:1`. The dispositions separately cite the
workflow steps that implement the checks and the App and native jobs at the reviewed commit.
The suite ran on `ucs03-devgate-spare2`, and the self-gates ran on `ucs03-devgate`.
Both jobs completed with zero skipped steps. [Suite job](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46032945029/job/140621074277) /
[suite App check](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/runs/140630212425)
and [self-gates job](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46032945029/job/140621073801) /
[self-gates App check](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/runs/140630152658).

## Test receipt

The lead's run across 18 owner and supporting modules passed 377 tests and
18 subtests. A second run selected 43 distinct nodes for these rows. It passed
40 and failed three in `TestSignAndVerify` during synthetic signer setup.
All three passed when rerun with the repository's `tests.fixtures.coherence.fixtures.cli_env()`
in the pytest child process. Every attempt had zero skips. The [test receipt](test-receipt.json)
records the commands, environment for the retry, node-to-row mapping, initial
failures and individual JUnit file hashes. The two selections overlap.

## Verifying the seal

From the repository root, verify the 13 finding objects against the recorded digest.

```sh
python3 scripts/evidence-validate.py \
  openspec/changes/dg-02-evidence-ledger-reconciliation/batches/batch-005/evidence \
  --expected sha256:517a5a7c24967cfcdc6cfd469f179148d0b31fb9036c9c6dd67925db56649c69
```

The [batch manifest](batch-manifest.json) also records the raw SHA-256 of the
disposition and test receipt. To check each row binding, remove only
`review_evidence_ref` and `review_evidence_digest` from the parsed row,
serialize with Python JSON using sorted keys, ASCII escapes and separators
`(',', ':')`, and hash those bytes with SHA-256. Its finding's `observed`
field includes that digest. The thirteenth finding binds the exact receipt
file bytes, including its final newline. This seal covers the review.
