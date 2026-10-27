# Changelog

All notable changes to the DevGate Agentic Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

> **Version-truth statement (doc-truth closure, 2026-10-13):** `VERSION` reads
> `1.3.0` and this Unreleased section carries post-1.3.0 work; the newest git tag
> remains `v1.2.0`. No release has been cut since 1.3.0's changelog entry
> (2026-09-23) — the version artifact and the tag intentionally disagree until the
> next tagged release, at which point Unreleased is folded into the new tag. This
> statement is the recorded intent for doc-truth (`doc-version-01`); no retroactive
> tag was cut.

### Fixed

- **A runtime-capability check skips loudly instead of measuring the runtime.**
  `test_schema_health_config.mjs`'s cold-install path needs `node:sqlite`
  (Node 22.5+); the fleet's minimum runtime is Node 20 (ci.yml), where the
  gate correctly fails loud ("adapter not usable", exit 1) for an engine that
  cannot load — so check 4b asserted a skip the gate rightly refuses to give
  and the suite went red on the fleet (run 40564317112: 2310 passed, 1 failed,
  this file). The check now probes `node:sqlite` at load and skips LOUDLY when
  the runtime cannot provide it — the same honesty guard
  `tests/test_schema_health_exitcodes.py` already uses (`SQLITE_OK`) — and is
  never reported as passed on a runtime that never ran it.
