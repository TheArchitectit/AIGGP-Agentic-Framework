# DG-02 evidence review

The baseline contains 182 requirements across 42 published capabilities. Detailed independent reviews cover rows 001-156. All 182 requirements remain **UNPROVEN**. The remaining 26 start at **DG02-U-157**. [Baseline roster](unproven-baseline-roster.jsonl) and [reconciliation tasks](tasks.md).

Use the batch summaries to find each requirement's observations, missing proof and validator command. Each manifest records the reviewed revision, row IDs and expected batch seal. An accepted batch seal verifies the review record. Requirement closure separately requires attributable implementation history and an accepted requirement-specific evidence bundle. [Proof rules](design.md) and [initial discovery](task-1.2-evidence.md).

| Batch | First row | Last row | Evidence |
| --- | --- | --- | --- |
| [batch-001](batches/batch-001/README.md) | DG02-U-001 | DG02-U-012 | [Manifest](batches/batch-001/batch-manifest.json) |
| [batch-002](batches/batch-002/README.md) | DG02-U-013 | DG02-U-024 | [Manifest](batches/batch-002/batch-manifest.json) |
| [batch-003](batches/batch-003/README.md) | DG02-U-025 | DG02-U-036 | [Manifest](batches/batch-003/batch-manifest.json) |
| [batch-004](batches/batch-004/README.md) | DG02-U-037 | DG02-U-048 | [Manifest](batches/batch-004/batch-manifest.json) |
| [batch-005](batches/batch-005/README.md) | DG02-U-049 | DG02-U-060 | [Manifest](batches/batch-005/batch-manifest.json) |
| [batch-006](batches/batch-006/README.md) | DG02-U-061 | DG02-U-072 | [Manifest](batches/batch-006/batch-manifest.json) |
| [batch-007](batches/batch-007/README.md) | DG02-U-073 | DG02-U-084 | [Manifest](batches/batch-007/batch-manifest.json) |
| [batch-008](batches/batch-008/README.md) | DG02-U-085 | DG02-U-096 | [Manifest](batches/batch-008/batch-manifest.json) |
| [batch-009](batches/batch-009/README.md) | DG02-U-097 | DG02-U-108 | [Manifest](batches/batch-009/batch-manifest.json) |
| [batch-010](batches/batch-010/README.md) | DG02-U-109 | DG02-U-120 | [Manifest](batches/batch-010/batch-manifest.json) |
| [batch-011](batches/batch-011/README.md) | DG02-U-121 | DG02-U-132 | [Manifest](batches/batch-011/batch-manifest.json) |
| [batch-012](batches/batch-012/README.md) | DG02-U-133 | DG02-U-144 | [Manifest](batches/batch-012/batch-manifest.json) |
| [batch-013](batches/batch-013/README.md) | DG02-U-145 | DG02-U-156 | [Manifest](batches/batch-013/batch-manifest.json) |

Batch 012 found that adding an unsupported reason code to the consumer fixture leaves the v1 contract suite passing. The corresponding qualification task is open. [Qualification tasks](../qualify-dg02-boundary-contract-domain-gaps/tasks.md).

Batch 013 records current source and synthetic-test observations for extraction, job lifecycle, and fleet planning. All twelve claims remain UNPROVEN because historical provenance and accepted row-bound evidence are not established. The extraction rehearsal exits successfully after skipping the scan when Node is absent. A plan can retain its ID when a caller replaces its capacity summary. Track both findings in [extraction and lifecycle qualification](../qualify-dg02-extraction-lifecycle-plan-gaps/sprint-plan.md).

The repository index covers published requirements and change packages. [OpenSpec index](../../INDEX.md).
