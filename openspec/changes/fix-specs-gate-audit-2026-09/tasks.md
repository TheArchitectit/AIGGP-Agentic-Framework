# Tasks: fix-specs-gate-audit-2026-09

Ledger of the 2026-09-20 drift audit's findings and their dispositions. A checked
box means the work landed on this branch; an unchecked box is open and says why.

## CRITICAL — declared hard spec gate red (26/31 failing strict validation)

- [x] Transform the 29 AIGGP delta specs to the delta grammar (`## ADDED
      Requirements`, `### Requirement:`, `#### Scenario:`, uppercase verbs).
- [x] Conform the 12 standard base specs: real `## Purpose`, `## Requirements`
      umbrella, demoted requirements. Demotion is required — a level-2
      requirement is a sibling of the umbrella, not a child.
- [x] Keep every existing ID marker and scenario block untouched; add no IDs.
- [x] Author the four genuine residuals (they were authoring defects the
      demotion exposed, not formatting): the aiggp-02 promote-halt requirement
      that shipped with zero scenarios, and the three game specs that had no
      requirement headers at all.
- [x] Normalize `SHALL not` → `SHALL NOT` across the affected files (the
      transform uppercased the modal but not the negation, freezing a
      pre-existing mixed casing).
- [x] Record the import status on all 11 AIGGP proposal.md files: imported
      draft, program not started, not a commitment.
- **Result:** `openspec validate --all --strict` → passes with 0 failures, exit 0.
  Traceability still exits 0 (advisory, uncovered requirements are a warning not
  a gate). **No coverage ratio is quoted here, on purpose.** An earlier revision
  of this line said "unchanged at 65/100" — which was wrong twice over: the
  figure was already stale when written (main measured 68/107, HEAD 69/107 after
  the S6 `.sh` fix), and it contradicted the very next sentence's rule against
  fixed numbers. The invariant that matters is the *exit status* and the
  advisory-vs-blocking classification; both are unaffected by this branch.
  **The item total is deliberately not quoted as a fixed number either.** `--all`
  counts *discovered* items, so this package's own addition moved it 31 → 32; any
  prose figure goes stale the moment a package is added. Two landed commit
  messages on this branch cite "31/31" — that was the count at the time of
  those commits (before this package existed), not an error, but the live
  tree is 32. Do not hardcode the total anywhere that outlives a commit.

## HIGH — self-test lane false green

- [x] Reproduce the escape before fixing: the audit's `run-tests.mjs` finds zero
      DevGate tests and exits 0; semantic-scan counted thousands of foreign
      files (the audit's snapshot was 16168; a re-run of the old walk-up today
      counts 21316 — the figure moves with sibling repos, the escape does not).
- [x] Create `tests/test_scanner_root_anchor.mjs` (the fixture `ci.yml`
      referenced but which never existed in any commit) and watch it go RED
      against the pre-fix scanners.
- [x] Add `scripts/lib/project-root.mjs` as the single layout contract; import
      it from `run-tests.mjs`, `semantic-scan.mjs`, and `guardrails-scan.mjs`.
- [x] Add the non-vacuity guard: zero discovery fails closed with a reason, with
      `DEVGATE_ALLOW_NO_TESTS=1` as the one explicit, loud skip.
- [x] Mutation-verify both guards (ancestor walk-up; inverted precedence;
      inert zero-discovery guard; opt-out truthy test) — each killed by a named
      check. The fixture's parent carries a marker file so the ancestor-search
      mutants are killable at all.
- **Result:** `node scripts/run-tests.mjs` discovers 39 files / 600 passed,
  where the audit recorded `TOTAL: 0 passed` exit 0.
- [x] Fresh-eyes audit of the fix (independent agent, 2026-09-21) found **two
      mutants surviving** the original 9-check fixture: `cwdRoot` (resolve from
      `process.cwd()`) and `caseless` (case-folded `.devgate` match). Both were
      real defects; both survived because no case spawned a scanner from
      outside the tree or installed it under a mis-cased directory.
- [x] Close them with three new checks (now 12): a foreign-cwd spawn for
      `run-tests` and `semantic-scan` (the foreign cwd carries its own passing
      tests, so a cwd-rooted scanner reports a populated, green, *wrong* tree
      rather than an error the assertion could misread), and a case-exact
      `.DevGate` install that must NOT be treated as the submodule marker.