- **Layout-asserting tests build the layout they claim to verify.** The four
  standalone-layout checks (log_failure default registry, detect-host-ci CLI
  ×2, schema-health unconfigured skip) ran the LIVE scripts against the live
  checkout and asserted clone-layout behavior — green only when the framework
  is checked out standalone (CI), red whenever it is vendored as
  `<host>/.devgate`, which is exactly the layout every consumer runs. Each
  now copies the script into a real clone-layout tree (`<tmp>/gameproj/scripts/`,
  a root NOT named `.devgate`) and asserts there; the schema-health case also
  pins the unconfigured skip's message on stdout, because the vendored run
  took a different skip path (host's configured DB absent — message on stderr)
  than the unconfigured one its name promises. Full pytest suite now green in
  both layouts (1890 passed, 0 failed).
- **A spawned test engine always runs top-level — the runner scrubs
  `NODE_TEST_CONTEXT` from its children's env.** Measured 2026-10-27 on
  v26.11.1: when run-tests.mjs itself executes under `node --test` (its own
  fixture suite is run that way), the outer runner marks the test file with
  `NODE_TEST_CONTEXT`, the fixture spawns run-tests.mjs with that marker still
  in its env, and every nested `node --test` treats its invocation as
  recursive — "run() is being called recursively within a test file. skipping
  running files." — evaluates ZERO tests, prints no TAP and exits 0. The
  root-anchor green-exit checks died on it (2 of 15 red only under
  `node --test`, green direct). `childTestEnv()` (lib/test-runner-select.mjs)
  deletes the marker before spawning any engine (node, vitest, pytest, cargo);
  pinned by `test_run_tests_runner.mjs` ("children run top-level even when the
  runner sits under node --test").
- **A run that executed ZERO tests fails closed instead of passing.**
  `node --test` on a file with no tests and vitest with a non-matching filter
  both print a `1..0` plan and exit 0 — under a naive verdict that reads as
  ✓ 0 pass / 0 fail, the gate-vacuous-01 shape. `isEmptyRun()` (lib/
  test-runner-select.mjs) names the state (skips count as evidence; todo-only
  fails closed), and run-tests.mjs refuses it in the verdict ("(ran zero tests
  — vacuous, not a pass)") and in solo flake adjudication alike.
- **A consumer whose package.json declares vitest runs its suffix-style JS/TS
  on vitest, not `node --test`.** Measured 2026-10-27 on the vbrainstorm
  consumer: every vitest file crashed before a single test ran with
  `ERR_MODULE_NOT_FOUND` on its extensionless TS imports ("Cannot find module
  '.../src/community/media'") — `node --test` loads the file but does not do
  TypeScript module resolution. The TS discovery arm existed but could not run
  the dominant TS layout (Decision 8: fix the written-but-broken arm, don't
  delete it). `selectJsRunner()` delegates suffix-style files to the local
  vitest binary (`run --reporter=tap --root <projectRoot> <relative-filter>`;
  the filter MUST be relative — an absolute path matches nothing and hits the
  1..0 trap), keeps prefix-style `test_*.mjs` on `node --test` (vitest's
  default include does not collect it), and keeps every file on `node --test`
  when vitest is not declared. Real consumer: 17/17 vitest files green.
- **`get_changed_files` counts metadata-only and deletion-only diffs as real
  scope.** Measured 2026-10-27 on the fleet (AIGGP run 40562221604, the
  exec-bit fix `88c3223`): the CI regression check printed "NOTHING SCANNED —
  the selected scope contains 0 changed files" and `--fail-if-empty` exited 2
  on a push that changed a real file's mode. The scope reader parsed only
  `+++ ` diff headers, but git emits NO `---`/`+++` pair at all for a pure
  mode change (`old mode`/`new mode` only), and a pure deletion's only `+++`
  target is `/dev/null` — so both read as empty scope. `get_changed_files`
  now also takes the b-side path from each `diff --git a/<old> b/<new>`
  header (post-image name, same rename semantics, deduped against the `+++`
  parse), so a path the diff NAMES is in scope. The vacuous-empty failure for
  genuinely empty ranges is untouched. `tests/test_regression_scope.py`
  grows 5 → 12 checks: FakeGit cases for mode-only / pure deletion / content
  / rename / mixed blobs, plus a real-git exec-bit + `git rm` round trip —
  the exact fleet shape.
- **`_collect_git_scope` fails loud instead of silently emptying the
  staged/unstaged scope.** The staged and unstaged arms did `if rc == 0:
  append` while the docstring promised fail-loud (gate-vacuous-01): a lock
  contended or corrupt index (rc 128) dropped the blob and the run scanned
  ZERO files with a green report — the same vacuous-empty shape as the
  mode-only parse bug above. rc 0/1 are data (matching `_diff_or_raise`);
  anything else now raises. Pinned by
  `TestGetChangedFilesScope::test_unreadable_staged_scope_raises_not_swallows`.
- **Corruption-gate diff headers resolve to the real path on both sides.**
  The header parser sliced `line[6:]` — stripping `--- ` plus two more
  characters — which works by accident for git's `a/`/`b/` prefixed paths but
  turned a pure deletion's `+++ /dev/null` into `ev/null`: a deleted file's
  removed lines were attributed to a nonsense path in per-file accounting
  (mass-rewrite counting, allowlist lookup, report lines). The slice is the
  4-char header marker and the optional prefix is stripped separately;
  `tests/test_check_corruption.py` grows
  `CorruptionDiffPathResolution` (3 checks: deletion path, new-file path,
  deletion scan stays clean).
- **The 500-line hard cap's own violators are split, not squeezed.**
  `check_corruption.py` stood at 518 (a touched hard oversize blocks) and
  `regression_diff.py` at 496 (4 lines of headroom). The hunk-level diff
  parser moves to `scripts/corruption_diff.py` (check_corruption 518 → 398)
  and the prevention-pattern contract to `scripts/regression_patterns.py`
  (regression_diff 496 → 410); both originals re-export the moved helpers so
  every importer and the importlib-based tests keep one module. Pinned by
  `tests/test_python_root_anchor.py` `_PY_DEPS` (the synthetic repo must
  carry the full sibling-import chain).
- **`check_diff_against_patterns` honors the shared scanner contract
  (comment lines + test-code scope).** Measured 2026-10-27 on the vbrainstorm
  community-acceptance tree: the prevention-pattern checker treated full-line
  comments as code — doc prose reading "D5): any non-banned member …" and
  "model by Space type\"): any visitor may enroll" matched PREVENT-011 /
  PREVENT-VB-001's `:\\s*any` as if it were a TypeScript `any` type — and it
  applied blocking rules to test code, so synthetic in-process route fixtures
  (``new Request(`http://localhost${path}`)``, Request `origin:
  "http://localhost"` options) hard-failed CI's `--pre-commit` mode with
  PREVENT-029 CRITICAL on `*.test.ts` files that `guardrails-scan.mjs`
  correctly exempted. The same diff passed one scanner and failed the other —
  FAIL-9231181d's "identical semantics intended for every scanner" contract
  broken two ways. `check_diff_against_patterns` now skips full-comment lines
  unless the rule opts in via `scan_comments` (exactly guardrails's comment
  contract; trailing inline comments still scan their code portion), and skips
  blocking rules (severity != "warning") on test files — warning-severity rules
  stay advisory everywhere, matching guardrails. `tests/test_diff_pattern_allow.py`
  grows 5 → 7 checks pinning both exclusions and their controls (code-line hits
  still fire, `scan_comments: true` still opts a marker rule back in, production
  paths still block).

- **Whole-file rewrites no longer feed flip pairing in `check_corruption`.**
  Measured 2026-10-27: vbrainstorm's `invites.ts` stability-barrel rewrite
  (9.13) reported `substitution flip (78% of characters changed, length within
  3%)` by pairing the old file's first comment ("This replaces the Phase-1
  FIXTURE_INVITES map; the InviteView response") with the barrel's first
  comment ("Every public name this module historically exported is re-exported
  here,") — SequenceMatcher alignment across a whole-file rewrite invents
  comment-to-comment pairs that share no content. The detector's own coverage
  model already judges rewrites via the mass-rewrite rule (≥8 add AND ≥8 rem
  per file; ≥10 files = BULK MUTATION), which reported the same rewrite as an
  intentional mass rewrite. Files that cross the mass-rewrite threshold are
  now excluded from flip pairing and judged by that rule alone;
  1↔1 edits of the same comment pair still fail flip (control test), and
  `tests/test_check_corruption.py` pins both legs.

- **`*-test-helpers.ts` / `*-test-utils.ts` are test code in both scanners.**
  Shared fixture modules (vbrainstorm's `space-test-helpers.ts`,
  `invite-test-helpers.ts`) hold harness-only code — synthetic Request
  builders, in-memory DB shims — but neither scanner's test-file classifier
  recognized the naming, so `guardrails-scan.mjs` fired PREVENT-029 CRITICAL on
  a fixture module's synthetic `new Request(\`http://localhost…\`)` while the
  identical line in a `*.test.ts` file was exempt. `isTestFile` (Node) and
  `_is_test_file` (Python) now match `(^|[.-])test[-_]?(helpers|utils)\.(ts|tsx|js|jsx|mjs|cjs)$`,
  keeping blocking-rule exemptions consistent for the fixture-module
  convention. `test_guardrails_scan.mjs` case 19 pins fixture/test silent +
  production blocking for the same line.

- **Pattern-rule `exclude_glob` honored by both scanners.** The Python
  `regression_check.py rules_for_file` applied a rule's `file_glob` but never
  its `exclude_glob`, and `guardrails-scan.mjs ruleAppliesTo` only read
  `exclude_glob` when `file_glob` was also set. So a boundary-file exemption
  could silence one scanner and not the other: vbrainstorm's PREVENT-029
  overlay exempts `src/lib/**` (documented boundary layer — JSON-LD URL
  literals in `postSeo.ts` are data, not network calls), which
  guardrails-scan honored and regression_check flagged CRITICAL on
  2026-10-27. Both now honor `exclude_glob` for every rule shape via the
  shared `glob_matches` contract; `tests/test_rule_scoping.py` (new) locks
  the Python side and `test_guardrails_scan.mjs` case 12b the Node side.

- **stitcher-codereview lint surface clean (5 errors removed).** Four
  `no-useless-escape` hits (`checks/drift.ts:62`, `checks/tests.ts:48,60`,
  `spec/parser.ts:95`) were `\-` inside character classes where a literal
  trailing `-` is the same set — verified equivalent over a 22-char alphabet
  plus split/replace samples. `templates/types.ts:98` typed its `file`
  parameter as `any` behind a PREVENT-011 allow comment; it is a parsed diff
  record, so it now takes the module's own `DiffFile` and the allow comment is
  gone. `npm run build` (tsc) EXIT 0 after the change; the package's `npm test`
  (vitest) finds no shipped test files — behavior evidence is the regex
  equivalence check and the clean build, not a suite run.

- **SEMANTIC-005 no longer demands dependencies the React lint forbids.**
  Measured on vbrainstorm (2026-10-27, community-acceptance-fixes warning
  sweep): the rule required module-scope bindings (ES imports, top-level
  declarations) and host builtins (`encodeURIComponent`) in every `useEffect`
  dependency array — the exact names `react-hooks/exhaustive-deps` rejects as
  "unnecessary dependencies … Outer scope values like 'X' aren't valid
  dependencies because mutating them doesn't re-render". Listing one silenced
  SEMANTIC-005 but fired the React lint; omitting it did the reverse, so no
  array could win on both gates — the contradiction the rule's own header
  already disclaims ("module plumbing" is exempt). Three exemptions close it:
  `moduleScopeNames(sourceFile)` treats every module-scope binding as the
  module plumbing it is (name-based, no scope walk — a rare component-local
  shadowing false negative is the accepted trade, matching the header
  philosophy); `EFFECT_GLOBALS` now spells the frozen ECMA-262 /
  web-platform builtins (`encodeURI*`, `decodeURI*`, `atob`/`btoa`, `URL`,
  `URLSearchParams`, `TextEncoder`/`TextDecoder`, `AbortController`/
  `AbortSignal`, `structuredClone`, `queueMicrotask`, `performance`, `crypto`,
  observer constructors `MutationObserver`/`IntersectionObserver`/
  `ResizeObserver`, and the media constructors `Audio`/`MediaMetadata` —
  `new Audio()` in AudioContext.tsx on vbrainstorm 2026-10-27 tripped the same
  class); and free-identifier gathering now skips type-position identifiers
  (`e: MessageEvent`, `querySelector<HTMLIFrameElement>`) — erased at compile
  time, so a callback never reads them, and demanding one produced another
  dependency the React lint forbids.
  Component-scope values the callback reads stay required. The independent
  audit's differential matrix (16 cases, pre/post-fix scanners, 2026-10-27)
  then caught four residues where that last claim leaked, all now closed:
  binding patterns collected property keys and default-initializer names as
  bindings (`{ apiBase: API_BASE }` exempted a local `apiBase`; `{ a = helper() }`
  exempted a local `helper`) — `bindingIdentifiers` now walks binding TARGETS
  only; `declare global` registered its marker name `global` as a module
  binding (exempting a local `global`) — ambient `global` is declaration
  merging, not a binding; and `class X extends Base` / `extends makeBase()`
  were treated as type positions because `ExpressionWithTypeArguments` is a
  TypeNode — heritage EXPRESSIONS evaluate at runtime and are reads again,
  while their `<T>` arguments stay exempt. Fixture coverage:
  module-scope exempt, component-scope omitted local still flagged, the
  ChatPane-shaped session effect green on the eslint-legal array, the
  VerifyEmail-shaped host-builtin effect green (including the
  Audio/MediaMetadata media constructors), type-position identifiers green,
  binding-target/declare-global/heritage residues green, and the
  no-dependency-array branch unchanged. `test_semantic_scan.mjs`
  grew 11 → 25 checks.
- **`--pre-commit` no longer green-lights an empty scope (gate-vacuous-01).**
  `--staged --pre-commit` run before `git add` scanned zero files, printed a
  NOTHING SCANNED banner followed by a green `0 over hard limit (blocks
  commit)` summary, labeled every oversize file "pre-existing; not touched by
  this diff", and exited 0 — exactly the run that let 500+-line files land in
  vbrainstorm while the gate read clean. `--pre-commit` now implies
  `--fail-if-empty` (empty scope → exit 2, vacuous wins over other counts),
  the verdict logic is one shared primitive (`gate_common.exit_code_for`),
  and on an empty scope the file-size report is explicitly inventory-only:
  no "(blocks commit)" claim and no touched/untouched classification against
  a diff that does not exist. Without the fail-loud flags a vacuous run stays
  a notice (exit 0), preserving the force-push-with-no-changes case.
- **PREVENT-026/029 no longer fire on standard Cloudflare Workers shapes.**
  Measured on vbrainstorm (community-subsite 3.1, which adds a Durable Object
  WebSocket endpoint): 4 false positives, 0 true positives. `fetch(request:
  Request)` type signatures are skipped by the `(?!\s*:)` lookahead; binding
  proxies — `env.ASSETS.fetch(request)` and DO namespace forwards carrying
  `idFromName` — join `forbidden_context`; and `new WebSocketPair()` (the
  socket-accept primitive, not a network call) no longer matches `new
  WebSocket`. Genuine SSRF shapes (`fetch(userUrl)`, `fetch(request.url)`) and
  real `new WebSocket(` clients still fire. Per-repo transport-boundary files
  (a DO `fetch` entrypoint) remain the job of each repo's `.guardrails`
  `exclude_glob`, the mechanism the rule's own suggestion prescribes.
- **`game_regression.py` reported the checks as the bugs (60 → 0 on
  MergeKingdom).** Its Godot table matched single lines, so it could not see a
  guard written on the next one: `preload("…tscn")` on a constant counted as an
  unchecked scene load, `var file := FileAccess.open(...)` followed by
  `if file == null:` counted as save corruption, and `SCRIPT_ERROR` matched
  `push_error(` / `assert(` — the recommended handling and a deliberate guard.
  Measured on MergeKingdom (`--all --pre-commit`): 60 issues, 0 real — 3 preload
  constants, 13 checked opens (7 `== null`, 6 Godot truthiness `if file:`), 43
  `push_error(...)` call sites. A rule may now be `(regex, guard, window)` and
  stays silent when one of the next `window` lines matches `guard`; whole-line
  comments are never scanned (the gate was reporting its own docstrings); and
  `SCRIPT_ERROR` is retired with the measurement recorded. After the change the
  same run reported one genuine hit — an unchecked `FileAccess.open` in
  `ad_manager.gd`, now fixed in MergeKingdom — and then 0. `test_game_regression`
  grew from 13 to 20 tests, one per false-positive shape plus a bounded-window
  negative control.
- **`scene_inventory.py` now sees code-side button wiring (`screen-inv-01`).**
  The Godot scanner read `.tscn` connection blocks only, so a UI wired the way
  Godot's editor and docs produce — `btn.pressed.connect(...)` in `_ready()`,
  or an `@onready var btn = $Panel/Btn` followed by that call — reported every
  button as orphaned. Measured on MergeKingdom: 4 scenes / 8 correctly wired
  buttons failed the gate, and the same run's orphans also hid five real
  defects (three popups whose `@onready` paths named nodes their scenes do not
  contain, aborting `_ready()` before the UI was built). The gate resolves the
  root node's Script ext_resource and counts the connections that script makes;
  a script wiring a different node leaves the orphan, and a commented-out
  `connect()` is not a handler (both negative controls pinned). 8 → 15 tests;
  `tests/test_scene_inventory.py` and the spec's scenario set now state the
  code-wiring contract.
- **`base-own-01`'s other two named file classes were measured, not assumed.**
  The requirement names prevention rules and openspec specs as well as the
  registry and allowlist. The rule files carry no repository paths, but four of
  their `note` fields asserted another project's state as current:
  `go_return_nil_after_ignored_error` and `python_pass_todo_body` claimed
  "existing occurrences allowlisted in silent-success-allowlist.json" (false —
  the bundled file is empty by contract, and the 1,725 entries removed on
  2026-10-25 were all the *Go* family, so the Python claim never held), and both
  Zig families ended "Ships disabled like every family here" (false — 4 of 11
  families ship enabled, and this tree contains no `.zig` file). All four notes
  now state their family's shipped state and point a consumer at its own
  overlay; zero provenance tags remain in the bundled rule files. Openspec
  specs were checked the same way: every foreign-repository mention outside the
  archive is provenance, which `base-specs-01` permits, and no bundled spec
  claims a path of this repository that does not exist.
  `scripts/baseline_ownership_check.py` also gained a third clause: an entry
  whose family is **declared but disabled** is a finding, because a disabled
  family never evaluates a file and such an entry suppresses nothing while
  counting as coverage. `tests/test_baseline_ownership_check.py` 14 → 16.
- **The bundled silent-success allowlist had 1,727 foreign entries again, and
  nothing noticed.** `beedec1` (2026-09-19, QA H3) emptied
  `.guardrails/silent-success-allowlist.json` and wrote the "empty by design"
  note; `16ce30e` (2026-09-20) wrote a pre-decontamination copy back over it
  while retiring two `internal/admin/bootstrap.go` markers — removing 2 entries
  from 1,727 and restoring the other 1,725 — and `b3f951b`, `eeb2884` and
  `239e30b` edited that restored copy afterwards (`239e30b` recorded it as
  "verified intact (1727 entries)"). Every one of the 1,727 names a path absent
  from this tree (`internal/` 1454, `tests/` 225, `go/` 40, `cmd/` 8):
  `baseline-ownership` / `base-own-01` states that a bundled baseline entry may
  reference only this repository's paths. The file is empty again, and two
  gates now keep it that way: the new `scripts/baseline_ownership_check.py`
  fails on any bundled allowlist entry whose `file` does not exist or whose
  `family` the bundled rules do not declare (run in CI's gates job), and
  `scripts/silent-success-scan.sh` merges a `<project>/.guardrails/
  silent-success-allowlist.json` overlay into the baseline so a consumer's
  entries have a correct home — the contract the note had already described but
  the scanner did not implement.
- **Size-gate directory scope covered `web`/`infra`.** The walk roots were a
  hardcoded candidate list that omitted `web` and `infra`, so
  `web/render3d.js` (1470) and `web/index.html` (685) sat past SRC_HARD while
  the FILE-SIZE CHECK reported clean — the FAIL-f6228dda / FAIL-8f9249ca shape,
  one directory short. `gate_common.load_source_dirs()` now builds the list
  (candidates including `web`/`infra`/frontend roots, minus submodules), with
  scope.json `source_dirs` (replace) and `extra_source_dirs` (extend) so a
  consumer grows scope without forking. `check_scope_coverage` additionally
  warns on any top-level dir holding source files that the walk does not
  enter — the class fix, not just the instance.

### Added

- **bundle-size-check: the build-output budget gate.**
  `scripts/bundle-size-check.mjs` measures built assets against a per-file
  budget from the consumer's `.guardrails/bundle-size.json` overlay (never by
  editing the submodule) - the build-output counterpart of the source line
  limits in `regression_sizes.py`. `max_kb` is KiB (bytes/1024), the same
  unit vite uses for `chunkSizeWarningLimit`, so the warning becomes fatal
  without changing its number. Exit contract matches `schema-health-check`:
  `0` ran and passed, `1` failed / config unusable / configured but missing
  or empty input, `2` loud skip when unconfigured - and a configured run with
  nothing measurable FAILS rather than passing vacuously. `tests/test_bundle_size_check.mjs`
  locks the contract (skip vs pass, fail-closed empty input, bytes/1024
  comparison, invalid config). Reusable CI template:
  `templates/github-workflows/bundle-size-check.yml` (self-contained,
  BUILD_CMD / DIST_DIR / MAX_KB placeholders, file-size-check idiom).
- **gameSessionStart, step 1: the session brain.** `scripts/game_session_start.py`
  validates one `aiggp.session/v1` manifest (schema:
  `.guardrails/prevention-rules/session-manifest.schema.json`), applies the one
  hard rule (a `play` session under `determinism.enabled: true` must carry a
  seed; absent means off, and `determinism.enabled` is now documented in
  `scripts/game-framework-README.md`), prints a kind-filtered advisory block,
  and appends accepted sessions to `.guardrails/sessions.jsonl`. The work-side
  block carries `worst-tracked gaps: N` read from the gap scanner's own JSON
  report - the brain never rescans, and a missing or foreign report reads
  `unknown`, never `0`. Exit codes are `0` accepted / `2` refused a known
  session / `1` cannot say, the inverse of the secret-scan family; the contrast
  is stated in the spec (session-06), not unified. Adapters and the Godot hook
  are later rollout steps and are stated as out of scope. Spec:
  `openspec/changes/add-game-session-start/`. Tests:
  `tests/test_game_session_start.py` (37).

- **Reasoned size overrides.** scope.json `size_overrides`
  (`{"web/render3d.js": {"hard": 1600, "reason": "..."}}`) raises one file's
  limit. `reason` is required and non-empty (same contract as
  `guardrails-allow`); a breach under an override still reports
  `kind='overridden'` with the reason so the exception stays visible. Over the
  raised limit remains a blocking error.

- **Silent-success scan: two Zig families.** The baseline globbed `*.go`, `*.py`,
  `hub/**/*` and `scripts/**/*`, so a Zig consumer was scanned by none of its
  enabled families — its source tree was never read while the gate reported OK.
  `zig_swallowed_error_continue` catches `else |_| {}` (an error discarded and
  the flow continuing as if the work happened) and `zig_ignored_error_catch`
  catches `catch {};`. Both target the shapes a Zig project kept producing by
  hand: a swallowed file load, and a `pipe.resize(...) catch {}` that leaves a
  viewport wrong with no diagnostic. Test files are excluded at the family
  level. Validated against dead-air (2026-09-27): 15 pre-existing markers
  allowlisted there with reasons, 4 excluded, and a planted `else |_| {}` is
  reported as `[NEW/unlisted]` and fails the scan.


### Fixed (pre-existing)

- **Mutation harness:** the hermetic env scrubbed `HOME` (git identity
  isolation), which relocates Python's user base — on a `pip --user` host the
  nested `python -m pytest` died with `No module named pytest` (exit 1) and
  `run_entry` read that as a failing test, so **every mutant reported
  "killed"** (4 verdict tests red; CI passed only because hosted pip installs
  system-wide). `PYTHONUSERBASE` now survives the scrub, and a nested run
  that cannot start raises `HarnessFailure` — reported as `HARNESS FAILURE`,
  never as a verdict.
- **Hub:** `/enroll` duplicate-name check moved inside the locked section
  (the pre-check outside it let two concurrent enrolls with different valid
  tokens both append — TOCTOU); request bodies capped at 64 KiB with a 413
  before any read (unauthenticated `Content-Length` was an allocation lever);
  the monitor now reads a locked deep copy of the registry instead of racing
  in-place heartbeat writes; queue-stall alerts key on the runs API's real
  `id` field (was `run_id`, so every stall deduped to one `"?"` issue);
  `Retry-After` parsing can no longer raise out of the poll loop; `repo`
  validation tightened to `[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z` in server and
  schema; a failed recurrence comment drops the issue dedupe entry instead of
  burning the cooldown.
- **`runner-enroll.sh`:** revoke payload built with `json.dumps` like enroll
  (string interpolation let a runner name smuggle JSON fields); `--interval`
  validated as whole seconds before it reaches unit heredocs/arithmetic; the
  installation window maps raw failures to the documented exit code 3 (`ERR`
  trap under `set -E`) instead of leaking child codes as usage errors.
- **`guardrails-scan.mjs`:** the test-scope inversion branch was an empty
  `if` — production lines were silenced by their own forbidden-context words
  (`password = "sample_key"` vs PREVENT-003). Suppression now applies only
  when the file is a test file or the line carries the test vocabulary
  itself; fixture 4b pins it.
- **`regression_check.py --base`:** the flag advertised scanning committed
  content but never fed the base-diff files into the known-bug and
  pattern checks — on a clean pushed tree they evaluated nothing while the
  gate printed a clean pass. `get_changed_files`/`get_diff_content` now take
  `base` (11 files scanned where 0 before, proven against `HEAD~5`).
- **`silent-success-scan.sh`:** project root by layout rule like every other
  gate (the nearest-`.git` walk could select an outer repo and scan
  siblings).
- **`secret-scan-fleet.sh`:** declared URLs starting with `-` are rejected
  before `git clone` (option injection through the declaration file).
- **CI:** the specs job's `| tail` pipelines run under `set -o pipefail` —
  a traceability regression used to be masked by tail's exit 0; the
  framework's own template had the fix, its CI did not.

### Changed

- **Rule coverage is honest now** (rule-truth-01/rule-behavior-01, design
  D1/D2/D7 from the archived `2026-09-13-rule-enforcement-gaps` change):
  `extracted-rules.json` deleted — its ten agent-behavior rules live in the
  skill templates (commit-validator gains the six git-safety laws, four-laws
  the `rm -rf` and production-in-test prohibitions, scope-validator the
  pre-work failure-registry check), with a README mapping table. Eight
  semantic rules flipped to `enabled:false` / `status:"not-implemented"`,
  and README counts corrected (37 pattern rules, seven workflow templates,
  six skills).
- **Templates:** `spec-coherence` bootstraps the pinned runtime *before*
  verifying it (the gate could never pass on a fresh checkout) and takes
  dispatch inputs via `env:` (shell-injection); `smoke-gate` fails on its
  own failure sentinel (the old branch shape let every sentinel hit pass);
  `guardrails-compliance` forbidden-files matches basenames as globs
  (`.env` as an ERE failed `config/environment.yml`, which ci-match-01
  explicitly protects) and its header/summary now say which checks are
  advisory; template `drift-scan` fetches full history and installs
  typescript@5 before the semantic arm; `file-size-check` fails on
  *exceeding* the limit, not meeting it.

### Added

- **Rules hygiene gate** (`scripts/rules_check.py`, wired into CI): an
  enabled rule with no registered checker, a rules file that fails its
  schema, or an enabled rule missing message/severity now fails the build —
  asked of the scanner itself via `semantic-scan.mjs --list-checkers`.
- **SEMANTIC-005** (React `useEffect` missing dependencies) is actually
  implemented in `semantic-scan.mjs` — no-deps arrays and omitted free
  identifiers are reported (warning severity, `guardrails-allow
  SEMANTIC-005` escape), closing the header's long-standing claim.
- **CHECKSUMS.sha256** regenerated from the current tree (79 entries,
  `verify` green; at audit time 9 digests were stale and 8 shipped files had
  never been listed).

### Added (S5/S6 promote)

### Added
- **Readiness delta round 2** (S5/S6/S8 remainder, runtime-verifiable scope):
  - **Fifth monitor check class** `_check_spec_coherence` (coh-int-02) —
    polls coherence-gate check-runs on watched branches; failing or timed-
    out conclusions raise `coherence_failure`, and ABSENCE raises
    `coherence_absent` (default-deny: the gate may run-and-fail or
    explicitly skip, never silently vanish). Config:
    `HUB_COHERENCE_WORKFLOW_MATCH` (default "coherence").
  - **Immutable evidence store** (`hub/coherence/store.py`, S5) —
    content-addressed append-only objects; digest collisions with
    different content are hard errors; tamper-at-rest detected on read;
    upload after seal is retryable and RESUMABLE (already-held objects are
    verified skips, never blind duplicates).
  - **Total decision-cache key + retention invalidation** (coh-ctx-05,
    coh-ev-04) — the key binds subject, package, policy, context, image,
    plugins, captured facts, TTL, retention, AND signer; unknown-vs-
    attributed evaluator identity is part of the key; malformed cache
    entries miss, never hit; TTL and retention expiry both invalidate.
  - **Determinism drill** (`scripts/determinism_drill.py`, S8) — N repeat
    evaluations must be byte-identical (decision + claim); 100/100 locally,
    30 per CI run in the evaluator-integrity job.
  - **Per-runner fleet units** (coh-int-07) — `runner-enroll.sh` now
    installs `devgate-hb-<name>.{service,timer}` and
    `devgate-hb-watchdog-<name>.{service,timer}` plus a name-scoped env
    file, so one host can enroll multiple spokes without clobbering.
  - **Coherence CI workflow template** (`templates/github-workflows/
    spec-coherence.yml`, coh-int-01/05/06) — frozen exit-code-to-verdict
    adapter (default-deny: timeout/crash/unknown exit are ERROR, never
    neutral), named for the hub's check-run matcher.
  - **Runbooks** (`docs/runbooks/`) — hub outage, policy rollback + key
    rotation, evidence/attestation verification and transport; every
    command references implemented code, and external dependencies
    (registry credentials, branch-protection admin, pilot approvals) are
    named as blocked rather than papered over.

### Added
- **Coherence S5/S6 core — decisions become attributable and authoritative-
  ready** (`hub/coherence/attest.py`, new `--verify` CLI mode):
  - Detached attestations over canonical decisions per the frozen
    `attestation.schema.json` (coh-ev-01): produced in the acyclic sealing
    order AFTER the decision, binding all six input digests; re-signing
    leaves decision bytes unchanged. Honest stand-in scope: HMAC-SHA256
    under `HUB_COHERENCE_SIGNER_KEYS` (ADR-018 remains open for real key
    management). Attesting an execution with an unknown evaluator image
    identity is refused — an attestation witnesses the evaluator too.
  - Signer-set verification + revocation fail-closed (coh-ev-05):
    unknown-signer / revoked-signer / signer-outside-validity-window /
    key-mismatch / signature-mismatch / statement-substitution /
    bound-input-substitution — each a stable rejection reason; the offline
    verifier refuses to run without a signer set.
  - Anti-rollback (coh-pol-02): the signed context may carry
    `policy_epoch_floor` (additive context-schema field); bundles with
    `min_bundle_epoch` below the floor are rejected as rolled back, and
    `issue_context` can bind the floor plus a `signers.json` signer-set
    digest (coh-ctx-01 discipline applied to signers).
  - Execution identity (coh-id-04): the launcher injects the digest-pinned
    image ref (`DEVGATE_IMAGE_DIGEST`) and the in-container runtime
    self-identifies instead of recording null; malformed injections are a
    protocol error, absence stays an honest null.
  - Decision claims (fw-*): the pipeline emits `decision.claim.json` bound
    to every input digest and stops at OBSERVED — a producer cannot
    self-certify; consumers raise claims via `scripts/evidence-validate.py`.
  - Negative controls nc-09 (rolled-back bundle) and nc-10 (substituted
    decision under a valid attestation) join the permanent suite.
- **Fleet drill** (`scripts/fleet_drill.py`) — 19-step end-to-end drill of
  the real fleet path: hub subprocess over real HTTP, enrollment semantics
  (one-time consumption, duplicate 409, forged 401), heartbeats, the real
  watchdog script against alive AND dead hubs, SIGTERM clean shutdown,
  registry + token survival across restart, heartbeat soak. 19/19 held.
- **Benchmark corpus doubled to 12 tasks** (race condition, config
  precedence, idempotency-state, command injection, journal recovery,
  multi-file feature) — every task validated in BOTH directions. The
  control phase caught two flawed verifiers before they could produce
  numbers, and a real harness defect: control/verify phases now run on
  SEPARATE repo copies (fw-bench-02).

### Changed
- **The two vacuous self-gates are live** (fw-gate-*):
  - `silent-success-scan.sh` now runs 2 enabled families over the shipped
    service tree (inline swallowed `except: pass`; TODO/FIXME markers in
    `hub/`), with a scan-root/allowlist override and a canary suite
    (`tests/test_silent_success_gate.py`) proving the gate FAILS on a
    planted violation — a gate that cannot fail is decoration.
  - `spec_traceability.py --ratchet` records a covered-requirements floor
    (63/119, `.guardrails/traceability-ratchet.json`) and fails CI on any
    regression while unbuilt capabilities stay advisory; coverage growth
    is surfaced with a raise-the-floor hint (`--update-ratchet`).

### Added
- **Evaluator-integrity & evidence architecture** (`fw-*` audit pass) — the
  audit methodology becomes permanent infrastructure:
  - `hub/coherence/verification.py` — claim lifecycle with a frozen state
    ladder (REQUESTED→…→VERIFIED), digest-bound staleness invalidation
    (changed inputs demote VERIFIED→UNKNOWN, never silently), independent
    verification as the only path to VERIFIED, whole-tree content
    commitments, and honest completion summaries that cannot average
    claims into success.
  - `scripts/evidence-validate.py` — standalone fail-closed validator for
    sealed evidence bundles and verification claims (rejects tamper,
    malformed shapes, parent-escaping paths, self-certified VERIFIED).
  - `scripts/mutation_check.py` — controlled mutation testing
    (comparison/bool/constant/raise-removal operators, comment/docstring
    exclusion, crash-safe restore, `--self-check`). `evidence.py` now
    holds a 100% mutation kill rate; 9 blind spots found and closed.
  - `scripts/negative_controls.py` — permanent evaluator-integrity suite:
    8 controls (forged digests, foreign protocol, unapproved evaluator,
    hostile overlay, identity violation…) run through the real CLI, plus a
    positive canary so reject-everything degeneration is also caught.
  - `.benchmarks/` — coding-agent benchmark harness with hidden
    behavioral verification (argv[1] repo contract), control validation
    (a verifier passing the unsolved repo invalidates the task), 6 tasks
    across bugfix/feature/refactor/security/reliability/CLI, metrics with
    a failure taxonomy, and `multi_solver.py` strategy comparison with
    anti-correlation analysis and a shipped GAMING strategy that must
    stay rejected (proves hidden checks resist hardcoding).
  - `hub/coherence/resource_limits.py` + `scripts/resource_audit.py` —
    wall-clock budgets, output-capped subprocess runs, runaway detection,
    capped backoff, and honest child-process resource measurement.
  - `scripts/regression_corpus.py` — engineering memory: relevance
    selection (which historical failures does this diff risk?) and
    staleness audit (dead patterns, missing paths, unresolved entries).
  - CI `evaluator-integrity` job runs all of the above on every PR.
- **Verification-semantics tests** — `tests/test_evidence_integrity.py`,
  `tests/test_metamorphic.py`, `tests/test_resource_governance.py`,
  `tests/test_regression_corpus.py`: self-certification rejected, stale
  evidence demoted, canon/claim/overlay round-trip and commutation
  invariants, governed retry loops terminate, corpus semantics pinned.

### Fixed
- **`evidence.verify()` crashed on malformed manifests** (fw-ev-01) —
  objects as dict/string, entries with missing or non-string fields, and
  unreadable evidence files raised TypeError/KeyError through the tamper
  detector; all shapes now fail closed (False). Parent-escaping object
  paths are rejected without being read (fw-ev-02).
- **Pathologically deep JSON escaped as a raw traceback** (fw-rt-01) —
  RecursionError from the stdlib parser is a RuntimeError outside every
  stage handler's except tuple; the CLI now yields the documented
  invalid-input envelope (exit 30), with a main() backstop for all stages.
- **Non-object `overlay.json` crashed the CLI** (fw-pol-01) — an overlay
  file containing valid-but-non-object JSON raised AttributeError outside
  every caught family; now a policy-resolution error (exit 31).

### Added
- **Test-suite hardening** (`harden-test-suite`) — the coherence golden
  vectors are load-bearing: `compute_golden.py` imports the real canon module
  (verified byte-identical) and `test_hub_coherence_golden.py` asserts the
  frozen vectors plus the profile-rejection contract; a collection-floor
  meta-test fails when discovered test files shrink (the F12 class);
  chmod-based exit-33 tests skip under root; regression-check fixtures moved
  out of the repo tree.
- **Runner monitor hub** (`hub/coherence/` + `container/`) — turns an
  OpenSpec package + policy + signed evaluation context into a canonical,
  deterministic accept/reject decision with sealed evidence and a frozen
  exit-code matrix (0 PASS / 10 ADVISORY / 20 FAIL / 30-40 ERROR classes).
  Domain-separated canonical digests, digest-verified packages/contexts/
  policy, an overlay that can strengthen but never weaken central policy, a
  fingerprinted baseline ratchet with expiring exceptions, four built-in
  evaluators, atomic artifact emission with a temp-dir fallback, and a
  reference launcher + containerized driver enforcing digest-pinned,
  read-only, non-root, network-none Podman execution with an
  execution-profile identity registry. 13 frozen JSON schemas ship with the
  service (`hub/coherence/schemas/`); 60+ `coh-*` requirements live under
  `openspec/changes/devgate-spec-coherence-service/` (S1-S4 of 8 sprints
  delivered; S5 signing, S6 fleet integration, S7 3D slice, S8 release
  remain). ~4k lines of stdlib-only Python with behavioral conformance,
  exit-code, ladder, launcher, and container test suites.

- **Runner monitor hub** (`hub/`) — a stdlib-only Python service that watches
  the self-hosted runner fleet from one machine. Endpoints `/enroll`,
  `/heartbeat`, `/revoke`, `/health`; one-time enrollment tokens and
  per-runner revocable heartbeat tokens (constant-time compared); an atomic
  `runners.json` registry on a hub volume that is never committed. Polls the
  GitHub API per registered repo for runner online state, queue-drain age, the
  latest check-run conclusion per watched branch, and scheduled drift-scan
  recency, combining that with spoke heartbeats as **independent** evidence
  channels. Alerts are deduplicated by `(repo, check-class, runner)`: one
  GitHub issue per key, recurrence as a comment, every event appended to an
  append-only JSONL log. Ships `scripts/runner-enroll.sh` (enroll / `--revoke`
  / systemd user timer), a Containerfile + Podman quadlet template under
  `templates/runner-monitor/`, a spoke-side hub watchdog, and the
  deployment runbook `docs/runner-monitor-monitor-hub.md`. The hub is
  monitor-only by default and binds loopback unless deliberately widened; see
  the runbook's TLS and firewall notes before exposing it.
- `spec_traceability.py`: a marker line may now carry several requirement IDs
  (`// spec: a-01, b-02, c-03`). The pattern previously captured only the first
  ID, so a multi-ID marker silently covered one requirement and reported the
  rest as uncovered.
- **Spoke-side hub watchdog** (`scripts/hub-watchdog.sh` + a
  `devgate-hub-watchdog.timer` installed by `runner-enroll.sh`) — the inverted
  dead-man switch (`mon-deadman-01`). The hub cannot report its own death and a
  GitHub-scheduled workflow cannot report its own absence, so each spoke polls
  the hub's `/health` on a timer and fails its own systemd unit when the hub is
  unreachable or its poll loop has gone stale. Local-only by design: no token
  on the spoke, no GitHub issue. `/health` now also reports
  `polling_enabled` / `poll_interval_sec` so a watchdog can tell "no PAT,
  polling off by design" (`last_poll_at` null, warn) from a wedged poll loop
  (`last_poll_at` stale, fail) rather than reading an unconfigured hub as a dead
  one. `monitor.py` now actually records `last_poll_at` each cycle (it was
  declared but never written).
- `.github/workflows/hub-health-probe.yml` — the former
  `devgate-monitor-deadman.yml`, converted from a scheduled "dead-man switch"
  that only ever printed an `echo` line (its header claimed it would open a
  GitHub issue if the schedule stopped firing; nothing in GitHub Actions or in
  the file did so) into an honest `workflow_dispatch` hub probe. It shares the
  watchdog's verdict logic so a manual probe and the spoke check cannot
  disagree. No `schedule:`, since a workflow cannot report its own absence.


- `regression_check.py`: a scope that scanned zero files now prints an
  explicit NOTHING SCANNED notice instead of the clean-pass line
  (no-vacuous-green); new `--fail-if-empty` (exit 2 on zero-input runs, for
  CI) and `--base REF` (scan committed content as `diff REF...HEAD`) flags;
  `--json` output gains `files_scanned` and `vacuous`.
- `semantic-scan.mjs`: missing TypeScript parser error now states the gate
  evaluated nothing, and `DEVGATE_SEMANTIC_REQUIRED=0` opts into an explicit
  SKIPPED exit-0 for projects that cannot provide the parser.
- README/AGENTS.md: "Evidence quality" guidance — presence/substring-only
  tests are weak evidence, and hand-written-literal round-trips prove nothing
  about the real save/load path.


### Changed

- **Spec platform migration (`migrate-specs-to-openspec-conventions`).**
  `openspec validate --all --strict` passes 26/26 and the CLI now sees every
  capability's requirements (previously 15/15 specs failed and all read as 0
  requirements — two tools, two truths). All 17 main specs carry Purpose +
  Requirements + RFC-2119 SHALL/MUST; the three game specs were rewritten to
  describe the tooling that actually ships here (the phase matrix is marked
  planned, owned by the consuming game repo); two stale complete changes were
  archived (`fleet-add-01` published); the lost `mon-local-01` local-only
  posture requirement is restored; `ai01-runner-monitor-impl` gained its
  missing proposal and correct archive pointers; AGENTS.md documents the
  OpenSpec conventions and archive ceremony; CI enforces strict validation as
  a hard gate. Also: `extracted-rules.json` deleted (required absent by
  `rule-coverage-truth`, schema-violating, loaded by nothing);
  `game_regression.py` gained the standard `--fail-if-empty` /
  NOTHING SCANNED contract and honors `DEVGATE_PROJECT_ROOT`.


### Fixed

- **2026-09-19 audit remediation part 2 (`harden-security-boundaries`).**
  Trust-boundary and operational hardening; itemized record in
  `docs/qa/2026-09-19-audit-delta.md`.
  - **Coherence containment (F3/F4):** package inventory paths and assertion
    file selectors are validated for containment before any read — traversal,
    absolute paths, and symlink escapes are invalid input/UNRESOLVED, never
    host-file reads. Manifest size and digest now come from one streaming read
    (F11).
  - **Hub runtime (F2/F5-F10):** SIGTERM shuts the idle hub down promptly
    (serve-loop timeout; the old `handle_request()` blocked until the next
    request); enrollment uniqueness is decided atomically under the registry
    lock; JSON bodies are capped (`HUB_MAX_BODY_BYTES`, 413 before read);
    monitor alerts key on the real run `id`; the `default` watched-branch
    sentinel resolves via the API instead of 404'ing silently; Retry-After is
    read from the HTTP header; the poll thread snapshots the registry under
    the lock; killed podman clients reap their containers via `--cidfile`.
  - **Token hygiene (mon-sec-02):** heartbeat verifiers are salted-hashed at
    rest (legacy plaintext registries upgrade on load; revocation clears the
    verifier); `runner-enroll.sh` builds JSON with `json.dumps`, never prints
    the issued token (it goes straight to the 0600 env file), time-bounds
    every curl, and validates identity fields before unit generation.
  - **Template supply chain (ci-sec-01):** every shipped action is pinned to a
    40-hex commit SHA (including `gitleaks-action`, which receives
    `GITHUB_TOKEN`), container images are digest-pinned with the rotation
    procedure documented inline, and the runner-monitor image gains a
    `/health` HEALTHCHECK.
  - **Quadlet secrets:** one canonical mechanism — the quadlets declare
    `EnvironmentFile=` (raw env file) and all three runner/hub docs match it;
    the old instructions wrote a bare env file into a `.container.d/` drop-in,
    which is quadlet INI and never parsed.
  - **detect-host-ci.py:** lookaround-based redaction (`RUNNER_TOKEN=` caught,
    `blacksmith-2x` no longer mangled), bounded asset walk that skips
    unreadable files, `*.yaml` workflows discovered, `FROM --platform=`
    parsed.
  - New tests: `test_hub_coherence_containment.py`,
    `test_hub_hardening.py`, `test_detect_host_ci.py`,
    `test_template_supply_chain.py`, `test_runner_enroll.sh`; monitor tests
    for the sentinel resolution and queue-id keys.
- **2026-09-19 audit remediation (`fix-vacuous-and-broken-gates`,
  `fix-coherence-container-contract`).** Full-repo review findings F1 and the
  still-open C-series/H-series from `docs/qa/2026-09-13-full-qa.md` are closed;
  each fix is locked by a test that fails on the old behavior. See
  `docs/qa/2026-09-19-audit-delta.md` for the itemized record.
  - **Container contract (F1, critical):** the pinned evaluator image could
    not load its frozen schemas (`SCHEMA_DIR` resolved through a change-package
    path the image never carried) — every in-container request died exit 30
    with a misleading reason, and the only real-container test asserted that
    same exit for an invalid request. Schemas moved to `hub/coherence/schemas/`
    with package-relative resolution; smoke evidence now includes an
    in-image schema load and a valid-request PASS case; rejection reasons must
    name the invalid input.
  - **Scanner root anchoring (C2/C3):** `semantic-scan.mjs` and
    `run-tests.mjs` no longer escape to the parent of a standalone clone
    (EACCES crash / stranger trees / "0 tests across 0 files" exit 0 while the
    repo's own tests sat unrun). All scanners now share the layout contract;
    `tests/test_scanner_root_anchor.mjs` locks it.
  - **Test runner:** Rust files run via `cargo test --test <stem>` (the old
    positional filter matched function names, so integration files ran zero
    tests and passed); discovery covers `test_*.mjs` and the whole project
    tree — `tests/test_guardrails_scan.mjs` now executes under the runner.
  - **npm audit (C6):** a HIGH/CRITICAL vuln in a DIRECT runtime dependency
    is blocking again (npm's `effects` is empty for direct deps; classification
    now uses `isDirect` + dependency name + effect chains). Tooling failures
    (npm missing, timeout, empty/unparseable output) surface as warnings with
    a named reason instead of reading as "no vulnerabilities".
  - **Deploy (C7/H7):** `deploy.sh` detects standalone vs submodule layout and
    gates the PROJECT tree (regression_check/failure_registry_check/
    scene_inventory/log_failure anchored by layout contract, with
    `DEVGATE_PROJECT_ROOT` override); the twine upload no longer double-publishes
    (`(A||B)&&C` precedence bug aborted the pipeline after a successful
    immutable publish) and uploads only the just-released version's artifacts;
    the clean-tree gate includes untracked files; schema health blocks when a
    database is configured instead of silently warning.
  - **Markers (H6):** spec traceability accepts `# spec: <id>` alongside
    `// spec: <id>`, mirrored in the coherence evaluator's grammar;
    `findings_to_spec.py` emits per-language advice.
  - **Registry targeting (H8):** `log_failure.py` defaults to the project
    overlay (the bundled baseline needs `--baseline`); an explicitly named
    registry path that does not exist fails the hygiene gate instead of
    passing vacuously.
  - **scene_inventory (C1):** no more `xml.etree` dead-end (every valid
    `.tscn` reported "parse error"); connections match by node-path segment;
    empty scope prints NOTHING SCANNED and `--fail-if-empty` exits 2.
  - **Test collection:** `tests/__init__.py` + `conftest.py` — a foreign
    `tests` package on the machine silently dropped the five conformance files
    from collection; discovered live during this audit.
  - **Test-infra:** `tests/test_regression_audit.py`,
    `tests/test_log_failure.py`, `tests/test_failure_registry_check.py`,
    `tests/test_scene_inventory.py` added; PREVENT-024 false positives on
    local module imports annotated with audited same-line exceptions.
- **Gates:** tracked-artifact checks (COMMITTED-ENV/COMMITTED-GENERATED) now
  honor `.guardrailsignore` like the walk-based checks. One carve-out: a bare
  `.env` can never be ignored — that check is the framework's leak tripwire.
  Hygiene variants (.env.testing, .env-redacted) stay ignorable.
- **Gates:** file-size gate exempts generated files — a source file whose
  first 1KB contains a "Code generated" marker is skipped from line counting
  (build artifacts, not hand-maintained code). Validated on rad-gateway:
  3 generated files left the report, hand-written oversize files unchanged.
- **Gates:** `regression_check.py` no longer crashes on repositories with
  non-UTF-8 bytes in git diff output (`UnicodeDecodeError` before any summary
  was printed). `run_git_command` now decodes with `errors="replace"`, so the
  file-size gate runs to completion and reports real counts on such trees.


- `regression_check.py --all` no longer crashes on repositories with no tags
  and 20 or fewer commits (`RuntimeError: could not diff HEAD~20...HEAD`); it
  falls back to the empty-tree base and scans the whole reachable tree.
- `spec_traceability.py` now discovers the standard OpenSpec change-package
  layout (`openspec/changes/<change>/specs/**/*.md`, archived changes
  excluded) in addition to `openspec/specs/<capability>/spec.md`, and
  distinguishes "no spec files found" from "spec files found but 0
  requirement IDs in the <!-- id: --> format" instead of reporting both as
  "no specs found under openspec/specs/".

## [1.3.0] - 2026-09-23

### Highlights

First release with **hosted CI on every push** (the framework's own gates
execute on GitHub runners: test suite, self-gates, specs strict validation,
evaluator-integrity attacks, container-image build + GHCR publish). The
spec-coherence evaluator image is now **published**
(`ghcr.io/thearchitectit/devgate-agentic-framework/devgate-coherence`),
digest-pinned in `container/execution-profiles.json`, and consumers get a
byte-equivalence-verified local invocation (`scripts/coherence-local`).

The fw-* readiness program adds a permanent evaluator-integrity CI job:
mutation testing with a self-check, ten negative controls through the real
CLI, a both-direction-validated benchmark corpus, fleet and determinism
drills, an allowlist-growth monitor, and test-count floors.
- **Hub service discovery:** `GET /services` and `GET /services/<name>` on the
  runner-monitor hub resolve a stable service *name* to the enrolled runner's
  `host_alias` + port, so CI stops baking literal IPs into repo variables
  (`mon-svcdisco-01`). Backed by `hub/services.py` (atomic `services.json`
  load/save, schema-validated) and `hub/schema/services.{schema,example}.json`.
  `resolve()` reports `resolved` from live enrollment and only sets `host` when
  an enrolled runner publishes an address — never an invented IP. The
  `templates/ci/service-endpoint.sh` wrapper prints `host:port` for a named
  service (fail-closed on unknown/unresolved) with an optional checked-in
  fallback map.

### Fixed

- **Runner enrollment:** the heartbeat unit no longer uses an inline `bash -c`
  ExecStart. systemd expands `$` in `ExecStart` against the unit's own
  environment, so the variables the body defined for itself (`DISK_OK`,
  `PODMAN_OK`) arrived empty, the POST went out as malformed JSON, the hub
  rejected it, and the unit exited 22 on *every tick* while enrollment still
  reported success. `ExecStart` now points at a copied
  `scripts/runner-heartbeat.sh`.
- **Runner enrollment:** units and the token env file are named per runner
  (`devgate-hb-<name>`, `devgate-watchdog-<name>`,
  `devgate-heartbeat-<name>.env`), so enrolling a second runner on one host no
  longer overwrites the first runner's token. Two names that sanitize to the
  same unit name are refused rather than merged. Legacy fixed-name units are
  retired for the runner being re-enrolled, and left alone when they belong to
  another.

### Fixed (pre-existing)

- **Gates:** tracked-artifact checks (COMMITTED-ENV/COMMITTED-GENERATED) now
  honor `.guardrailsignore` like the walk-based checks. One carve-out: a bare
  `.env` can never be ignored — that check is the framework's leak tripwire.
  Hygiene variants (.env.testing, .env-redacted) stay ignorable.
- **Gates:** file-size gate exempts generated files — a source file whose
  first 1KB contains a "Code generated" marker is skipped from line counting
  (build artifacts, not hand-maintained code). Validated on rad-gateway:
  3 generated files left the report, hand-written oversize files unchanged.
- **Gates:** `regression_check.py` no longer crashes on repositories with
  non-UTF-8 bytes in git diff output (`UnicodeDecodeError` before any summary
  was printed). `run_git_command` now decodes with `errors="replace"`, so the
  file-size gate runs to completion and reports real counts on such trees.

### Added

- **Runner monitor hub** (`hub/`) — a stdlib-only Python service that watches
  the self-hosted runner fleet from one machine. Endpoints `/enroll`,
  `/heartbeat`, `/revoke`, `/health`; one-time enrollment tokens and
  per-runner revocable heartbeat tokens (constant-time compared); an atomic
  `runners.json` registry on a hub volume that is never committed. Polls the
  GitHub API per registered repo for runner online state, queue-drain age, the
  latest check-run conclusion per watched branch, and scheduled drift-scan
  recency, combining that with spoke heartbeats as **independent** evidence
  channels. Alerts are deduplicated by `(repo, check-class, runner)`: one
  GitHub issue per key, recurrence as a comment, every event appended to an
  append-only JSONL log. Ships `scripts/runner-enroll.sh` (enroll / `--revoke`
  / systemd user timer), a Containerfile + Podman quadlet template under
  `templates/runner-monitor/`, a spoke-side hub watchdog, and the
  deployment runbook `docs/runner-monitor-monitor-hub.md`. The hub is
  monitor-only by default and binds loopback unless deliberately widened; see
  the runbook's TLS and firewall notes before exposing it.
- `spec_traceability.py`: a marker line may now carry several requirement IDs
  (`// spec: a-01, b-02, c-03`). The pattern previously captured only the first
  ID, so a multi-ID marker silently covered one requirement and reported the
  rest as uncovered.
- **Spoke-side hub watchdog** (`scripts/hub-watchdog.sh` + a
  `devgate-hub-watchdog.timer` installed by `runner-enroll.sh`) — the inverted
  dead-man switch (`mon-deadman-01`). The hub cannot report its own death and a
  GitHub-scheduled workflow cannot report its own absence, so each spoke polls
  the hub's `/health` on a timer and fails its own systemd unit when the hub is
  unreachable or its poll loop has gone stale. Local-only by design: no token
  on the spoke, no GitHub issue. `/health` now also reports
  `polling_enabled` / `poll_interval_sec` so a watchdog can tell "no PAT,
  polling off by design" (`last_poll_at` null, warn) from a wedged poll loop
  (`last_poll_at` stale, fail) rather than reading an unconfigured hub as a dead
  one. `monitor.py` now actually records `last_poll_at` each cycle (it was
  declared but never written).
- `.github/workflows/hub-health-probe.yml` — the former
  `devgate-monitor-deadman.yml`, converted from a scheduled "dead-man switch"
  that only ever printed an `echo` line (its header claimed it would open a
  GitHub issue if the schedule stopped firing; nothing in GitHub Actions or in
  the file did so) into an honest `workflow_dispatch` hub probe. It shares the
  watchdog's verdict logic so a manual probe and the spoke check cannot
  disagree. No `schedule:`, since a workflow cannot report its own absence.

### Fixed

- `regression_check.py --all` no longer crashes on repositories with no tags
  and 20 or fewer commits (`RuntimeError: could not diff HEAD~20...HEAD`); it
  falls back to the empty-tree base and scans the whole reachable tree.
- `spec_traceability.py` now discovers the standard OpenSpec change-package
  layout (`openspec/changes/<change>/specs/**/*.md`, archived changes
  excluded) in addition to `openspec/specs/<capability>/spec.md`, and
  distinguishes "no spec files found" from "spec files found but 0
  requirement IDs in the <!-- id: --> format" instead of reporting both as
  "no specs found under openspec/specs/".

### Added (gates)

- `regression_check.py`: a scope that scanned zero files now prints an
  explicit NOTHING SCANNED notice instead of the clean-pass line
  (no-vacuous-green); new `--fail-if-empty` (exit 2 on zero-input runs, for
  CI) and `--base REF` (scan committed content as `diff REF...HEAD`) flags;
  `--json` output gains `files_scanned` and `vacuous`.
- `semantic-scan.mjs`: missing TypeScript parser error now states the gate
  evaluated nothing, and `DEVGATE_SEMANTIC_REQUIRED=0` opts into an explicit
  SKIPPED exit-0 for projects that cannot provide the parser.
- README/AGENTS.md: "Evidence quality" guidance — presence/substring-only
  tests are weak evidence, and hand-written-literal round-trips prove nothing
  about the real save/load path.

## [1.2.0] - 2026-09-04

### Added

- Self-hosted runner standard under `templates/runner/`: the official
  `ghcr.io/actions/actions-runner` image deployed as a Podman quadlet, with
  secret drop-ins, durable registration, and no hosted-runner fallback.
- Scheduled drift-scan workflow templates plus `scripts/detect-host-ci.py`,
  which reads a host repo's own workflows and reports the `runs-on:` labels and
  `schedule:` crons already declared there (secrets redacted).
- The spec traceability gate (`scripts/spec_traceability.py`): every OpenSpec
  requirement ID needs a `// spec: <id>` marker in a source file, advisory by
  default and blocking per capability.
- Reusable gate patterns ported from the game project (scene inventory,
  file-size check, guardrails compliance, secret validation, smoke gate) under
  `templates/`.
- Go rules for rune digits, listen-on-all-interfaces, and unclosed file
  handles; newly surfaced rule warnings.
- GitHub Sponsors (`FUNDING.yml`, README section, badge).

### Changed

- Gates now **block** a deploy on failure rather than warning (regression,
  guardrails, build, test), with an incident-proven failure-registry
  enforcement loop.
- `exclude_glob` support and `**` globstar parity in the gate configuration
  contract, plus a registry hygiene gate.
- The game framework is absorbed directly instead of being carried as a
  submodule.

### Fixed

- `regression-check` honors a rule's `file_glob`; `info` findings are advisory.
- `run-tests.mjs` parser repaired — a crashed test file now fails the gate
  instead of passing silently. Rust test-file support added.
- The `.devgate` tree is excluded from the marker scan.

## [1.1.0] - 2026-08-08

### Changed

- All scripts are now fully generic: they auto-detect the project root,
  language, and package manager instead of assuming a fixed layout. Rewrote
  `regression_check.py`, `run-tests.mjs`, `semantic-scan.mjs`,
  `guardrails-scan.mjs`, `schema-health-check.mjs`, and `deploy.sh` against the
  detected project rather than a hardcoded tree, and updated AGENTS.md and the
  README to match.

## [1.0.0] - 2026-08-08

### Added

- First tagged release, cut as part of the guardrails control-plane
  architecture so consumers can pin DevGate as a versioned submodule instead of
  vendoring drifting copies.
- Static/CI quality gates: pattern and semantic scans, regression check, test
  isolation, deploy gate, and drift scans, with GitHub workflow templates and a
  runner under `templates/`.
- Policy skill templates under `templates/skills/` (Four Laws, halt conditions,
  production-first, scope validator, three strikes, commit validator). The
  canonical versions of these rules now live in
  [guardrail-policy-packs](https://github.com/TheArchitectit/guardrail-policy-packs)
  (`core/` pack v1.0.0); the copies here remain for compatibility until
  consumers migrate to pinned packs.
