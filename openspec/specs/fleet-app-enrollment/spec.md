# fleet-app-enrollment Specification

## Purpose
Keeping every non-archived repository enrolled with the fleet GitHub App: discovery follows every installation page, archived repos are skipped visibly, variables and secrets are reconciled idempotently and non-destructively, and a dry run performs zero writes.

## Requirements

### Requirement: Discovery follows every installation page
<!-- id: fleet-app-01 -->
Discovery SHALL read `GET /installation/repositories?per_page=100` and SHALL
follow every `Link` header carrying `rel="next"` until no next link remains.
Every repository the installation reports SHALL be considered, regardless of
visibility or fork status, and a single-page read SHALL NOT be treated as the
whole fleet.

#### Scenario: the installation spans multiple pages
- **WHEN** the installation listing reports three repositories across two pages
- **THEN** every repository on both pages is reconciled and the second page is fetched from its `rel="next"` link

#### Scenario: a next link leaves the GitHub API
- **WHEN** a `Link` header points at a host other than HTTPS `api.github.com`
- **THEN** the run fails closed without following the link

### Requirement: Archived repositories are skipped visibly
<!-- id: fleet-app-02 -->
An archived repository SHALL be skipped without any variables or secrets
request, SHALL be named in the report with the action `skipped-archived`, and
SHALL be counted under `counts.archived_skipped`. A skip SHALL be visible in
the report rather than inferred from a repository that is simply absent.

#### Scenario: one archived repository in the listing
- **WHEN** the installation reports one archived repository among active ones
- **THEN** no actions request is made for it, `counts.archived_skipped` is 1, and the run still exits 0

### Requirement: Variable reconciliation is idempotent
<!-- id: fleet-app-03 -->
The reconciler SHALL compare the repository variable `DEVGATE_SWEEP_APP_ID`
with the configured App ID. It SHALL POST when the variable is absent, PATCH
when the value differs, and perform no write when it matches. Updating a
repository variable SHALL use GitHub's `PATCH` endpoint; `PUT` is not the
update operation and SHALL NOT be used.

#### Scenario: absent, wrong, and matching values
- **WHEN** three repositories carry no variable, a stale value, and the configured value
- **THEN** the first is created, the second is updated, and the third receives no write

### Requirement: Secret creation is idempotent and non-destructive
<!-- id: fleet-app-04 -->
A secret value cannot be read back, so an existing private-key secret SHALL be
treated as present and correct and SHALL NOT be overwritten by a default run.
When the secret is absent the reconciler SHALL fetch the repository Actions
public key, seal the PEM in memory, and PUT the ciphertext. Re-sealing an
existing secret SHALL occur only under an explicit `--rotate`.

#### Scenario: the secret already exists
- **WHEN** a default run finds `DEVGATE_SWEEP_APP_PRIVATE_KEY` metadata present
- **THEN** it reads metadata only and issues no PUT

#### Scenario: explicit rotation
- **WHEN** the same run is given `--rotate`
- **THEN** it fetches the public key, PUTs a newly sealed value, and reports `secret-rotated`

### Requirement: Dry run performs zero writes
<!-- id: fleet-app-05 -->
`--dry-run` SHALL perform reads only and SHALL issue no POST, PATCH, or PUT.
Planned work SHALL be reported with `-planned` action names so a plan is
distinguishable from an applied run. A dry run that needs no seal SHALL NOT
require the private key.

#### Scenario: unconfigured repository in dry-run
- **WHEN** a dry run reaches a repository with no variable and no secret
- **THEN** no write request occurs and the report carries `variable-create-planned` and `secret-create-planned`

### Requirement: App authentication fails closed
<!-- id: fleet-app-06 -->
The enrollment workflow SHALL require both `vars.DEVGATE_SWEEP_APP_ID` and
`secrets.DEVGATE_SWEEP_APP_PRIVATE_KEY` and SHALL fail, naming the missing
half, when either is absent. It SHALL NOT fall back to `github.token` for
enrollment, because that token cannot administer another repository. The
reconciler SHALL reject invalid inputs with exit 2 before making a request.

#### Scenario: only half the pair is configured
- **WHEN** the App ID variable is set and the private-key secret is missing
- **THEN** the workflow fails by name instead of running on the workflow token

#### Scenario: missing installation token
- **WHEN** `FLEET_APP_TOKEN` is empty
- **THEN** the reconciler exits 2 and writes no report

### Requirement: Execution is scheduled and fleet-only
<!-- id: fleet-app-07 -->
The workflow SHALL declare only `schedule` and `workflow_dispatch`; it SHALL
NOT declare `pull_request` or `pull_request_target`. A scheduled run SHALL
apply. A manual dispatch SHALL default to `dry_run=true`. The job SHALL run on
the `devgate` label with a 45-minute timeout and workflow-level concurrency
that prevents overlapping runs.

#### Scenario: trigger surface
- **WHEN** the workflow file is read
- **THEN** its only triggers are `schedule` and `workflow_dispatch`

#### Scenario: a scheduled run applies
- **WHEN** the workflow runs from its schedule
- **THEN** the reconciler runs without `--dry-run`

#### Scenario: a manual dispatch plans by default
- **WHEN** a dispatch supplies no `dry_run` input
- **THEN** the reconciler runs with `--dry-run` because the input defaults to true

### Requirement: No credential reaches a report or a log
<!-- id: fleet-app-08 -->
The private key and token SHALL be supplied to the reconciler through the
environment and SHALL NOT appear in argv, a written file, stdout, stderr, or
the JSON report. Report and log content SHALL be limited to repository names,
action names, statuses, and errors that carry no response body. Sealed
ciphertext SHALL differ from the PEM it seals.

#### Scenario: an applied run creates a secret
- **WHEN** the reconciler seals a PEM and the report and streams are inspected
- **THEN** neither the PEM nor the token appears, and the stored ciphertext is not the PEM

### Requirement: Per-repository errors do not stop the fleet
<!-- id: fleet-app-09 -->
A per-repository failure SHALL be recorded in that repository's `errors` and
SHALL NOT stop the remaining repositories from being reconciled. The run SHALL
write the report and then exit nonzero when any repository failed. Exit 0
SHALL mean that no repository failed.

#### Scenario: one repository fails, another is healthy
- **WHEN** one repository's variable read returns HTTP 500 and a second repository is fully configured
- **THEN** the second is still reconciled, `counts.failed` is 1, and the run exits 1
