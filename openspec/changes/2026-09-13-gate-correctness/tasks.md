# Tasks: gate correctness repairs (dependency-ordered)

## Sprint 1 — shared root contract (unblocks C2, C3)
- [ ] 1.1 Extract project-root resolution to match guardrails-scan.mjs semantics; port semantic-scan.mjs (D1)
- [ ] 1.2 Port run-tests.mjs to the same contract (D1)
- [ ] 1.3 Fixture test: standalone checkout → semantic scan and run-tests do their work and exit 0 (D7)

## Sprint 2 — test runner truth (C3, C4)
- [ ] 2.1 Whole-tree test discovery honoring SKIP_DIRS + .guardrailsignore (D3)
- [ ] 2.2 `cargo test --test <stem>` + 0-test detection = file failure (D3)
- [ ] 2.3 Fixtures: tests-in-pkg/ discovered; Rust fixture with 0-match filter fails (D7)

## Sprint 3 — regression --all semantics (C5)
- [ ] 3.1 Pattern arm scans tag-window added lines under --all (D4)
- [ ] 3.2 Add `--base <ref>` for per-PR scoping (D4)
- [ ] 3.3 Update README CI section + tool warning text + drift-scan header to the true contract (D4)
- [ ] 3.4 Fixture: committed critical violation visible to --all in clean tree (D7)

## Sprint 4 — scanners (C1, H4)
- [ ] 4.1 scene_inventory.py: drop ET.parse, normalize node paths, keep orphan failures (D2)
- [ ] 4.2 Fixtures: minimal valid scene passes; nested button with handler passes; true orphan fails (D2, D7)
- [ ] 4.3 blankTestModulesRust: count braces from attribute line (D5)
- [ ] 4.4 Fixtures: single-line and multiline cfg(test) forms both exempt (D5, D7)

## Sprint 5 — file-size gate (H5)
- [ ] 5.1 Add tests/test to SOURCE_DIRS (D6)
- [ ] 5.2 Fix test-file classification (real basename match) (D6)
- [ ] 5.3 Fixtures: 550-line tests/test_big.py → TEST_HARD warning class, not SRC_HARD error (D6, D7)

## Sprint 6 — hygiene
- [ ] 6.1 Remove dead isCommentLine branch and no-op test-scope-inversion block in guardrails-scan.mjs (L1)
- [ ] 6.2 Remove unused mkdtemp isolation dir in run-tests.mjs (L7)
- [ ] 6.3 Full suite green; CHANGELOG entry; version bump per release gate
