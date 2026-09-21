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
  Traceability unchanged at 65/100 (advisory, exit 0).
  **The total is deliberately not quoted as a fixed number.** `--all` counts
  *discovered* items, so this package's own addition moved it 31 → 32; any
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

- [ ] **OPEN — new scope, not silently absorbed.** `scripts/regression_check.py:86`
      and `scripts/scene_inventory.py:19` still resolve their root by marker
      walk-up from cwd — the identical defect this branch fixed for the three
      Node scanners. Verified: `regression_check.py` run from a markerless repo
      adopts the parent's `package.json` as `PROJECT_ROOT`. Both run in the
      consumer CI template (`drift-scan.yml:99`), and `regression_check.py` runs
      in DevGate's own `self-gates` job. **Deliberately left open**: the
      external audit did not raise it, it is a different language surface, and
      the fix belongs with the same fixture pattern this branch established.
      Recorded here so it is visible rather than discovered later.

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
