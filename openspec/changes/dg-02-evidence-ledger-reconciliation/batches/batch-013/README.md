# DG-02 batch 013 handoff

**DG02-U-145 through DG02-U-156 remain UNPROVEN.** All twelve original citations are empty. Three Luna collectors inspected the owning specifications, implementation and tests at `c1311159e5c13f44c1bc514713c6578d57cb5065`. The lead independently checked each row against the baseline, Git history, named tests, canonical manifests and ledger. The batch seal authenticates the review. Historical requirement acceptance still needs its own bundle and trusted expected digest.

The [test receipt](test-receipt.json) records 244 passing tests and 210 passing subtests. Phase B separately collected 2,195 tests in the core copy. The [dispositions](batch-013-disposition.jsonl) identify the tests or command for each row and the source blobs inspected.

| Row | Requirement | Observed behavior | Remaining proof |
| --- | --- | --- | --- |
| DG02-U-145 | `repo-005-01` | The real extraction rehearsal ran the package suite with only its three declared core inputs. The import-surface pin passed. | Bind the historical isolated run, build-input list and tests to the claim. |
| DG02-U-146 | `repo-005-02` | With Node, the boundary-absent core collected 2,195 tests and the pattern scan passed. Without Node, it still collected 2,195, skipped the required scan and exited 0. | Require a non-success or incomplete verdict for a missing scanner runtime, plus a requirement-bound historical receipt. |
| DG02-U-147 | `repo-005-03` | The only declared invocation site is the CI workflow. Tests pin its path, accept its reference, reject an undeclared reference and reject a declaration inside the package. | Recover the reviewed manifest, gate and corresponding historical test inputs. |
| DG02-U-148 | `fleet-008-01` | The lifecycle refuses a second job, has a closed transition table, and refuses a return from a terminal state to warm capacity. | Bind the historical state table, terminal paths and warm-pool accounting to accepted evidence. |
| DG02-U-149 | `fleet-008-02` | Cleanup fixtures require the disposal fields, permit an unknown job identity, and block replacement for a predecessor whose cleanup has neither been proved nor quarantined. | Bind the historical cleanup and admission decisions to their underlying proof records. |
| DG02-U-150 | `fleet-008-03` | A cleanup failure can move the instance to a recorded quarantine. The model retains its identity, failure and time and excludes it from warm capacity. | Recover the original quarantine transitions and warm-stock evidence. |
| DG02-U-151 | `fleet-008-04` | Missing, nonpositive and over-limit resource values were rejected. The rendered command carried the configured CPU, memory and PID limits. | Bind historical validation and command rendering to the original resource-limit claim. |
| DG02-U-152 | `fleet-008-05` | The lifecycle tests classify modeled failures into named error kinds, including unexpected exceptions, and exercise the adapter boundary. | Recover accepted evidence matching the original typed-error cases. |
| DG02-U-153 | `fleet-002-01` | Normal planning simulated two free slots becoming one. A separately constructed plan with the same base, changes and identity displayed caller-supplied capacity of 20 to 19. | Qualify the integrity of the displayed capacity summary and bind the historical plan evidence. |
| DG02-U-154 | `fleet-002-02` | Apply rechecked the base revision, required scopes and changes. A refused multi-change apply retained the refusal without committing earlier change entries. | Bind historical revision, principal and apply-time revalidation results. |
| DG02-U-155 | `fleet-002-03` | Retrying the same key and plan returned the recorded revision. A different plan for that key was refused, and the original ledger remained intact. | Bind the original apply, replay and conflicting-key records to the historical claim. |
| DG02-U-156 | `fleet-002-04` | The audit suite refused sequence gaps and backwards time, retained the refusal entry and rejected a synthetic credential-shaped reason without repeating its value. | Recover the original audit and refusal records and verify their requirement-specific expected digest. |

The extraction QA references a [successful historical workflow](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/40066836124). The plan QA documents a [failed historical workflow](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/40067748051). Both commits are ancestors of the reviewed source. Neither reference supplies an accepted bundle and expected digest for these rows.

## Independent audit

The independent auditor accepted this batch review at the seal below. The auditor recomputed all 12 disposition hashes and 13 evidence-object hashes, checked the 40 named row-to-test references and replayed the extraction command for row 146. The standalone validator rejected each of 13 individually altered objects and an incorrect expected seal. The lead separately verified source bindings, test identities, controls and the chain through batch 012. Both parties retained all twelve UNPROVEN verdicts.

## Verify and resume

```sh
python3 scripts/evidence-validate.py openspec/changes/dg-02-evidence-ledger-reconciliation/batches/batch-013/evidence --expected sha256:3fe84def525a3b1f0cd88f7f787b5a82eefdfc51b23335b83222a357b57a3efb
```

The test receipt binds the [previous seal](../batch-012/batch-manifest.json). Each row finding binds the sorted compact ASCII JSON disposition with the two review-evidence link fields removed. The [batch manifest](batch-manifest.json) records the disposition and receipt digests.

**Resume at DG02-U-157.** Detailed review covers 156 of 182 rows. All 182 remain UNPROVEN. The extraction and plan gaps have [qualification tasks](../../../qualify-dg02-extraction-lifecycle-plan-gaps/tasks.md) and a [role-based sprint plan](../../../qualify-dg02-extraction-lifecycle-plan-gaps/sprint-plan.md).

For push CI, the lab CI operator should use the exact commit that added this handoff. Match each of the ten native jobs across CI, Open-item gates, Spec-state and Release Coverage to its AI02 App check, checkout SHA, runner ID and UCS03 service start. Record missing, pending, skipped, failed or wrong-runner results individually. See the [App and runner evidence procedure](../../../qualify-consumer-delivery-evidence/hosted-pilot.md). Release Coverage requires an annotated version tag at the pushed commit. The existing v1.4.0 tag identifies the reviewed source.
