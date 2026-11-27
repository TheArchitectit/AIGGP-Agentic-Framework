# DG-02 evidence review batch 004

This batch reviews `DG02-U-037` through `DG02-U-048` against AIGGP revision
`bdbd450e0275a05b319ce29d83f761e8ed552e69`. The immutable input roster still
contains 182 rows. These twelve findings remain **UNPROVEN**; the batch makes
no ledger transition and does not treat a source marker or module pass as
acceptance.

## Review scope

For each row, the disposition records the original source-record digest, the
ordered citation range and files changed in that range, current source-marker
coordinates, the requirement's named owner-spec tests, observed module
outcomes, a concrete summary of the behaviors those test modules exercise,
and the proof conjuncts still missing. The current marker coordinates are
repository-relative line numbers in the reviewed head. The original source
record digests were checked against the referenced lines in
`openspec/state-unproven.jsonl` at the reviewed head.

| Row | Requirement | Named behavior exercised by the listed tests | Remaining evidence gap |
| --- | --- | --- | --- |
| U-037 | `coh-rt-06` | Planner rejects repository-supplied evaluator code and schema-valid but unapproved evaluators. | Aggregate tests do not establish all pinned-image, no-network/no-secret runtime conditions; no canonical requirement bundle. |
| U-038 | `coh-rt-07` | Launcher and runtime tests exercise bounded writable locations, atomic export, and incomplete-output errors. | No row-specific canonical bundle or external runtime acceptance receipt. |
| U-039 | `coh-dec-01` | Decision tests exercise error precedence, dependency-blocked outcomes, and result decisions. | No isolated row-bound result receipt or canonical bundle. |
| U-040 | `coh-dec-02` | Exit-code and decision tests exercise structured failure envelopes and exit mapping. | No isolated row-bound result receipt or canonical bundle. |
| U-041 | `coh-dec-03` | Canonicalization tests exercise sorted canonical JSON and digest stability. | No isolated row-bound byte-identity receipt or canonical bundle. |
| U-042 | `coh-dec-04` | Conformance and container tests exercise error/exit mapping, caller relay, and malformed or missing result handling. | No isolated consumer receipt or canonical bundle. |
| U-043 | `coh-dec-05` | Result tests exercise stable finding ordering. | No isolated repeat-run determinism receipt or canonical bundle. |
| U-044 | `mon-enroll-01` | Registry and HTTP tests exercise single-use enrollment, heartbeat issuance, and revocation. | No accepted deployment or operational receipt and no canonical bundle. |
| U-045 | `mon-alert-01` | Alert tests exercise append-only logging, issue creation, deduplication, recurrence comments, and secret-field filtering. | No accepted hosted GitHub issue receipt and no canonical bundle. |
| U-046 | `mon-monitor-hub-01` | Tests check credential-placeholder handling and prevent secret disclosure in service responses. | They do not prove every monitor-host duty is documented or host details/credentials are absent from committed files; no canonical bundle. |
| U-047 | `coh-ctx-01` | Issuance tests exercise digest-bound context sets, signer binding, and end-to-end context issuance. | No isolated context-validation receipt or canonical bundle. |
| U-048 | `coh-ctx-02` | Issuance, modes, and CLI tests exercise authoritative stage selection and rejection of weaker requested modes. | No isolated stage-authority receipt or canonical bundle. |

The behavioral summaries point to named assertions recorded in each disposition.
The Python outcomes are shared module-level results; they are not represented as
isolated row receipts. This distinction is why every row remains UNPROVEN.
The state gate was not run because there is no proposed transition to evaluate.

## Test receipt

The sealed [test receipt](test-receipt.json) records the exact per-module
outcomes. The receipt was refreshed after reproducing the complete 34-module
run with Python 3.12.13 in this Linux checkout:

```bash
mapfile -t modules < <(../py312/bin/python -c \
  'import json; print("\n".join(json.load(open("openspec/changes/dg-02-evidence-ledger-reconciliation/batches/batch-004/test-receipt.json"))["per_module"]))')
../py312/bin/python -m pytest -q --junitxml=/tmp/dg02-batch004-audit312.xml "${modules[@]}"
node --test tests/test_guardrails_scan.mjs
```

The Python run reported **551 passed, 0 skipped, 0 failed, and 9 passing
subtests** across 34 modules. The JUnit XML SHA-256 is recorded in the receipt;
the temporary report itself is not part of this batch. The Node test file
reported all controls passing. The suite exercises shared implementation
contracts and does not supply any external or deployment acceptance result.

## Seal and unchanged scope

The [batch manifest](batch-manifest.json) records the raw disposition digest,
receipt digest, evidence-manifest digest, reviewed head, and unchanged-roster
assertion. Verify the evidence bundle from the repository root:

```sh
python3 scripts/evidence-validate.py \
  openspec/changes/dg-02-evidence-ledger-reconciliation/batches/batch-004/evidence \
  --expected sha256:728533e782a0117cb58a8c7653422dc769ec6aec8a2f978e34c6570e5cad945f
```

The validated bundle seals review findings and test outcomes only. The original
182-row roster, the source ledger, and all lifecycle states remain unchanged.
