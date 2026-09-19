# Audit delta — 2026-09-19 fixes landed on the `audit` branch

Scope: closure record for fixes landed from `docs/ROADMAP-2026-09.md` Phase 0,
against the findings inventories in `docs/qa/2026-09-13-full-qa.md`,
`docs/qa/external-audit-2026-09-14.md`, and the 2026-09-19 review (F-series).
Directive for every item below: reproduced first, fixed, then locked by a test
that fails on the old behavior (no config-only or doc-only "fixes").

## Closed by `fix-coherence-container-contract`

| Finding | Status | Evidence |
|---|---|---|
| F1 pinned image could not load frozen schemas; only real-container test asserted the same exit a broken service produces | **closed** | schemas moved to `hub/coherence/schemas/`; package-relative resolution (host == container); in-image schema-load test; valid-request PASS smoke case; rejection reason asserted to name the invalid input; `TestSchemaHome` guards against path regression |
| Runtime dependent on an active change-package path (S8 archive would break the CLI) | **closed** | same move; pointer note `SCHEMAS-MOVED.md`; S4 regression entry in the coherence package |

## Closed by `fix-vacuous-and-broken-gates`

| Finding | Status | Evidence |
|---|---|---|
| C1 `scene_inventory.py` failed every valid `.tscn` (ET.parse dead-end); nested connections false-orphaned; empty scope read as pass | **closed** | regex parser primary; last-segment path matching; NOTHING SCANNED + `--fail-if-empty`; `tests/test_scene_inventory.py` (8 tests) |
| C2 `semantic-scan.mjs` escaped to the parent on a standalone clone (EACCES crash / stranger trees) | **closed** | layout-contract anchoring; walk() error/symlink guards; `tests/test_scanner_root_anchor.mjs` |
| C3 `run-tests.mjs` green with zero tests on a standalone clone; four-dir discovery vs documented "anywhere" | **closed** | same anchoring; full-tree discovery; 22 → 23 files discovered in this repo (the scanner suite was invisible before) |
| C4 Rust arm ran zero tests via positional filter | **closed** | `cargo test --test <stem>`; a non-target file now fails loud |
| C5-adjacent markers / never-run `test_guardrails_scan.mjs` | **closed** | prefix-form `test_*.mjs` discovery; the suite now executes under the runner |
| C6 npm audit misclassified direct runtime HIGH/CRITICAL as dev-only | **closed** | `isDirect` + name + effects classification; failure-to-run surfaces as warnings; `tests/test_regression_audit.py` (8 tests) |
| C7 deploy gated the submodule / could not run standalone | **closed** | script-location anchoring in `regression_check.py`, `failure_registry_check.py`, `deploy.sh`, `scene_inventory.py`, `log_failure.py`; `DEVGATE_PROJECT_ROOT` override |
| H6 `//`-only marker grammar locked Python out of blocking mode | **closed** | `#` prefix accepted and mirrored in `evaluators.MARKER_RE`; per-language scaffolder advice; 3 new traceability tests |
| H7 twine double-upload/abort-after-publish precedent bug | **closed** | explicit if/then, version-scoped artifacts, visible stderr |
| H8 `log_failure.py` wrote to the shared baseline by default | **closed** | project-overlay default, `--baseline`/`--registry` for the bundled registry; `tests/test_log_failure.py` |
| New: `failure_registry_check.py` vacuous green on a typo'd explicit path | **closed** | explicit missing path is exit 1 for every label; `tests/test_failure_registry_check.py` |
| New: `tests/__init__.py` missing — five conformance files silently dropped from collection when a foreign `tests` package is installed | **closed** | regular package + `conftest.py`; reproduced live before/after |
| deploy.sh schema gate demoted to WARN while documented as a gate; untracked files invisible to the clean-tree check | **closed** | schema blocks (skips green only when unconfigured); untracked check added |

## Still open (tracked, not silently dropped)

- **SEMANTIC-005 / 9 dead semantic rules** (H1) → `docs-and-data-truth-pass`.
- **1,726-entry contaminated allowlist** (H3) → `docs-and-data-truth-pass`.
- **drift-scan template shallow checkout + missing typescript** (H2) →
  `consolidate-shared-gate-logic` / template pass.
- **silent-success overlay + enabled families** (M2/M3) →
  `docs-and-data-truth-pass` (data) + `consolidate-shared-gate-logic` (overlay).
- **`openspec validate` 15/15 main-spec failures** →
  `migrate-specs-to-openspec-conventions`.
- **Hub runtime hardening (F2-F11, F14)** → `harden-security-boundaries`
  (in progress on this branch).
- **Framework CI** → `add-framework-ci-pipeline` (in progress on this branch).

## Method notes

- Every closure above was re-verified against HEAD before fixing; the
  reproduction is either in a committed test or in the finding's evidence
  column above.
- Registry entries FAIL-2026091901..08 record the incident classes with
  prevention patterns; `failure_registry_check.py` exits 0 on the tree.
- Framework self-scan is warning-clean (the two PREVENT-024 hits on local
  module imports got audited same-line `guardrails-allow` annotations — and
  surfaced a doc bug: AGENTS.md's preceding-line annotation example does not
  match the scanner's same-line contract; tracked for the consolidation
  package).

## Closed by `add-framework-ci-pipeline`

| Finding | Status | Evidence |
|---|---|---|
| M9 the framework's own PRs run no checks (no CI executed tests/) | **closed** | `.github/workflows/ci.yml`: `tests` (pytest + node fixture suites + the framework's own per-file runner), `self-gates` (guardrails/semantic/regression-with-range/ silent-success/registry), `specs` (traceability counts; openspec validate informational until the migration lands), `container-image` (builds the pinned image and proves schemas resolve inside it — the F1 regression, fw-ci/coh-rt-08) |
| Unpinned actions in the framework's own workflows | **closed** | all uses SHA-pinned (checkout / setup-python / setup-node resolved via the GitHub API and recorded with version comments); `drift-scan.yml` setup-node pinned |
| Semantic scan in CI had no parser installed (would fail closed on TS consumers) | **closed** | self-gates installs `typescript@5` before the scan |
| F12-adjacent: collection could silently shrink | **closed** | `tests/__init__.py` + `conftest.py` land in the container-contract commit; the `tests` job fails on any collection error |
