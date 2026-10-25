# 2026-10-25 - bundled baseline hygiene: ten foreign entries removed, and the gate now fails on them (`base-own-01`)

Requirement: `baseline-ownership` / `base-own-01` - *"Every entry in a bundled
baseline data file (failure registry, silent-success allowlist, prevention
rules, openspec specs) SHALL reference only paths, bugs, and capabilities of
this repository; a hygiene gate SHALL fail when a bundled entry references a
path absent from this tree."* Its second scenario names the clean-checkout
half: *"a clean checkout is warning-free"* - `failure_registry_check.py` exits
0 with no stale-path warnings.

Both halves were false, and the warning half was hiding the error half.

## What was measured

`python3 scripts/failure_registry_check.py` on a clean checkout printed
**eleven** stale-path warnings over **seven** entries and exited **0**.


An earlier draft of this record counted **six** removals and **eight** warned
entries. Both figures came from the warning list alone; the correct counts are
**ten** and **seven**. It also said five entries named a path that exists here,
and that "every one of the nine removed entries that carried a SHA" used a
7-character prefix; the measured split is **four** and **eight of nine** (the
ninth is `FAIL-20cc1a39`, whose 40-character SHA passed only because a backfill
had put a real local commit there). The first two of those figures also appear
in the message of `a8bde2d`, which cannot be edited without rewriting pushed
history; they are corrected here instead.

## What was wrong

The bundled `.guardrails/failure-registry.jsonl` ships to every consumer. It
had drifted into a partial copy of three other repositories' histories:

- **`gamerepo01`** (the Go + TypeScript game) - five entries. Every
  `fix_commit` resolves in that repository and in none of this one's history:
  `b01514c`, `6ebeffe`, `1f3dedb` (twice), `19a1374`.
