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
- **Duplicate gate engines** (the root-detection contract is now unified
  across the worst offenders; 3 overlay merges, 4 glob engines, 5 SKIP_DIRS
  remain) → `consolidate-shared-gate-logic`.
- **Golden vectors not load-bearing; untested modules (`hub/main.py`,
  `deploy.sh`, `silent-success-scan.sh`, `schema-health-check.mjs`)** →
  `harden-test-suite`.
- **arm64 profile + image publish** (coherence S4, environment-gated) —
  unchanged; needs registry credentials and an arm64 host.

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

## Closed by `harden-security-boundaries`

| Finding | Status | Evidence |
|---|---|---|
| F3 package inventory path traversal (host-file read/oracle) | **closed** | `_contained` rejects absolute/`~`/segments/symlink escape before any read; hostile-path tests assert no host content in errors |
| F4 assertion selector escape (exfiltration into sealed evidence) | **closed** | selector containment in `evaluators._extract`; traversal/absolute/symlink-escape are UNRESOLVED with stable reasons; positive control keeps legit selectors working |
| F11 manifest size/digest from two reads (inconsistent entries) | **closed** | `_digest_and_size`: one streaming pass produces both |
| F2 SIGTERM shutdown hang | **closed** | `server.timeout = 1.0` re-checks the stop Event; test drives the real hub process, SIGTERMs it idle, asserts exit 0 < 4.5s |
| F8 enroll TOCTOU | **closed** | duplicate-name check moved under the registry lock with token consumption; two-thread enroll test asserts one 200 and no double registration |
| F9 unbounded request body | **closed** | `HUB_MAX_BODY_BYTES` (default 1 MiB); 413 before read; invalid/negative Content-Length 400; normal bodies unaffected |
| Plaintext tokens at rest / token echoed to stdout | **closed** | salted-hash verifiers with legacy upgrade-on-load and verifier-clearing revoke; `response_summary` filters secrets; test asserts the token bytes never appear in the registry file or on stdout |
| F5 queue alerts keyed on nonexistent `run_id` | **closed** | `id` used; test asserts two stalled runs produce two distinct keys |
| F6 `watched_branches: ["default"]` silently 404'd gate-results | **closed** | sentinel resolves via `/repos/{repo}` with a loud per-cycle warning when unresolvable; both paths tested |
| F7 Retry-After read from JSON body | **closed** | captured from the HTTP header on 403/429, consumed by the next backoff |
| F10 monitor thread read registry unlocked | **closed** | `HubState.snapshot_runners()` under the lock; threading contract documented on HubState |
| F14 killed podman client could orphan the container | **closed** | `--cidfile` + best-effort `podman kill` + bounded reap on timeout/overflow paths |
| Template action/image pinning (incl. gitleaks + GITHUB_TOKEN) | **closed** | all `uses:` are 40-hex SHAs (SHAs resolved from the GitHub API, rotation documented); FROMs digest-pinned; `actions-runner` and `python:3.12-slim-bookworm` digests recorded with resolution dates; runner-monitor image gains a `/health` HEALTHCHECK |
| Quadlet secrets docs unparseable / three-way contradictory | **closed** | both quadlets declare `EnvironmentFile=` (raw env file, `-` optional); runner README, add-a-runner.md, and the hub runbook match it; supply-chain test rejects raw-env-in-`.container.d` instructions |
| runner-enroll JSON by string interpolation; token echoed; unbounded curl | **closed** | `json_payload` via `json.dumps` (hostile-label fixture), `response_summary` filters secrets, every curl time-bounded, identity fields validated before unit generation; sandboxed harness `tests/test_runner_enroll.sh` (15 checks) |
| detect-host-ci redaction false-positives; rglob crashes; `*.yaml` ignored | **closed** | lookaround-based redaction (RUNNER_TOKEN still caught, `blacksmith-2x` not), bounded walk with OSError skip, both extensions, `FROM --platform` parsing; `tests/test_detect_host_ci.py` |

## Closed by `migrate-specs-to-openspec-conventions`

