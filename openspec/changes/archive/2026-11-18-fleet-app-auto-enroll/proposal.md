# Change: Automatic Fleet GitHub App Enrollment

> **Status:** Implemented and unit-tested; live apply is still pending (the
> owner runs it). This package is deliberately not archived.

## Why

`TheArchitectit` is a user account, not an organization, so there are no
organization secrets to inherit. Every repository carries its own
`DEVGATE_SWEEP_APP_ID` variable and `DEVGATE_SWEEP_APP_PRIVATE_KEY` secret.
A repository created tomorrow starts without them, and until a human sets the
pair its fleet workflows fall back to `github.token` (1,000 requests/hour,
scoped to that one repository). The user identity already measured 0/5,000
remaining on 2026-11-18, so the fallback is both slower and pressure on the
wrong budget.

The App installation is 101651861 with `repository_selection=all` and
actions/secrets/administration write. What was missing was the per-repository
copy of the pair, not the App. A new repository should be enrolled the night
it appears, without a human remembering to run two commands.

## What Changes

- **Add `scripts/fleet-app-enroll.py`.** A reconciler that lists every
  repository the installation covers (Link-header pagination), skips archived
  repositories with an explicit count, and ensures the variable and secret on
  every other repository. Stdlib plus `PyNaCl` for the sealed secret.
- **Add `.github/workflows/fleet-app-enroll.yml`.** Nightly at 05:23 UTC and
  on manual dispatch. Scheduled runs apply; a dispatch defaults to
  `dry_run=true`. It reuses the canonical fail-closed App pair check and the
  pinned `actions/create-github-app-token` from `spec-fleet.yml`.
- **Add `tests/test_fleet_app_enroll.py`.** Fifteen tests against an
  in-memory fake GitHub API: pagination, archived skipping, variable
  create/update/skip, secret create/skip, rotation, dry-run, error isolation,
  credential absence from output, sealed ciphertext, and workflow structure.
- **Document it in `docs/GITHUB-APP-TOKEN.md`.** What is compared, what is
  not (an existing secret's value is unreadable), the nightly timing, the
  manual flags, and the scope limits.

## Non-goals

- Enrollment writes only the variable and the secret. It does not install
  workflows into other repositories, modify their code, add collaborators,
  delete, disable, or archive anything.
- It cannot enroll a collaborator's separate account. That account needs its
  own App installation and its own credential pair.
- The variable update uses `PATCH`, which is GitHub's update operation. A
  `PUT` would fail live and is not implemented.
