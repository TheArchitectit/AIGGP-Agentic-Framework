# Spec: Adding a runner to an existing fleet

## Requirement: Documented N+1th runner procedure
<!-- id: fleet-add-01 -->
The runner templates SHALL include a walkthrough for adding a runner to a
fleet that already has runners, a shared entrypoint, and a monitor-hub. The
walkthrough SHALL cover submodule transport options (HTTPS default, SSH with
per-repo deploy key for private repos), token hygiene, durability, and the
registration+verification steps. The walkthrough SHALL use role placeholders
in place of real hostnames, IPs, or tokens per mon-registry-01. It SHALL NOT
instruct readers to edit inside a `.devgate/` submodule per base-own-01. It
SHALL point to the operator's private infra repo for machine-specific details.
It SHALL be discoverable from `templates/runner/README.md`.

#### Scenario: operator adds a runner to a running fleet
- **WHEN** an operator follows the walkthrough on a fleet host
- **THEN** they create a quadlet with a shared entrypoint bind-mount, a
  token drop-in, and a dedicated work volume, and the runner registers
  without forking the entrypoint

#### Scenario: public submodule transport
- **WHEN** the target repo's `.devgate` submodule is public
- **THEN** the walkthrough's default HTTPS URL works with zero credentials

#### Scenario: private submodule transport
- **WHEN** the target repo's `.devgate` submodule is private
- **THEN** the walkthrough documents the SSH+deploy-key fallback with
  per-repo key scoping

#### Scenario: no secrets in the walkthrough
- **WHEN** the add-a-runner.md is scanned for tokens, IPs, or hostnames
- **THEN** none are found — only role placeholder names per mon-registry-01

#### Scenario: discoverability
- **WHEN** an operator reads templates/runner/README.md (the first-provision
  guide)
- **THEN** a link to add-a-runner.md is visible for operators who already
  have a fleet