| Finding | Status | Evidence |
|---|---|---|
| `openspec validate --strict` failed 15/15 main specs; CLI read requirements as 0 everywhere | **closed** | all 15 specs converted (Purpose + Requirements + `### Requirement:` + SHALL/MUST); `validate --all --strict` 26/26; `openspec list --specs` non-zero for every capability — both parsers agree |
| Game specs were foreign documents (no ids, gates that don't exist) | **closed** | rewritten per base-specs-01: game-regression (game-reg-01..03), per-screen-tracking (screen-inv-01..02) describe the real, tested scanner contracts; game-type-phase-matrix reduced to one requirement explicitly marked planned (game-matrix-01); game-framework-README rewritten (no submodule instruction) |
| Two ✓ Complete changes unarchived; delivered ids invisible to the CLI | **closed** | `openspec archive` for add-runner-to-fleet (fleet-add-01 now in main specs) and fix-size-gate-test-scope |
| ai01 missing proposal.md + broken archive pointer (×2) | **closed** | proposal.md derived from plan.md; both pointers now name `archive/2026-09-13-runner-monitor` |
| mon-local-01 lost in archive→main migration | **closed** | restored verbatim into hub-architecture |
| Rules/schema file contradictions (extracted-rules.json shipped vs rule-coverage-truth; missing semantic-rules.schema.json; dangling AGENT_GUARDRAILS.md refs) | **closed** | extracted-rules.json deleted (was schema-violating, loaded by nothing); semantic-rules $schema pointer removed; skills now point at AGENTS.md |
| Spec-format drift could recur silently | **closed** | CI specs job now hard-fails on `openspec validate --all --strict` (@fission-ai/openspec pinned install) + traceability counts; spec-fmt-01..03 published into main specs |

## Closed by `docs-and-data-truth-pass`

| Finding | Status | Evidence |
|---|---|---|
| H3 1,726-entry foreign allowlist in the shared baseline | **closed** | purged (12,093 → ~740 bytes); the baseline ships empty by design and the scan says so; consuming repos own their overlay entries |
| M3 silent-success-rules preamble lied (two families shipped enabled) | **closed** | all families ship `enabled: false`; the scan prints an explicit no-families skip |
| README described half the repo; coherence service undiscoverable | **closed** | tree reflects the full repo; new Runner Monitor Hub and Spec Coherence Service sections |
| SEMANTIC-005 advertised, unimplemented (H1's user-facing half) | **closed** | README + scanner header de-advertise; the rules file is documented as advisory catalog, not scanner coverage (full H1 rule-count reconciliation remains for the rules-data owner) |
| Schema-health config required editing the submodule (M2 half) | **closed** | `<project>/.guardrails/schema-health.json` overlay config implemented (adapter + expected_columns); half-configured and malformed configs fail loud, never skip green; `DEVGATE_PROJECT_ROOT` parity; `tests/test_schema_health_config.mjs` (6 checks) |
| AGENTS.md instructed consumers to violate the overlay contract (M10) | **closed** | custom-rules section points at the project overlay; database section points at the config file; rule counts corrected 29 → 32 |
| templates/README omitted runner-monitor + add-a-runner; phantom `check_file_sizes.sh` ref | **closed** | tree completed; SETUP header now describes the self-contained workflow and the real regression gate |
| Dangling `docs/AGENT_GUARDRAILS.md` in all six skills; dangling `semantic-rules.schema.json` pointer | **closed** | skills point at AGENTS.md; `$schema` pointer removed (schema doesn't ship); NOTE: these were briefly false-checked-off in the migration change and are now genuinely fixed — the delta table is the source of truth |
| .gitignore dead tilde pattern + duplicate entries | **closed** | deduped |
| pre-work-check rule table listed 14 of 32 rules | **closed** | regenerated from `pattern-rules.json` (32 rows, derived not hand-copied) |
| CHANGELOG missing the coherence service; duplicate section headings | **closed** | coherence-service entry added; Unreleased normalized to one Added/Changed/Fixed each |

Semantics note (H1 remainder): the SEMANTIC-005 de-advertisement and rules-
file-as-catalog clarification close the user-facing half of H1; reconciling
the 9 unimplemented semantic RULES themselves (implement or re-home) is a
rules-data decision tracked for the rules owner, not silently dropped.

## Closed by `harden-test-suite`

| Finding | Status | Evidence |
|---|---|---|
| F13 golden vectors dead + generated by a parallel implementation | **closed** | `compute_golden.py` now imports the real `hub.coherence.canon` (regeneration exercises the real path — verified byte-identical output); `test_hub_coherence_golden.py` asserts canon's output against every frozen vector and the profile-rejection contract (floats, >int64, unknown role tags) |
| Collection can silently shrink (fw-ci-01 meta-guard) | **closed** | `TestSuiteFloor` asserts a committed floor of discovered `tests/test_*.py` files; a drop fails with instructions to bump deliberately |
| chmod-based exit-33 tests invert under root | **closed** | `skipIf(euid==0)` guards with the reason in the skip message |
| Test fixtures written inside the repo tree | **closed** | `test_regression_check.py`'s `_tmp_registry.jsonl` and `_tmp_sizes/` moved to temp dirs; no in-tree writes remain |
