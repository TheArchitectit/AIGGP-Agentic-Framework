# Tasks

## 1. Traceability denominator (rule-denominator-01)

- [x] 1.1 Count requirement statements in the numerator, the same unit the
      denominator counts; state the reuse count in the summary line.
- [x] 1.2 Keep blocking evaluation per statement, dedupe only the failure list.
- [x] 1.3 Negative controls: a delta restating a covered sealed id reports 2/2
      with no advisory line (`test_id_reused_by_a_delta_is_not_phantom_uncovered`);
      the same shape uncovered still exits 1
      (`test_reused_id_still_blocks_when_the_marker_is_absent`). Measured
      against NeonDash's live tree before/after: `49/51 covered` + `2
      uncovered` became `51/51 covered (49 unique id(s), 2 stated by more than
      one spec)` with `--report` showing 0 UNCOVERED in both runs.

## 2. Registry scope line (gate-scope-line-01)

- [x] 2.1 `check()` records per-source parsed counts, merged count and error
      warning counts into a caller-supplied scope dict, including on its early
      returns.
- [x] 2.2 `main()` prints `failure-registry: scope: N merged entries [source n,
      ...]; X error(s), Y warning(s)` on every path, before the findings.
- [x] 2.3 Tests: clean run still evidences scope; a missing named registry
      prints the line with the reason; the merged breakdown names both sources
      through the module API (the submodule layout needs a tree, not an env
      var — root-anchor-01 resolves `.devgate/` from the script's own path).

## 3. Declared anchors (gate-anchor-scope-01)

- [x] 3.1 `anchor_dirs(root)` reads `inventory_dirs` from the existing
      `.guardrails/scope.json`; absent file or absent key keeps the built-in
      game defaults for every current repo.
- [x] 3.2 Refuse a malformed, empty or escaping declaration (coh-sec-01
      containment, same rule as the size gate's walk roots) — exit 2, never a
      quiet fall back to the defaults.
- [x] 3.3 Report the anchor set in use: a table line naming the source and the
      dirs, and the SGA-04 "unknown scope" refusal naming which set produced
      the empty.
- [x] 3.4 Tests for all four behaviours, including the JSONDecodeError branch
      naming the file (json's own message does not).

## 4. Consumer side (NeonDash, not this repo)

- [ ] 4.1 Bump `.devgate` to the release carrying these three fixes.
- [ ] 4.2 Replace the yaml registry line-count guard with a requirement on the
      tool's own scope line; raise the traceability ratchet floor to the new
      statement-level count in the same commit, or the ratchet reads a
      denominator change as a regression.
- [ ] 4.3 Declare `"inventory_dirs": ["scripts", "tools"]` in
      `.guardrails/openspec/scope.json` — note NeonDash's scope file lives
      under `openspec/` while the contract lives at
      `.guardrails/scope.json`; if the symlinked layout disagrees with the
      contract path, that is this task's finding, not a footnote.
