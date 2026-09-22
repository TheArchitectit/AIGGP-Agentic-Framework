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
      discovery count, root-anchor fixture) with the container proof explicitly
      **NOT RUN**, and no hardcoded item total.


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
  - [x] MINOR (container build row never fires) — correct. Both container rows
        now state that hosted CI evaluates neither; the table preamble no
        longer claims every row is CI-checked.

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
