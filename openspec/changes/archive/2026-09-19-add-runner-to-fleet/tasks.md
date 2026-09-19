# Tasks: add-runner-to-fleet

## Sprint 1 — Walkthrough document

- [x] 1.1 Write `templates/runner/add-a-runner.md` documenting:
  - Shared entrypoint reuse (bind-mount, don't fork)
  - Token hygiene (pipe raw `gh api` output, never through argv)
  - Submodule transport (HTTPS default, SSH + deploy key for private repos)
  - Durability (credential pre-seed, `EnvironmentFile=` must exist)
  - Registration + verification steps
  - `.gitignore` pointer to private infra repo
- [x] 1.2 Add `.gitignore` block pointing to private infra repo for
  machine-specific fleet details
- [x] 1.3 Link from `templates/runner/README.md` ("If you already have
  runners, see add-a-runner.md")

## Sprint 2 — Spec

- [x] 2.1 Add `fleet-add-01` requirement to `specs/add-runner-to-fleet/spec.md`
- [x] 2.2 Cite existing constraints: `mon-monitor-hub-01`, `mon-registry-01`,
  `mon-enroll-01`