- [x] Also close the audit's finding that `guardrails-scan.mjs`'s root was
      asserted by no test despite the fixture header claiming otherwise: a
      PREVENT-001 tripwire file planted on both sides, so the reported
      violation path names the tree actually scanned. `.guardrails/` is now
      copied into the synthetic repo — without it the scanner loads zero rules
      and the check would pass vacuously against any root.
- [x] Re-run the full battery — 7 mutants, **zero survivors**: `selfFirst` (1
      check), `parentAlways` (9), `caseless` (1), `cwdRoot` (3), `noFailClosed`
      (3), `truthySkip` (1), `guardWalkup` (1).
- [x] Clean the nits that same audit raised: dead `markerless` parameter and
      its stale header prose, and the now-unused `resolve` import in
      `run-tests.mjs`.
- [x] Correct the `16168` figure. It was quoted as fact in three places but is a
      frozen snapshot: re-running the old walk-up today counts **21316** sibling
      files. The comment now says thousands and names the moving figure, so the
      claim cannot rot into a falsehood.

### Regression and restoration, five days on (2026-09-26)

The contract above was **quietly undone on main** and its escape class
re-entered through data. Recorded here rather than quietly corrected, per the
disposition rule this package set.

- [x] **The deletion.** `9c19259` ("fix(container): COPY the change-package
      schema dir into the evaluator image") deleted all 395 lines of
      `tests/test_scanner_root_anchor.mjs` under a container-only commit
      message. Nothing else in CI ran it — `ci.yml` had replaced its explicit
      step with a comment claiming the fixture was "superseded by the python
      root contract suite", which is false: `test_python_root_anchor.py` pins
      only the three Python scanners (its file names the .mjs fixture once, in
      its own docstring). The 14-check Node battery went to zero, leaving
      all three Node scanners' root contract pinned by nothing.
- [x] **The escape re-entered via data.** `cf3f6e4` (fw-scope-01, scope.json as
      the single skip_dirs source) resolved `.guardrails/scope.json` by walking
      up from `process.cwd()` in all three scanners — the root-anchor-01
      ancestor-escape class again, this time choosing *which scope file to
      trust* rather than which tree to scan. In `run-tests.mjs` the walk-up was
      also broken outright: it called `dirname` without importing it, so any
      invocation whose cwd lacked the contract crashed with
      `ReferenceError: dirname is not defined` (repro: `cd scripts &&
      node run-tests.mjs`). Production CI never hit either shape only because
      it happens to run from the repo root where the first candidate hits.
- [x] **Restored and repaired.** Fixture reinstated from `9c19259^` (the
      `f55da46`-era 14-check version), then repaired for the scope contract:
      every synthetic repo layout now plants `.guardrails/` beside the root it
      claims (checks 2/4/5/8), so no check can pass vacuously on a missing
      contract. All scanners' `findScope`/`SKIP_DIRS` now resolve from the
      LAYOUT roots only (`projectRoot`/`devgateRoot`), never `process.cwd()`;
      `run-tests.mjs`'s `findUp` deleted outright.
- [x] **CI re-wired.** `ci.yml` regains an explicit
      `node tests/test_scanner_root_anchor.mjs` step (visible by name, same
      treatment as the Python suite) and the false "superseded" comment is
      corrected to say what the Python suite actually pins.
- [x] **The restored fixture did not kill the regression.** Run against the
      `cf3f6e4` cwd-walk-up scope lookup, all original 14 checks stayed green —
      case 6's foreign cwd carries no scope contract (a walk-up there throws
      for a different, visible reason) and case 7 spawns with `cwd == repo`,
      where cwd and layout agree. Added check 7b: `guardrails-scan` spawned
      from a parent whose `.guardrails/scope.json` skips `src/`; a walk-up
      reads the foreign contract, suppresses the trip file, and prints
      "pattern scan clean" for a tree it never scanned. Against the mutant 7b
      is the ONLY failure (exit 1, precisely that line); after revert 15/15
      green. Same lesson as the 2026-09-21 fresh-eyes round: a restored pin is
      a candidate pin until a mutant proves it.
- **Evidence (2026-09-26):** fixture 15/15 green standalone (14 restored +
  mutant-killing 7b); `run-tests.mjs`
  994 passed / 65 files from both repo root and `scripts/` cwd (the crash
  repro now completes); full gates green (pytest 994+5s, openspec 36/36
  --strict, all 8 mutation batteries, silent-success scan, regression_check
  hard-limit 0, `git diff --check`).
