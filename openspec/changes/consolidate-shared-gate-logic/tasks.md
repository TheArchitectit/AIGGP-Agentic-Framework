# Tasks: consolidate-shared-gate-logic

- [ ] 1 Create `scripts/gate_common.py`: root detection (guardrails-scan
      contract), `read_jsonl_registry` (error-reporting semantics), one
      allow-annotation matcher, one glob engine (+globstar), SKIP_DIRS
      constant, NOTHING_SCANNED helper. Unit tests for each.
- [ ] 2 Migrate Python gates one per commit (regression_check,
      regression_diff, failure_registry_check, game_regression,
      scene_inventory, findings_to_spec, spec_traceability, log_failure);
      full test suite green after each.
- [ ] 3 Create `scripts/lib/gate_common.mjs` (root detection, walk with
      EACCES/symlink handling, glob, allow-annotation); migrate
      guardrails-scan, semantic-scan, run-tests.
- [ ] 4 Parity matrix fixtures: submodule layout, standalone clone, nested
      package, markerless parent; annotation forms (`// id: reason`,
      `# id: reason`, bare, prev-line); glob shapes (`**`, classes, drive
      letters); run against both implementations, assert identical verdicts.
- [ ] 5 Reconcile SKIP_DIRS into one canonical list; document additions in
      gate_common docstring (per-name rationale).
- [ ] 6 Unify package-manager detection (single table incl. go/godot) shared
      by deploy.sh and regression_audit.
- [ ] 7 Delete dead local copies; grep-verify no duplicate implementations
      remain (`grep -rn "findProjectRoot\|find_project_root\|line_has_allow\|
      globMatch\|glob_matches"` count: exactly the shared libs).
- [ ] 8 Tightening task (explicit): reason-required allow annotations
      everywhere + docs note; fixtures updated where bare-colon annotations
      existed in tests.
- [ ] 9 Coverage: silent-success-scan.sh joins the overlay contract
      (gate_overlay merge + .guardrailsignore), closing QA M2.
