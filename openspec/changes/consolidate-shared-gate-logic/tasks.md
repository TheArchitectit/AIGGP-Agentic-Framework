# Tasks: consolidate-shared-gate-logic

- [x] 1 Create `scripts/gate_common.py`: root detection (guardrails-scan
      contract), `read_jsonl_registry` (error-reporting semantics), one
      allow-annotation matcher, one glob engine (+globstar), SKIP_DIRS
      constant, NOTHING_SCANNED helper. Unit tests for each.
      (`tests/test_gate_common.py`, 19 tests.)
- [x] 2 Migrate Python gates one per commit (regression_check,
      regression_diff, failure_registry_check, game_regression,
      scene_inventory, findings_to_spec, spec_traceability, log_failure);
      full test suite green after each.
      Migrated: regression_diff, game_regression, failure_registry_check,
      regression_sizes, regression_audit (+ deploy.sh). The remaining names
      had no local copy of these primitives to delete — their root contract
      already lived in `scripts/lib/project_root.py`.
- [x] 3 Create `scripts/lib/gate_common.mjs` (root detection, walk with
      EACCES/symlink handling, glob, allow-annotation); migrate
      guardrails-scan, semantic-scan, run-tests.
      (`tests/test_gate_common.mjs`, 16 checks. Fixtures stage the lib next
      to project-root.mjs — a bare scanner copy dies at import.)
- [x] 4 Parity matrix fixtures: submodule layout, standalone clone, nested
      package, markerless parent; annotation forms (`// id: reason`,
      `# id: reason`, bare, prev-line); glob shapes (`**`, classes, drive
      letters); run against both implementations, assert identical verdicts.
      (`tests/test_gate_common_parity.py` — one case table, Python + a Node
      subprocess, identical verdicts. Drive-letter globs are Windows-only and
      not exercised on this host; fnmatch vs the JS translator agree on `/`.)
- [x] 5 Reconcile SKIP_DIRS into one canonical list; document additions in
      gate_common docstring (per-name rationale).
      (`.guardrails/scope.json` is the single source — `worktrees` added
      2026-09-28 with its rationale; `file_size_skip_parts` deleted.)
- [x] 6 Unify package-manager detection (single table incl. go/godot) shared
      by deploy.sh and regression_audit.
- [x] 7 Delete dead local copies; grep-verify no duplicate implementations
      remain (`grep -rn "findProjectRoot\|find_project_root\|line_has_allow\|
      globMatch\|glob_matches"` count: exactly the shared libs).
      Verified 2026-09-28. Only remaining `def find_project_root` is
      game_regression's named alias to `gate_common.project_root` (callers
      and tests import it under that name) — not a second implementation.
- [x] 8 Tightening task (explicit): reason-required allow annotations
      everywhere + docs note; fixtures updated where bare-colon annotations
      existed in tests.
      (`gate_common.line_has_allow` / `lineHasAllow` reject a bare colon;
      README names the contract under the Pattern Scanner annotation form.)
- [x] 9 Coverage: silent-success-scan.sh joins the overlay contract
      (gate_overlay merge + .guardrailsignore), closing QA M2.
      Merge was already in place; `.guardrailsignore` now honored via
      `gate_common.load_ignore_patterns` / `is_ignored` (the loader also
      left game_regression for the shared home). New fixture:
      `test_guardrailsignore_scopes_the_walk`.
