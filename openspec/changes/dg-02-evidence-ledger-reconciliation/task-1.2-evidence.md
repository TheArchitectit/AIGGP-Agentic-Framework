# DG-02 task 1.2 — row-level candidate review

**Review revision:** `2bf84ddab55695340e91ceb026b319fcae7de3e4` (isolated detached worktree)
**Input baseline:** `7ec9983466f1ba5dada04c29700f68dfaed15d9e`
**Input digest:** `sha256:5de4a469e82c1b40cc750f9ab57b8b3c055f728fd6c925466f8d8ad81dd35804`
**Disposition:** The candidate review covers all 182 input rows in roster order. All 182 retain `UNPROVEN`.

## Review performed

The per-row JSONL records the original row key and source-record digest, cited endpoint resolution and strict ancestry, complete changed-file list for resolved ranges, current source-marker locations (with line numbers), marker-path overlap with the cited range, test-file references, evidence bundle discovery, validator/test result, state-gate result, and explicit missing conjuncts. Test-file references are discovery findings. The row-level tests and sealed evidence require separate review.

The pinned input manifest was checked against Git at its baseline: **58/58** listed paths resolve to the recorded blob IDs. The roster contains **182** unique `(spec, requirement)` pairs.

## Results

- **113** cited ranges resolve and their endpoints are in strict ancestry order.
- **69** citations are not usable ordered commit ranges: 61 are empty, 4 cite `templates/github/workflows/`, and 4 cite unresolved short commit `4b69262`.
- Current source-marker locations exist for **172** requirements. For **107** rows, a current marker path also appears in the cited changed-file range. Each row labels these as marker-only locations; the report does not infer that the marked code enforces the requirement or that it executed.
- **96** requirements have a test-file reference discoverable under `tests/`. The JSONL records these as references, with execution result `NOT_RUN`; no row-bound passing test record was found.
- No matching tracked row-specific sealed bundle and expected manifest digest was discovered for these 182 rows. Their validator result is `NOT_RUN`, not pass.
- The tracked `openspec/evidence/doc-truth` bundle is an existing but unrelated example. At the canonical Git checkout, `scripts/evidence-validate.py --expected sha256:d6e020b5d26f03ef700ebf3115bcba00807e017ea535b99293b88cf284f2a781 openspec/evidence/doc-truth` returned `evidence-validate: OK — bundle verified, claims consistent`. It was not attributed to any roster row.
- A per-row state-gate acceptance is `NOT_RUN`: the gate adjudicates ledger transitions, and no candidate transition is created from this review. An aggregate state-gate replay over `7ec9983466f1ba5dada04c29700f68dfaed15d9e..2bf84ddab55695340e91ceb026b319fcae7de3e4` returned `spec-state: OK` and reconciled 7 commits. This aggregate result does not adjudicate the unproven roster rows individually, so each row remains `NOT_RUN` for state-gate acceptance because no candidate transition was created.

These findings support recording the review outcome, not promoting requirements. Rows lacking resolved provenance, relevant changed-file overlap, a row-specific passing test record, or accepted sealed evidence remain `UNPROVEN` as shown individually in the JSONL.

## Validation and change boundary

OpenSpec CLI **1.14.3** strict validation of `dg-02-evidence-ledger-reconciliation` passed after the report artifacts were added. Task 1.2 still requires review of the implementation and behavioral evidence for the individual requirements. Task 2.1 requires sealing and validating the aggregate disposition.

**Canonical Git JSONL SHA-256:** `sha256:a77e3e9966e72dd8c2233444e424d4e39fb4e074fe60a567616019c19addac79`
