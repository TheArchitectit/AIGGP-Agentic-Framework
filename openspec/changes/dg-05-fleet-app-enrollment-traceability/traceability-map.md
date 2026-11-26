# Fleet App enrollment scenario-to-evidence map

Scope: canonical `openspec/specs/fleet-app-enrollment/spec.md`, IDs
`fleet-app-01` through `fleet-app-09`. The code and workflow paths below are
the enforcing sites. The named tests exercise an in-memory `FakeGitHub` and
temporary report paths; they are hermetic evidence only. CI invocation is
`.github/workflows/ci.yml:66,86-87` (`pytest`, `cryptography`, and PyNaCl are
installed, then `python3 -m pytest tests/ -v`).

| ID / canonical scenario | Enforcing site | Test and asserted outcome | Evidence class and limits |
|---|---|---|---|
| `fleet-app-01` pagination; reject a next link outside HTTPS `api.github.com` | `scripts/fleet-app-enroll.py:105-108` `_require_https`; `:168-179` `next_link`; `:207-222` `list_repositories`; `:130-159` API request boundary | `tests/test_fleet_app_enroll.py:196-211` `test_installation_repositories_paginate_with_link_headers`: two listing calls, three repos processed, each repo touched. `:214-234` `test_next_link_to_untrusted_host_fails_closed`: nonzero result, no repos reconciled, unsafe host reported, only one listing request. | Behavioral, hermetic. No live installation listing. |
| `fleet-app-02` archived repository is visibly skipped | `scripts/fleet-app-enroll.py:295-318` `reconcile_repo` returns before variable/secret calls | `tests/test_fleet_app_enroll.py:237-250` `test_archived_repositories_are_skipped_and_counted`: zero calls for archived repo, action `skipped-archived`, count 1, exit 0. | Behavioral, hermetic. |
| `fleet-app-03` absent/wrong/matching variable values | `scripts/fleet-app-enroll.py:234-257` `_ensure_variable` selects POST, PATCH, or no write | `tests/test_fleet_app_enroll.py:252-273` `test_variable_is_created_updated_or_left_alone`: final values, expected POST/PATCH, no write for match, and all three action labels. | Behavioral, hermetic. |
| `fleet-app-04` existing secret is retained; explicit rotation seals and PUTs | `scripts/fleet-app-enroll.py:258-273` `_put_secret`; `:274-293` `_ensure_secret` | `tests/test_fleet_app_enroll.py:276-299` `test_secret_is_created_only_when_absent_and_is_sealed`: only absent secret is PUT; ciphertext decrypts to the fixture PEM and is not plaintext; present secret does not fetch a key. `:302-320` `test_rotate_reseals_an_existing_secret`: default does not PUT; `--rotate` does and reports `secret-rotated`. | Behavioral, hermetic; generated ephemeral test key only. No real repository secret is inspected. |
| `fleet-app-05` dry-run has no writes and emits planned actions without requiring PEM | `scripts/fleet-app-enroll.py:234-257` `_ensure_variable`; `:274-293` `_ensure_secret`; `:386-404` `_validate` exempts dry-run from private key requirement | `tests/test_fleet_app_enroll.py:323-333` `test_dry_run_performs_no_writes`: empty write list, mode `dry-run`, planned variable and secret actions. The environment explicitly has an empty `FLEET_APP_PRIVATE_KEY`. | Behavioral, hermetic. |
| `fleet-app-06` reconciler rejects invalid inputs before request; workflow App-pair preflight exists but is not demonstrated fail-closed end-to-end | `.github/workflows/fleet-app-enroll.yml:46-73` named pair checks; `scripts/fleet-app-enroll.py:386-404` `_validate`; `:407-418` `run` validates before client requests. **Reviewed baseline:** `.github/workflows/fleet-app-enroll.yml:87-105` falls back to `github.token` when the mint step produces an empty output and the resolver runs. Route remediation to [DG19 plan](../dg19-fail-closed-fleet-enrollment-token/proposal.md). | `tests/test_fleet_app_enroll.py:372-383` `test_missing_token_is_a_usage_error_and_writes_nothing`; `:386-398` `test_invalid_app_id_fails_before_api_request_or_report` (empty and nonnumeric); `:464-477` workflow content test asserts the named missing-pair messages only. | Reconciler validation is hermetic. Workflow assertions are static and do not simulate mint failure; the workflow does **not** currently prove the complete fail-closed requirement. DG19 records the fallback repair. |
| `fleet-app-07` only schedule/manual triggers; scheduled apply; manual defaults to dry-run; runner, timeout, concurrency | `.github/workflows/fleet-app-enroll.yml:20-41` trigger/job/concurrency; runner and timeout at `:40-41`; `:87-105,120-135` mode expression and conditional `--dry-run` invocation. Leading workflow marker is `:17`. | `tests/test_fleet_app_enroll.py:438-448` `test_workflow_has_no_pull_request_trigger_and_a_safe_dispatch_default` asserts trigger set, default, expression and CLI arguments. `:450-461` `test_workflow_runs_nightly_on_devgate_off_the_hour` asserts schedule, runner, timeout and concurrency. | Static workflow-contract checks only. Neither the scheduled job nor manual dispatch was run. |
| `fleet-app-08` reconciler output scrubbing and ciphertext differ from PEM; end-to-end workflow credential boundary is not demonstrated | `scripts/fleet-app-enroll.py:185-204` `seal_secret`; `:343-370` `_scrub`/`_emit`. Workflow env wiring is `:120-135`. **Reviewed baseline:** `.github/workflows/fleet-app-enroll.yml:87-105` writes whichever token was chosen (including fallback `github.token`) to `$GITHUB_OUTPUT`, a file. Route remediation to [DG19 plan](../dg19-fail-closed-fleet-enrollment-token/proposal.md). | `tests/test_fleet_app_enroll.py:276-299` asserts ciphertext differs from fixture PEM and decrypts correctly. `:354-369` `test_credentials_never_reach_stdout_or_the_report` searches reconciler stdout, stderr and JSON report for fixture PEM, body and token. `:464-477` asserts workflow key env wiring and pinned actions. | Reconciler behavior is hermetic with dummy token and ephemeral test key. The tests do not observe the workflow's output file or execute token mint/fallback; full `fleet-app-08` is **not established**. DG19 records the workflow repair and remaining issuer boundary. |
| `fleet-app-09` one repository failure is recorded while healthy repo proceeds; report written before nonzero result | `scripts/fleet-app-enroll.py:295-318` `reconcile_repo`; `:407-481` `run` processes all selected repos, emits report, then chooses exit | `tests/test_fleet_app_enroll.py:336-351` `test_one_repo_error_does_not_stop_the_others_and_exits_nonzero`: failed count 1, broken repo has errors, healthy repo has no errors and secret action, exit 1. `invoke` reads the temporary report after run. | Behavioral, hermetic. No fleet-wide run. |

## Separate active-change IDs

| ID | Existing evidence / disposition |
|---|---|
| `fleet-app-10` | This file supplies the requested nine-ID mapping. There is no independent map-validation test, and no source marker is claimed as proof of the mapping quality. The new behavior test for the previously uncovered foreign-host pagination scenario is included above. |
| `fleet-app-11` | **NOT_RUN** for terminal per-requirement evidence: no configured signer set or signed evidence artifact for this enrollment work was supplied in this worktree. The local hermetic pytest result is not a signed bundle and is not a live run. No signature, signer identity, or live result is claimed. |

## Live status

**NOT_RUN:** no live fleet enrollment, GitHub Actions workflow execution, or
signed live report was reviewed for this change. All passing behavior tests
above are against disposable in-memory fixtures.

## DG-19 follow-up

The source anchors above refer to the original DG-05 review snapshot. The
current workflow rejects an empty minted token before reconciliation and
uses the pinned action output directly from the reconciler environment.
Issuer-owned token file handling remains open. [Current DG-19 evidence](../dg19-fail-closed-fleet-enrollment-token/evidence.md)