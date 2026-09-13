# Design: gate correctness repairs

## Locked decisions

D1. **One root-resolution contract, one implementation.** Extract the
    guardrails-scan.mjs anchor rule — project root = parent of `.devgate/`
    when the script lives in one, else the script's own repo — into the
    shared position for semantic-scan.mjs and run-tests.mjs. No walking up
    from the script's parent; a standalone checkout is its own project.
    This is the fix C2/C3 share; it also deletes a whole class of
    "escaped into a sibling directory" bugs the current comments describe.

D2. **scene_inventory.py: delete the ET.parse dead end, fix path comparison.**
    Parse `.tscn` with the existing regex approach only; normalize connection
    `from=` node paths to bare node names before the orphan comparison; keep
    exit 1 for genuine orphans. Add the audit's minimal HUD.tscn plus a
    nested-button scene as fixtures.

D3. **run-tests.mjs: whole-tree discovery + correct cargo invocation.**
    Discover test files across the project root (respecting SKIP_DIRS and
    .guardrailsignore) instead of four hardcoded directories. Run Rust
    integration files with `cargo test --test <stem>`; assert the cargo
    output's "running N tests" is N>0 and fail the file when it is 0 —
    a 0-test run is a silent success, per the framework's own doctrine.

D4. **regression_check.py: make --all mean the tag window for every arm.**
    Under `--all`, the pattern-rule arm scans the added lines of
    `tag...HEAD` (the same window the registry arm already uses) instead of
    the working-tree diff. Docs (README CI section, tool warning text,
    drift-scan.yml header) are updated to say exactly this. A separate
    `--base <ref>` flag is added for per-PR scoping — the README currently
    documents its absence as a known limitation.

D5. **Rust test blanking: count braces from the attribute line.**
    blankTestModulesRust starts depth counting on the `#[cfg(test)]` line
    itself, so single-line and multiline module forms behave identically;
    add fixture coverage for both forms and for `#[cfg(test)]\nmod tests {`.

D6. **File-size gate: scan tests/, fix the literal glob.**
    Add `tests`/`test` to SOURCE_DIRS auto-detection; replace the
    `"test_*.py"` endswith entry with a real basename match
    (`name.startswith("test_") and name.endswith(".py")`), keeping `_test.py`
    and the JS/Rust/Go patterns. TEST_HARD applies to test files only.

D7. **Every fix lands with a fixture test that failed before it.**
    The suite grows fixture projects under tests/fixtures/ exercising:
    standalone semantic scan, standalone run-tests, cargo filter>0,
    --all tag-window pattern hit, single-line cfg(test), tests/ sizing.
    Existing 44 tests must stay green.

## Open questions

Q1. Should `--all` keep failing loud (RuntimeError) when the tag window
    can't be diffed, or degrade to a warning in scheduled drift runs? Audit
    recommendation: keep failing loud — the drift template fix (separate
    change) supplies fetch-depth, so the loud path should stay armed.

Q2. run-tests.mjs discovery over the whole tree will pick up consumer
    fixture directories with intentional failing tests. Respect
    `.guardrailsignore` (D3) and add a `DEVGATE_TEST_IGNORE` env list, or
    keep a allowlist of directory names? Recommendation: ignore file + env,
    matching the scanner contract.

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Whole-tree test discovery surfaces long-dormant failing tests in consumers | Medium | Ship behind the same run; document in CHANGELOG; `.guardrailsignore` escape hatch (D3) |
| `--all` semantics change turns scheduled drift runs red on repos with legacy violations | Medium | That is the gate working as documented; release-note it prominently and pair with the drift template fix |
| Brace counting on the attribute line mis-blanks exotic Rust (`#[cfg(all(test, feature="x"))]`) | Low | Treat any `#[cfg(…test…)]` attribute line identically; fixture for the compound form |
| Scene regex parser misses Godot 4 multiline node attributes | Medium | Fixtures from a real Godot 4 project (Sword of Hope) before merge |