- **Follow-up owed:** none for the escape itself, but the deletion pattern — a
  test file vanishing under an unrelated message — is invisible to every gate
  except the one it deletes. The explicit CI step restores *run-visibility*
  (deleting the fixture next time turns the step red instead of silent); it is
  not a pin against untracked deletion, and no current gate claims otherwise.

## MEDIUM — same escape class in the Python scanners (found by the S1 audit, NOT the external audit)

- [x] **CLOSED (S8).** Three Python scanners resolved their root by marker
      walk-up from cwd — the identical defect fixed for the three Node scanners,
      and a direct violation of `root-anchor-01` and `root-anchor-03`, the
      requirements this branch itself authored: `regression_check.py`,
      `scene_inventory.py`, and `failure_registry_check.py`. All three now import
      one shared contract, `scripts/lib/project_root.py` (sibling of
      `project-root.mjs`), satisfying `root-anchor-03`'s single-implementation
      rule; each gained a module-level `PROJECT_ROOT` so the value is observable
      without running a scan.
      - **The third scanner was found by correcting a false claim in this very
        slice.** An earlier version of this note asserted
        `failure_registry_check.py` was "not in DevGate's own gate path" and
        deferred it alongside `game_regression.py`. That was **wrong**:
        `ci.yml:101` runs it on every push, so it is *more* gate-load-bearing
        than `scene_inventory.py` (which no gate invokes). Its `_find_project_root()`
        walked up from `Path.cwd()` for the first `.git`, and the value it
        returned selected which `.guardrails/failure-registry.jsonl` overlay the
        gate reads — a walk-up that lands above the checkout silently points the
        gate at the wrong consumer's registry. The fix is not scope creep: under
        this package's own stated rationale ("conforming them is completing this
        package's own contract") a gate-invoked `root-anchor-01` violation is
        squarely in scope, and the deferral existed only because the gate-path
        claim was false.
      - Escape reproduced first: from a markerless repo under a
        marker-bearing parent, all three resolved `PROJECT_ROOT` to the parent.
      - Pinned by `tests/test_python_root_anchor.py` (7 tests, each watched RED
        against the unfixed scanners): standalone-under-marked-parent, submodule
        → consumer, cwd-independence, mis-cased `.DevGate` is not the marker,
        multi-ancestor walk-up, single-shared-implementation, and the pure-
        function probe mirroring the Node check 9. All 7 now assert across
        **three** scanners via one subprocess probe, not two.
      - **Both walk-up spellings are pinned.** `regression_check.py`/
        `scene_inventory.py` named the old helper `find_project_root`;
        `failure_registry_check.py` named it `_find_project_root` (leading
        underscore). A test that grepped only the underscoreless form would pass
        on a `_find_project_root` that survived — the single-shared-implementation
        check now asserts both definitions are gone and the shared import present,
        for all three files.
      - Mutation battery on the third scanner: 4 mutants (walk-up-from-cwd on the
        consumed constant, always-parent, always-self/ignore-marker, case-insensitive
        shared module), each killed. Combined with the Node battery this closes the
        `root-anchor-01`/`-03` class for every scanner DevGate's CI actually runs.
      - **Scope note (corrected).** `game_regression.py` also defines a
        `find_project_root`, and it genuinely is **not** on DevGate's gate path,
        so it stays deferred — unlike `failure_registry_check.py`, deferring it
        rests on a checked claim. The check that actually holds: no `.github`
        workflow, no `scripts/*`, and no consumer template invokes
        `game_regression.py` (grep for it returns only comment prose in
        `regression_diff.py` and QA write-ups, never a `python3 … game_regression`
        call), and no gate script `import`s it as a module. It has its own test
        (`test_game_regression.py`, 6 passing), so it is exercised — just not on
        DevGate's *own* CI gate, only by consumers who opt into the game lane.
        `log_failure.py`'s `DEVGATE_ROOT` is a *package* location for its
        registry file, not a project root, so it is correctly not a second copy
        of the contract and `root-anchor-03` does not apply to it.
      - **A second self-correction, from the audit of this very delta.** The
        first version of this scope note cited `grep game_regression .github
        templates deploy.sh` as its proof. That recipe was itself a small false
        verification: there is no root-level `deploy.sh` (the real one is
        `scripts/deploy.sh`, which does not reference game_regression), so the
        `deploy.sh` term matched nothing and the "zero hits" was partly true by
        shell-expansion accident rather than by checking the right file. The
        conclusion survived (game_regression is genuinely off the gate) but the
        citation did not, so it was rewritten to name what was actually
        searched. A deferral justified by a command that would print the expected
        answer whether or not the file existed is the same failure class, one
        level down.
      - **PREVENT-024 observation (honest, not absorbed):** importing
        `project_root` trips that rule — its pattern
        `(import|from|...)\s+[a-z_]+_[a-z]+_[a-z]+` fires on any two-underscore
        module name and its "triple-underscored" message is mis-worded, so it is
        a false positive on a real local module. The three imports this slice adds
        (`regression_check.py`, `scene_inventory.py`, `failure_registry_check.py`)
        carry an inline `guardrails-allow PREVENT-024:` annotation naming the
        module, which is DevGate's documented mechanism and leaves the scan at
        zero new hits.
        Two *pre-existing* hits on `tests/test_hub_spec_coherence.py` and
        `tests/test_regression_check.py` are left untouched — this slice annotates
        what it introduced, not the whole rule. The rule's over-broad pattern is a
        separate cleanup.