- **`devgate-game-framework`** (a consumer that runs DevGate's own scripts) -
  three entries. `5edf702` (twice) and `0a4b701` resolve there.
  `scripts/regression_diff.py` exists in *both* repositories, which is exactly
  why the path check stayed quiet about two of them.
- **`OpenRawFlow`** - one entry, `FAIL-20cc1a39`, the consumer's CI gate-suite
  skip naming `.github/workflows/devgate-gates.yml` (a file that has never
  existed here). It was filed into this repository deliberately: `3ef483c`
  (2026-09-22) says so and records `fix_commit: "pending"` - *"the
  consumer-side fix commit lives in OpenRawFlow, not this repo's history"*.
  Six days later `ac6e13e` ("Backfill fix_commit for ... FAIL-20cc1a39
  (db238bf)") replaced that `pending` with a real local SHA, so a foreign entry
  ended up looking hub-owned. `db238bf` is a real commit here and its subject
  is "fix(ci): pytest install for the gates job (test floors)" - nothing to do
  with a gate suite skipped behind a rust check. The backfill made the entry
  pass an ownership test it should have failed; it is the one finding in this
  record that a path sweep could never have produced.
- **`FAIL-2026071302`** - `fix_commit: "pending"`, so no repository can be
  named for it. Its paths (`src/store.test.ts`, `src/engine.test.ts`) have zero
  commits in this repository's entire history, so it fails `base-own-01` on the
  path clause alone.

All ten were removed as whole-line deletions. Nothing else in the file was
reformatted, and the two header comment lines are untouched. Their records are
preserved verbatim below so the owning repositories can re-file them into their
own overlays; this change does not edit those repositories.

## The ten removed (verbatim, for the record)

| failure_id | date | category | affected_files as written | fix_commit |
|---|---|---|---|---|
| `FAIL-2026071302` | 2026-07-13 | lint | `src/store.test.ts`, `src/engine.test.ts` | pending |
| `FAIL-fc601f4b` | 2026-09-03 | runtime | `go/internal/engine/game.go,go/internal/generator/generator.go,go/internal/sprites/manager.go` | b01514c |
| `FAIL-83074e86` | 2026-09-03 | runtime | `go/internal/engine/save.go,go/cmd/game/main_test.go` | 6ebeffe |
| `FAIL-d6c6e7c5` | 2026-09-07 | build | `.github/workflows/ci.yml` | 1f3dedb |
| `FAIL-b97103df` | 2026-09-07 | test | `.gitignore`, `go/assets/generated` | 1f3dedb |
| `FAIL-3bc44d38` | 2026-09-08 | regression | `scripts/regression_diff.py`, `.github/workflows/ci.yml` | 5edf702 |
| `FAIL-9231181d` | 2026-09-08 | regression | `scripts/regression_diff.py` | 5edf702 |
| `FAIL-72da6333` | 2026-09-08 | regression | `go/cmd/game/runtime.go` | 19a1374 |
| `FAIL-07a50c72` | 2026-09-08 | regression | `.devgate/.guardrails/failure-registry.jsonl` | 0a4b701 |
| `FAIL-20cc1a39` | 2026-09-22 | config | `.github/workflows/devgate-gates.yml` | db238bf013cc8ab85486b0e1c0009072682e37f1 |

`FAIL-07a50c72`'s message names `FAIL-72da6333`, which is also in this set; the
reference is preserved as written in the record below.

````jsonl
{"failure_id": "FAIL-2026071302", "timestamp": "2026-07-13T09:12:00Z", "category": "lint", "severity": "medium", "error_message": "Pre-existing lint failures in test files (unused imports, stale references)", "root_cause": "Test files shipped with unused imports and stale references; lint was red before any new work", "affected_files": ["src/store.test.ts", "src/engine.test.ts"], "fix_commit": "pending", "regression_pattern": "TS6133 unused import / TS2353 unknown property in committed tests", "prevention_rule": "Run tsc --noEmit in CI pre-commit; fix test files so the gate is green", "status": "resolved", "updated_at": "2026-07-13T15:21:40.050878Z"}
{"failure_id": "FAIL-fc601f4b", "timestamp": "2026-09-03T01:43:17Z", "category": "runtime", "severity": "high", "error_message": "Level-up message built via string(rune('0'+level)): garbage output for level >= 10 (same class also hit generator sceneKey and sprites variant naming)", "root_cause": "Digit conversion by rune arithmetic instead of strconv.Itoa", "affected_files": ["go/internal/engine/game.go,go/internal/generator/generator.go,go/internal/sprites/manager.go"], "fix_commit": "b01514c", "regression_pattern": "string\\(rune\\('0'\\s*\\+", "prevention_rule": "PREVENT-030", "status": "resolved", "updated_at": "2026-09-03T01:43:17Z", "file_glob": ["*.go"]}
{"failure_id": "FAIL-83074e86", "timestamp": "2026-09-03T01:43:17Z", "category": "runtime", "severity": "medium", "error_message": "Save files written to bare CWD-relative paths: test/prod separation failures and saves lost when launched from another directory", "root_cause": "No path anchor for savegame.json/meta.json; os.Chdir-dependent tests", "affected_files": ["go/internal/engine/save.go,go/cmd/game/main_test.go"], "fix_commit": "6ebeffe", "regression_pattern": "", "prevention_rule": "", "status": "resolved", "updated_at": "2026-09-03T01:43:17Z", "file_glob": ["*.go"]}
{"failure_id": "FAIL-d6c6e7c5", "timestamp": "2026-09-07T20:49:34Z", "category": "build", "severity": "high", "error_message": "go build -v ./cmd/game fails in CI: /usr/bin/ld: cannot find -lXxf86vm: No such file or directory (collect2: ld returned 1)", "root_cause": ".github/workflows/ci.yml \"Install dependencies\" step omitted libxxf86vm-dev, which Ebiten's X11 backend links against (-lXxf86vm); build.yml already listed it.", "affected_files": [".github/workflows/ci.yml"], "fix_commit": "1f3dedb", "regression_pattern": "", "prevention_rule": "Keep ci.yml's X11 apt list in sync with build.yml; include libxxf86vm-dev alongside the other -dev packages.", "status": "resolved", "updated_at": "2026-09-07T20:49:34Z"}
{"failure_id": "FAIL-b97103df", "timestamp": "2026-09-07T20:49:34Z", "category": "test", "severity": "high", "error_message": "xvfb-run go test fails: asset \"*.png\" missing from assets/generated: stat ../../assets/generated/*.png: no such file or directory (spawners_test.go + paths_test.go)", "root_cause": "go/assets/generated/ was excluded by .gitignore line 9, so the 31 runtime assets were never committed; asset-existence tests failed on fresh CI checkouts.", "affected_files": [".gitignore", "go/assets/generated"], "fix_commit": "1f3dedb", "regression_pattern": "go/assets/generated", "prevention_rule": "Track generated runtime assets in git; do not re-add go/assets/generated/ to .gitignore.", "status": "resolved", "updated_at": "2026-09-07T20:49:34Z", "file_glob": [".gitignore"]}
{"failure_id": "FAIL-3bc44d38", "timestamp": "2026-09-08T01:25:00Z", "category": "regression", "severity": "high", "error_message": "regression gate passed vacuously on shallow CI checkouts: git diff base...HEAD rc!=0 silently skipped, zero lines scanned, step green in ~1s", "root_cause": "get_added_lines --all swallowed a failing base diff; the devgate CI job checkout is fetch-depth 1 (no tags), so the tag base never resolved", "affected_files": ["scripts/regression_diff.py", ".github/workflows/ci.yml"], "fix_commit": "5edf702", "regression_pattern": "", "prevention_rule": "A gate must fail loud when it scanned nothing: raise on nonzero rc from the --all base diff; CI regression jobs fetch full history", "status": "resolved", "updated_at": "2026-09-08T01:25:00Z"}
{"failure_id": "FAIL-9231181d", "timestamp": "2026-09-08T01:25:00Z", "category": "regression", "severity": "medium", "error_message": "diff-based registry scan flagged guardrails-allow'd lines: spawners_test.go comment asserting the anti-pattern's ABSENCE read as a re-add of FAIL-fc601f4b", "root_cause": "check_added_against_registry ignored guardrails-allow annotations that game_regression.py honours, so the two scanners contradicted each other on the same tree", "affected_files": ["scripts/regression_diff.py"], "fix_commit": "5edf702", "regression_pattern": "", "prevention_rule": "Annotation handling must be identical in every scanner (keyed on failure_id/prevention_rule, per game_regression.line_has_allow)", "status": "resolved", "updated_at": "2026-09-08T01:25:00Z"}
{"failure_id": "FAIL-72da6333", "timestamp": "2026-09-08T02:14:52Z", "category": "regression", "severity": "medium", "error_message": "PREVENT-010 gate audit: profiling auto-exit ran time.Sleep inside a bare goroutine (uncancellable — the timer kept sleeping after a clean shutdown) and the pprof server ran http.ListenAndServe on a listener nothing owned (port stayed bound, goroutine outlived main's defers).", "root_cause": "Fire-and-forget goroutines with no cancellation handle, flagged by PREVENT-010 (go func without context).", "affected_files": ["go/cmd/game/runtime.go"], "fix_commit": "19a1374", "regression_pattern": "time\\.Sleep\\(time\\.Duration\\(\\*profileDuration\\)", "prevention_rule": "Duration-triggered shutdown must use time.AfterFunc with a deferred Stop; an HTTP debug server must bind its own net.Listener at the call site (defer Close) and be served via http.Serve, never http.ListenAndServe on an unowned listener.", "status": "resolved", "updated_at": "2026-09-08T02:40:00Z"}
{"failure_id": "FAIL-07a50c72", "timestamp": "2026-09-08T03:04:03Z", "category": "regression", "severity": "low", "error_message": "failure_registry_check.py exited 1: FAIL-72da6333 logged with empty fix_commit because log_failure.py ran before the fixing commit existed.", "root_cause": "Registry appends made mid-unit can't know their own commit SHA; the validator requires fix_commit on resolved entries.", "affected_files": [".devgate/.guardrails/failure-registry.jsonl"], "fix_commit": "0a4b701", "regression_pattern": "", "prevention_rule": "Order of operations per unit: commit the fix, then log_failure.py --fix-commit <sha>, then push. Never append a resolved entry with an empty fix_commit; if already pushed, backfill only fix_commit/updated_at in a follow-up.", "status": "resolved", "updated_at": "2026-09-08T03:04:03Z"}
{"failure_id": "FAIL-20cc1a39", "timestamp": "2026-09-22T22:28:55Z", "category": "config", "severity": "high", "error_message": "CI gate suite sat after the failing rust check, so all four DevGate scan gates were skipped on every push", "root_cause": "the Run gate suite step followed a fail-prone rust check with no condition of its own, and its summary/exit loop iterated RESULTS[rust] which was never assigned", "affected_files": [".github/workflows/devgate-gates.yml"], "fix_commit": "db238bf013cc8ab85486b0e1c0009072682e37f1", "regression_pattern": "", "prevention_rule": "gate-suite step gated on !cancelled() plus checkout success, rust outcome seeds RESULTS[rust], regression gate passes --fail-if-empty; asserted in devgate-gates.yml. Filed WITHOUT regression_pattern: every faithful pattern for this failure also matches the fix commit's own added lines, which false-fires the gate in 20-commit fallback windows (proven via --all on 2026-09-22); the guard lives in the prevention text and the workflow condition, not a regex", "status": "resolved", "updated_at": "2026-09-27T13:53:52.964513+00:00"}
````

## What the gate does now

`scripts/failure_registry_check.py` splits the same finding by SOURCE, which is
what the requirement says ("a *bundled* entry"):

| Finding | Bundled (`devgate`) | Overlay / explicit file |
|---|---|---|
| `affected_files` path absent from the tree | **error** (new, `base-own-01`) | warning, unchanged |
| `fix_commit` full 40-char SHA absent from the owner's history | error, unchanged | error, unchanged |
| `fix_commit` short SHA (7-39 hex) absent from the owner's history | **error** (new) | not resolved, unchanged |
| any of the above where the owner has no git history at all | warning `unverified` (new) | n/a |

The short-SHA clause is the one that mattered in practice: **eight of the nine
removed entries that carried a SHA carried a 7-character prefix**, and the old
rule only resolved 40-character values, so none of those eight had ever been
checked. (The ninth, `FAIL-20cc1a39`, carried a 40-character SHA and passed
only because `ac6e13e` had backfilled a real local commit into it.) A copy or
tarball install (no `.git`) now warns
`fix_commit '...' unverified - no git history at <owner>` instead of failing:
the question is unanswerable there, and a warning is what that is.

`check()` gained keyword-only `devgate_root` / `project_root` seams so tests can
present a two-repo layout in-process; `main()` and the documented environment
override are unchanged. The overlay keeps its lenient contract on purpose: a
project overlay legitimately goes stale as the project renames files, and the
overlay is the thing the project refreshes.

### Before and after, on identical input

A scratch worktree of `8576940` (pre-change script) with one extra entry
planted - `affected_files: ["go/internal/engine/save.go"]`,
`fix_commit: "5edf702"`:

- pre-change script: **exit 0**, twelve stale-path warnings, **no finding at
  all** about the foreign SHA.
- post-change script, same tree: **exit 1** - nine `fix_commit '...' not found
  in git history` errors (the eight removed entries still present in that
  worktree, plus the planted one) and twelve
  `base-own-01 - bundled entry references a path absent from this tree` errors.

## Verification

- `python3 scripts/failure_registry_check.py` on this tree - exit 0, no
  findings.
- Registry: 43 -> 33 lines total, 41 -> 31 data lines, two header comments
  untouched, ten whole-line deletions.
- `python3 -m pytest tests/test_failure_registry_check.py -q` - **13 passed**
  (5 before). The eight new tests cover: bundled stale path -> error; bundled
  live path -> clean (positive control); overlay stale path -> warning +
  exit 0; bundled foreign short SHA -> error; bundled *local* short SHA ->
  clean (positive control); bundled foreign full SHA -> error; bundled short
  SHA with no git history -> warning, exit 0; overlay foreign short SHA -> not
  resolved, exit 0.
- The same new tests run against the pre-change script in a scratch worktree of
  `8576940` - 8 failed (the seam does not exist there), which is why the
  behavioural pair above was also measured through the CLI on a fixed tree.

## Not done here

- Five `pending` and five `(this commit)` `fix_commit` placeholders remain in
  the bundled file (`FAIL-2026071301`, `FAIL-3619d624`, `FAIL-2026091910/11/12`
  and the five `FAIL-fw-*` entries). They are not path- or ownership-findings,
  and guessing a SHA for them would be worse than leaving the placeholder
  visible; closing them is a separate `fix_commit`-coverage seam.
- The ten removed records are preserved verbatim above, not migrated. Filing
  them into the owning repository's overlay is that repository's call.
- The overlay warning contract is deliberately unchanged - see the table above.
