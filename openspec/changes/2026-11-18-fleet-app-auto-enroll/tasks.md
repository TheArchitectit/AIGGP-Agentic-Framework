# Tasks: 2026-11-18-fleet-app-auto-enroll

Evidence: `tests/test_fleet_app_enroll.py`, 15 tests. Three sealing tests need
`PyNaCl==1.5.0`; they skip, not fail, on an interpreter without it. Every
ticked box below names the test that proves it.

- [x] Paginate `GET /installation/repositories?per_page=100` with Link headers
  and reconcile every repository the installation reports.
  - `test_installation_repositories_paginate_with_link_headers`
- [x] Skip archived repositories without any actions call, name them
  `skipped-archived`, and count them in the report.
  - `test_archived_repositories_are_skipped_and_counted`
- [x] Create the App ID variable when absent, update it when the value differs,
  and leave it alone when equal.
  - `test_variable_is_created_updated_or_left_alone`
- [x] Create the private-key secret only when metadata reports it absent; seal
  the PEM with the repository public key in memory.
  - `test_secret_is_created_only_when_absent_and_is_sealed`
- [x] Never overwrite an existing secret by default; re-seal only under
  `--rotate`.
  - `test_rotate_reseals_an_existing_secret`
- [x] Make `--dry-run` perform zero writes and report planned actions.
  - `test_dry_run_performs_no_writes`
- [x] Continue past a per-repository error, report it on that repository, and
  exit nonzero at the end.
  - `test_one_repo_error_does_not_stop_the_others_and_exits_nonzero`
- [x] Keep the PEM and token out of stdout, stderr, and the JSON report.
  - `test_credentials_never_reach_stdout_or_the_report`
- [x] Keep the report machine-readable on stdout when no report path is given.
  - `test_report_is_pure_json_on_stdout_when_no_path_is_given`
- [x] Reject a missing token with exit 2 before making any request.
  - `test_missing_token_is_a_usage_error_and_writes_nothing`
- [x] Limit a `--repo` run to the named repository and skip the installation
  listing.
  - `test_repo_flag_limits_scope_and_skips_the_listing`
- [x] Count repositories outside `FLEET_OWNER` and do not touch them.
  - `test_repositories_outside_the_owner_scope_are_counted_not_touched`
- [x] Declare only `schedule` and `workflow_dispatch`; default a manual
  dispatch to dry-run.
  - `test_workflow_has_no_pull_request_trigger_and_a_safe_dispatch_default`
- [x] Run on `devgate` with a 45-minute timeout, an off-minute nightly cron,
  and concurrency.
  - `test_workflow_runs_nightly_on_devgate_off_the_hour`
- [x] Keep the private key in step env (never argv) and pin the App-token and
  artifact actions, plus PyNaCl.
  - `test_workflow_keeps_the_private_key_in_env_and_pins_actions`
- [ ] Live apply against installation 101651861, confirming the installation
  can list repositories and write the variable and secret. The owner runs
  this; no live GitHub call was made by this package.
- [ ] `docs/GITHUB-APP-TOKEN.md` describes enrollment, comparison limits,
  timing, flags, and scope. Written, but no test asserts the prose.

## Verification

- `python3 -m pytest tests/test_fleet_app_enroll.py -q` — 15 passed with
  PyNaCl 1.5.0; 12 passed and 3 skipped without it.
- `python3 -m pytest tests/test_spec_fleet_classify.py tests/test_spec_fleet_walk.py tests/test_secret_scan_fleet.py -q`
  — 43 passed.
- `openspec validate 2026-11-18-fleet-app-auto-enroll --strict` — passed
  (openspec 1.14.3).
- `openspec validate --all --strict` — 50 passed, 0 failed.
