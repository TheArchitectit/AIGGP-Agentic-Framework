# DG-02 evidence review batch 006

**DG02-U-061 through DG02-U-072 remain UNPROVEN.** Three Luna agents collected
evidence. The lead independently checked the source records, Git history,
requirements, implementations, tests and synthetic consumer outcomes at
`666cbed7caa59d315fb1ecde780a7661eb4828ac`.

The [dispositions](batch-006-disposition.jsonl) give the enforcement locations,
exact test identifiers and remaining proof for each row. All 12 original Git
windows were nonempty, ordered, and reachable from the reviewed commit. Six
checked-in evidence manifests were present (doc-truth and batches 001-005).
The review found no requirement-specific bundle and accepted digest for these
historical claims. Each row therefore records its canonical requirement validator
as `NOT_RUN`. The batch makes zero lifecycle transitions. Detailed review now
covers 72 of the 182 original rows. The next 110 start at `DG02-U-073`.

| Row | Requirement | Observed behavior and outstanding proof |
| --- | --- | --- |
| 061 | `fw-ci-03` | All 35 external action references in nine of the ten workflow files used a full commit SHA. A synthetic mutable tag failed the pin test. The reviewed run was a main push. |
| 062 | `game-reg-04` | Logging the same failure twice preserved the first entry and appended the second. With default IDs, the scanner reported two hits on one line. The scenario calls for one. |
| 063 | `game-reg-05` | A registered literal blocked both staged and unstaged pre-commit scans with exit 1, the failure ID and line. The historical claim specifies a registered NULL_DEREF case. |
| 064 | `game-reg-06` | The logger saved a seed and input trace and refused incomplete submissions. Replay and adjudication of a later divergence remain unverified. |
| 065 | `game-reg-01` | Guard-window, preload and comment cases ran. A pressed-signal connection produced ORPHAN_SIGNAL at the expected file and line and blocked pre-commit. Historical closure evidence is missing. |
| 066 | `game-reg-02` | The scanner distinguished Go from Markdown, scoped allow annotations to the matching ID, and honored project ignores in the tested discovery path. Historical closure evidence is missing. |
| 067 | `game-reg-03` | Both empty-scope runs printed NOTHING SCANNED. Default mode exited 0 and strict mode exited 2. Historical closure evidence is missing. |
| 068 | `rule-config-01` | The project allowlist worked. The schema gate skipped the spec's `schema-contract.json` (exit 2). Changing only the filename to `schema-health.json` detected the missing SQLite column (exit 1). |
| 069 | `rule-fresh-01` | On a fresh consumer without a project overlay, the shipped silent-success gate ran four enabled families and exited 0. The spec calls for a disabled-by-default skip notice. |
| 070 | `gate-root-01` | Python and Node fixtures traced root selection in standalone and submodule layouts, including a decoy parent tree. Coverage is limited to the exercised gates. |
| 071 | `gate-vacuous-01` | Empty discovery and a zero-test TAP run failed closed. An empty real Cargo target exited 0 under Cargo and 1 under the framework runner. Adding one test made the runner pass. Discovery losing an eligible file in the selected root remains unverified. |
| 072 | `gate-allwindow-01` | On the same clean commit after a tag, the critical prevention-rule match passed under `--all` and failed under `--base origin/main`. The registry arm did detect the same literal under `--all` once it was registered. |

## Test and control receipt

The [receipt](test-receipt.json) records 160 passing pytest cases from 11 modules.
A separate selection of 50 distinct named cases passed. These selections overlap.
The Node test runner reported 16 passing cases. The root and schema harnesses
reported 15 and seven passing assertions respectively. Nine synthetic controls
record the fixture, commands and observed results. An exit code of 0 in a
synthetic control can be counterevidence when the requirement calls for rejection.

Row 061 also records the GitHub App check and suite job for the reviewed
revision. The full pytest step completed on `ucs03-devgate`.
[App check](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/runs/140650485002) /
[matching job](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46038027437/job/140638326462).

## Verify the batch

Run the official validator from the repository root against the expected digest.

```sh
python3 scripts/evidence-validate.py \
  openspec/changes/dg-02-evidence-ledger-reconciliation/batches/batch-006/evidence \
  --expected sha256:83420bbfdc1c52bc76fdfae9e168b734d58f0329277465e6116d712c2ed95d1e
```

The [batch manifest](batch-manifest.json) records the raw SHA-256 values for
the disposition and receipt. Each of the 12 row findings binds the full row.
Remove its two link fields (`review_evidence_ref` and `review_evidence_digest`),
serialize with sorted JSON keys, ASCII escapes and separators `(',', ':')`, and
hash the bytes. The resulting SHA-256 appears in the finding's `observed` field.
The thirteenth finding binds the exact receipt bytes including the final newline.