- **Result:** `run-tests.mjs` 40 files / 608 passed (was 39/601); guardrails
  exits 0 with **zero new** warnings — all three scanner imports (and the test's
  own probe `import failure_registry_check`, which trips the same over-broad rule)
  carry `guardrails-allow` annotations, leaving only the two pre-existing hits;
  `regression_check.py --base origin/main` resolves the repo and runs clean;
  `failure_registry_check.py` (the ci.yml:101 invocation) still exits 0 on a clean
  checkout, i.e. the fix changed *which tree it may resolve to*, not its answer
  here — in DevGate's own checkout the layout contract and the old walk-up agree.
- **Two ledger self-corrections recorded (see `design.md`):** this slice
  initially shipped a false scope claim ("`failure_registry_check.py` is not in
  DevGate's own gate path"), which its own fresh-eyes audit did *not* catch —
  the audit's "no vacuous passes" verdict was about the *code* and was correct;
  the defect was in the prose. The catch came from re-verifying a claim before
  committing it. Then the *replacement* verification written for the
  `game_regression.py` deferral ("grep … deploy.sh returns zero hits") proved to
  be weak too — a nonexistent path that would have printed the same answer
  regardless — and was caught by the independent audit of the delta. Both are
  logged, not hidden, because the lesson generalizes: a deferral justified by an
  unverified claim, *or by a check that could not have failed*, is the same false
  closure shape this package exists to prevent, just relocated from a test
  assertion into a sentence.

## HIGH — containerized coherence path not rebuilt and re-pinned

- [ ] **OPEN — out of scope for this package.** The evaluator image must be
      rebuilt and its identity re-pinned before the coherence-service package is
      a safe unification baseline. This is a merge-gate item on that package
      (the trio: rebuild, re-pin, execute), not a spec-format defect. This branch
      makes no claim about it and does not mark it resolved.

## HIGH — coherence change delivered but not accepted (31 open items)

- [ ] **OPEN — separate lifecycle event.** Package acceptance is a docs/qa
      decision with its own record. What this branch changes is that the spec
      tree is now strict-green, which removes the format barrier that stood in
      front of that decision. It does not perform the acceptance.

## MEDIUM — AIGGP-02 overlap unreconciled

- [x] Produce the requirement matrix against the shipped
      `devgate-spec-coherence-service` ladder: duplicates (shipped strictly
      stronger in the adoption-ladder and promote/halt pairs; equal-or-stronger
      for evaluation), shipped-only supersets (`coh-pol-02/05/06/07`), and three
      novel draft items.
- [x] Dispose every novel item "not built (program not started)" — the AIGGP
      program has not begun, so no row may read as adopted.
- [x] Record precedence (shipped ladder wins), keep the deltas `ADDED`, add no
      `coh-*`-mirroring IDs, and carry a reconcile-at-archive item into that
      package's `tasks.md`.
- See `openspec/changes/aiggp-02-fleet-spec-coherence/reconciliation.md`.

## MEDIUM — README overstates readiness

- [x] Replace asserted readiness prose with a CI-checked status row that states
      what was actually verified and marks the container proof NOT_RUN.

## This package (S5): the negative control, the pin, and the README row

- [x] `scripts/specs-validate-negative-control.sh` — stages
      `tests/fixtures/malformed-spec/spec.md` (no `## Purpose`, no
      `## Requirements` umbrella, a level-2 `## Requirement:`) into a
      throwaway store, because the CLI resolves items by NAME, not by file
      path (a file-path argument yields "Unknown item", not a validation).
      Requires nonzero exit AND the validator's own words naming the Purpose
      defect. Nonzero exit alone is insufficient: an unknown item also exits 1,
      so a mis-staged probe would pass vacuously.
- [x] Mutation battery on the control, each killed by a named guard:
      M1 validator-downgraded-to-no-op → killed by the exit-status check;
      M3 mis-staged-probe (unknown item) → killed by the "Unknown item" guard —
      and this mutant is exactly what an exit-status-only control would have
      passed, which is why the content guards exist; M4 validator-crashes-
      for-unrelated-reason → killed by the must-name-the-Purpose-defect check.
- [x] **The control itself shipped CI-red, and the mutation battery missed it —
      found on the first hosted run after merge (main `f6bb49b`).** The battery
      tested the control's *logic* (does it refuse a bad spec) by running it on
      my machine, where a global `openspec` 1.13.0 sat on PATH. The control
      invoked the CLI as bare `npx openspec` from inside the throwaway probe
      directory; `npx` resolves against the *cwd's* `node_modules`, and the probe
      dir has none, so on a clean runner the command dies with npm's "could not
      determine executable to run" — a nonzero exit that names no defect, caught
      by the must-name-the-Purpose guard as the designed failure-closed. Local
      green because the global install answered the name. This is the audit's
      central defect one level up again: **a control whose green depends on the
      machine it runs on is not a control.** Fixed by resolving the CLI to the
      exact binary the hard gate above it resolves to —
      `$repo_root/node_modules/.bin/openspec` — with a loud MISCONFIGURED exit
      when it is absent, so the control can only pass by exercising the pinned
      CLI, never a PATH accident. Verified under a faithful CI-layout mirror
      (global openspec off PATH, repo-local install present): passes.
      **How to run it locally** (the repo has no root `package.json`, so a plain
      install walks up to the parent dir): `npm install --no-save
      --no-audit --no-fund @fission-ai/openspec@1.13.0 --prefix .` — then both
      `npx openspec validate --all --strict` and this control resolve the repo
      copy, exactly as CI does.
      - **Root cause of the invisibility, recorded because it is a process gap,
        not just a bug:** ci.yml triggers on `push: branches: [main]` and
        `pull_request`, and we open no PRs ("this is our repo"). The audit branch
        therefore **never ran hosted CI at all** — every green on it was
        local-only. The "32/32, negative control exit 0" ledger entries were
        true statements about my machine, not about the gate. The lesson generalizes
        the package's own thesis from *code* to *provenance*: a check that has
        never run where it is claimed to run has proven nothing about that place.
- [x] Pin `@fission-ai/openspec@1.13.0` in ci.yml (was unpinned npx — the gate
      moved under the tree whenever upstream published). Pinned to the version
      the 32/32 result was verified with, deliberately not the latest (1.13.1
      exists); the pin comment says to re-run the negative control on bump.
- [x] ci.yml tests job: a non-vacuity step that captures the runner's output
      and asserts the discovered-file count is ≥ 1, so a regression that turns
      discovery back into a silent zero has to beat a number, not just print
      less.
- [x] README: "What is verified, and where" — a CI-checked table naming the
      mechanism for each claim (strict validate, negative control, runner
      discovery count, root-anchor fixture) with the container proof marked
      **NOT RUN**, and no hardcoded item total. (The NOT RUN marking was itself
      an unverified over-correction — the S7-audit bullet at the end of this
      ledger records the hosted logs disproving it.)


## Coverage honesty (S6)

- [x] `spec-fmt-04` was marked in a `.sh` file, but `spec_traceability.py`'s
      `SCAN_EXTS` was `{.rs,.py,.mjs,.js,.ts}` — shell scripts were never
      scanned, so the marker was invisible and the requirement read UNCOVERED
      while the source looked asserted. Fixed by adding `.sh`, pinned by
      `test_shell_script_marker_counts_as_coverage` (watched RED first:
      "router-req-01: UNCOVERED" for a `.sh`-marked requirement). Coverage
      68 → 69.
- [x] `spec-fmt-01/02/03` are left advisory-uncovered **on purpose**, not by
      omission: they describe properties of the spec tree whose enforcing
      mechanism is the validator itself, not a repository file, so a marker
      would have to point at an unrelated line to move a number — manufactured
      coverage, which `spec-fmt-03` forbids. Rationale recorded in `design.md`.
- [x] Frontmatter/plan text citing "31/31" corrected where it outlived those
      commits (the live count is 32; the ledger says not to hardcode it).

## S7 verification, and an audit that did not report

- [x] Full gate mirror run on the final tree: `run-tests.mjs` 601 passed / 39
      files; `test_scanner_root_anchor.mjs` 12/12 green; `openspec validate --all
      --strict` 32/32 exit 0; negative control exit 0; `pytest tests/` 601 passed;
      traceability exit 0 (69/107); `git diff --check` clean; `guardrails-scan`
      clean; `regression_check --all` 0 over hard limit (6 pre-existing soft
      warnings, none in files this branch touched).
- [x] Mutation battery re-run on the committed tree: 7 mutants, **zero
      survivors**. Two additional mutants beyond the original battery also died
      (double-hop `.devgate` parent, always-self submodule branch).
- [x] Negative control attacked three ways and fails closed each time: fixture
      silently replaced with a *valid* spec (control FAILS — the property that
      matters most), CLI missing (exit 127 caught as misconfiguration), fixture
      deleted (caught as misconfiguration).
- [x] Resolved the earlier audit's vacuity warning about the semantic lane. It
      held only under a *parser-present* environment; the new foreign-cwd check
      asserts on the counted-file number rather than the SKIPPED line, so
      `cwdRoot` is still killed with `typescript` installed. Verified both
      conditions — parser present and `node_modules` absent (the real CI
      condition, since the tests job installs no typescript).
- [x] Stability: fixture green on 3 consecutive runs; runner count stable at
      601/39 across runs.
- [x] **First independent audit DID NOT REPORT** (2026-09-21). An agent was
      dispatched to audit sections A–E of the final tree; it went idle without
      delivering findings and three requests for its report went unanswered.
      **Recorded as an unfinished audit, not a clean one.** A replacement was
      dispatched rather than treating silence as a pass.
- [x] **Second independent audit COMPLETED** (2026-09-21, `s7-audit-retry`) —
      5 claims confirmed against measured output, 1 BLOCKING, 2 minor. Verdict:
      the "no false closure" thesis substantially upheld. All three findings
      dispositioned in `design.md`; summary:
  - [x] BLOCKING ("walk-up mutant survives") — **half right**. The mutant was a
        no-op on every real layout (its first probe returns `devgateRoot`, the
        same answer as the contract), so the audit's *defect* claim is refused.
        Its *gap* claim stands: no check pinned the contract's pure-function
        property. Check 9 added (watched RED against a real filesystem walk-up,
        then GREEN), battery now **8 mutants, zero survivors**.
  - [x] MINOR (stale traceability count) — correct and understated: the line
        said 65/100, main measured 68/107. Ratio dropped, invariant named.
  - [x] MINOR (container build row never fires) — **accepted, then disproven by
        the hosted logs.** The claim ("ubuntu-latest has no podman, the rows
        never evaluate") came from me and was echoed by the auditor; I recorded
        it as checked, but the branch never produced a hosted run, so nobody
        could have checked it. Runs 35675783843 / 35684356819 after merge:
        podman **is** present, the build executes (`STEP 1/7`), prints
        `schemas OK in image`, and yields the same digest across commits — the
        opposite of "never fires". Disposition reversed in README and
        `design.md`; the SKIPPED guards stay as future-proofing. Two voices
        repeating one untested premise is agreement, not corroboration.

## Cross-package note (no false closure)

- [x] Correct the working note that claimed AIGGP-01 targeted Jinja/3D-adapter
      codebases. `grep -in 'jinja\|adapter'` over its specs returns nothing: its
      "no vacuous gates" and "correct audit subject" requirements target
      DevGate's own shipped scanners, overlapping this audit's findings.
      Disposition: not built (program not started) — this branch closes the
      audit findings directly; AIGGP-01's requirements are not accepted or
      rejected here.
- [x] Do not mark AIGGP-00/-09/-10 closed. They depend on the AIGGP program.
      This ledger tracks the *drift audit's* findings, not package acceptance.

## Closed note — the permanently-empty shape in `guardrails-scan` scoping (resolved 2026-09-26)

- [x] `semantic-scan`'s walk gained `.mjs`/`.cjs` on 2026-09-26 (closing the
      coherence package's S0 carry-forward), but `guardrails-scan.mjs`'s
      `SOURCE_EXTENSIONS` still omitted them — and this repo's first-party JS
      is 100% `.mjs`. The pattern-scan rules scoped by file_glob (`*.js`/`*.ts`
      family globs) therefore evaluated none of this repo's own modules. Not a
      root escape (the root is correct and pinned) — the *extension scoping*
      was the hollow part. Decision owed: add `.mjs`/`.cjs` to
      `SOURCE_EXTENSIONS` and re-baseline any new rule hits, or record the
      rules as bundle-only (meant for consumers, not DevGate-itself) so the
      emptiness is declared, not discovered. Left open deliberately: it changes
      what a shipped gate evaluates and deserves its own evidence pass, not a
      ride-along commit.
      **Disposition: scoped IN, evidence pass first.** Probe (fix applied to a
      working copy, full repo scan): **zero new findings attributable to
      `.mjs`/`.cjs`** — all 9 warnings were pre-existing `.py` PREVENT-024
      hits, exit 0 — so no re-baseline was owed. Pin: section 15 of
      `tests/test_guardrails_scan.mjs` (violating `.mjs`/`.cjs` files in a
      synthetic project reported, clean `.mjs` not), verified RED before the
      fix and green after. One consequence the probe surfaced that section 15
      does not cover: with `.mjs` files now walked, `isCommentLine`'s extension list
      also gained `.mjs`/`.cjs`, mirroring the Zig precedent — without it,
      `scan_comments: true` rules (severity warning or error; this repo's
      PREVENT-020 is severity `info` and never runs here, but a consumer's
      retuned copy would) would treat a comment-only `// TODO` line in any
      walked `.mjs` file as code. Caveat recorded honestly:
      **no bundled rule yet carries a `*.mjs` glob**, so real bundled-rule
      coverage of the walked files still awaits rule retuning — the walk is
      fixed (files are now eligible for any glob that names them), the
      fixture proves eligibility with a custom rule, and the repo no longer
      prints "clean" on files it never read.

## Post-close hygiene (queued from earlier-window audits, worked 2026-09-26)

These are not external-audit findings; they are self-found defects that
accumulated a queue with no written home. Each gets evidence-pass → fix →
pin, in push order.

- [x] **`/health` overcounts revoked runners** (hub/server.py). The endpoint
      reported `len(registry.runners())`; `revoke()` keeps the row with
      `enrolled: False` (audit trail), and the monitor filters that field every
      cycle — so the health page advertised monitoring the hub would never
      perform, exactly during an outage triage when an operator counts
      reporters. Fix: count the live set (`enrolled` filter, same law as the
      monitor), row retention unchanged. Pin (RED first):
      `tests/test_hub_enroll_heartbeat.py::test_health_registered_runners_excludes_revoked`
      — enroll → count 1 → revoke → count 0, plus the row-still-present
      assertion so the fix cannot "pass" by deleting audit state.
- [x] **A bulk edit can corrupt executable STRING payloads, not just code —
      `bash -n` guard added.** When `88b74e9` (explicit-UTF-8 sweep, run on a
      Windows box where the affected suites cannot execute) pasted
      `, encoding="utf-8")` into two bash `case` arms inside `write_text`
      literals (`tests/fixtures/runner_spoke.py` podman stub, `tests/`
      `test_coherence_local_wrapper.py` fake-python relay), six tests broke by
      SIDE EFFECT — a never-matching case arm looks like a wrong answer, not
      like a syntax error. Repaired both literals; added the class guard:
      `test_generated_shell_stubs_are_syntactically_valid_bash` AST-extracts
      every maximal bash-shebang string literal under `tests/` (12 found,
      floor asserted so the extractor cannot silently stop matching) and
      lints each with `bash -n`. Mutation M5 in
      `tests/mutation_battery_runbook_claims.py` reintroduces the corruption
      verbatim and must be caught by the lint test — 5/5 killed, control
      survived; suite floor entry `test_runbook_claims: 4` (90% of 5,
      targeted). Honest boundary: the guard covers bash bodies only — a
      corrupted python/heredoc payload is still side-effect-detected.
- [x] **Registry accepts duplicate spellings of one host — enrollment now
      refuses whitespace-wrapped names.** Evidence pass (measured, not reasoned):
      enrolling `ucs03`, `UCS03`, and `"ucs03 "` through the live `Registry`
      produced THREE rows, all `enrolled: True`, all counted by `/health` —
      `find_runner` and the name half of `verify_heartbeat_token` match
      byte-exactly and nothing normalizes on any path. The hub-outage runbook's
      "the hub answers 409 for an already-enrolled name" claim is true only for
      the exact string; the duplicate window it warns operators about was open
      to anything a copy-paste smuggled. Disposition by vector: **whitespace**
      → refused at enrollment with 400 (the spoke freezes `RUNNER_NAME=`
      verbatim into its env file, so a hub-side trim would store a name the
      helper never heartbeats against — 401 forever; bad names must die where
      they are cheap to fix); **case** → deliberately untouched, the name is
      credential-bearing (B's token verifies against `"UCS03"`, not `"ucs03"`),
      a fold would silently merge hosts an operator named apart; **duplicate
      labels inside one row** → inert, the only reader is a set comprehension
      (`monitor.py` `registered_labels`), not a defect. Guard:
      `test_enroll_rejects_a_whitespace_wrapped_name` (400, nothing persisted,
      the one-time token survives the refusal — the clean spelling enrolls
      with the SAME token) and `test_enroll_rejects_a_non_string_name_400_not_500`
      (the `.strip()` call the guard adds would otherwise traceback on a JSON
      number; verified load-bearing — deleting the isinstance check kills that
      test, deleting the whitespace check kills the other). The refusal sits
      before the 409 probe and before token consumption. Suite floor
      `test_hub_enroll_heartbeat: 7→9` (90% of 11, targeted). Honest boundary:
      this closes the MISTAKE window; an operator deliberately enrolling one
      host twice under two names remains possible by design — identity is the
      name, and the fleet has real multi-name hosts (coh-int-07).
- [x] **`"$NEW"` enrollment token path — it was not hypothetical: the LIVE
      hub carried it.** Evidence pass on dell-u2 (measured 2026-09-26, shape
      only reported): the running hub's `/data/runners.json` had 3 enrollment
      tokens, one of them literally `$NEW` — a shell variable pasted into
      `HUB_ENROLLMENT_TOKENS` with single quotes somewhere in the operator's
      minting path, loaded by `hub/main.py`'s startup loop, which accepted ANY
      non-empty string as a credential. A placeholder in the enrollment list
      is a predictable credential: anyone who has read the runbook's `<tok>`
      shape could enroll a rogue runner. The value was never usable (no
      enrollment against it appeared in the registry's runners — and one-time
      consumption would have hidden it; the audit reports what remains
      observable, not an absence-proof). Fix: the load moved out of `main()`
      into `load_enrollment_tokens(registry, env_value)` (env value explicit —
      testable without a subprocess), gated on a mint-shape regex
      (`[A-Za-z0-9_-]{16,}` — both mint paths, `secrets.token_urlsafe` and
      operator hex, match, so no real token can be rejected by alphabet);
      refusals are loud (stderr) but VALUE-FREE (a near-miss may itself be a
      secret). Registry gained `prune_enrollment_tokens(keep)` so a restart
      HEALS a placeholder an older loader persisted — the env-path refusal
      alone would leave the live `$NEW` riding the volume forever. The rule's
      home is documented in the hub runbook with a concrete mint command, so
      the refusal never surprises an operator. Pins: three tests — placeholder
      refused (valid sibling in the same env still loads), valid shapes loaded
      verbatim (control: the guard cannot eat real tokens), stored-placeholder
      pruned on restart; mutation probes verified both guards are load-bearing
      (accept-all regex kills 2, no-op prune kills 1). Suite floor
      `test_hub_enroll_heartbeat: 9→12` (90% of 14, targeted). Follow-up
      owner-side: restart the hub once to prune the live `$NEW` (and the
      standing token-rotation question covers it).
