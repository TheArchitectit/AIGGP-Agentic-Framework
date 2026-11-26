# Qualify monitor recovery under single-writer ownership

## Why

The monitor already keeps its runner registry and alert history on its configured
instance volume, and registry writes use an atomic file replacement. That protects
an individual write from a partial file, but it does not define how to create and
verify a restorable state backup, fence an old writer before restore, or show that
the restored monitor has reconciled its state with the spokes.

The existing `mon-hub-01` requirement establishes one monitor service. This change
defines controlled backup and recovery within that single-writer model. It does not
add a second monitor, automatic failover, or a deployment claim.

## What Changes

- Define a manifest and digest checks for a consistent backup of the configured
  monitor state: the runner registry, service map, and append-only alert logs.
- Require recovery to validate the complete backup before applying it and to keep
  the live state unchanged when validation fails.
- Define explicit restored and converged receipts. Preserved valid enrollments may
  reconcile through authenticated heartbeats; missing or unusable enrollments are
  marked for controlled re-enrollment and never counted healthy by default.
- Require exclusive writer fencing and a new state generation before recovery can
  start the monitor. The existing single-writer boundary remains in force.
- Keep backup data, manifests, and receipts in private instance storage. Exclude
  environment secrets, bearer tokens, live endpoints, host identifiers, and private
  deployment details from committed examples and public receipts.

## Existing Work and Boundaries

The archived `2026-10-03-ai01-runner-monitor-impl` change defines persistent
registry and alert-log storage; this change adds recovery qualification to that
design. The archived GitLab restore-deferral review concerns a separate GitLab
instance backup drill. The active `dg09-gitlab-runner-live-monitoring` change
concerns optional GitLab polling and does not define monitor-state recovery.

## Impact

The hub architecture and future backup/restore tooling, registry and service-map
schemas, alert-state reconciliation, and local recovery fixtures. All implementation
and operational verification tasks remain open; no live instance or private
deployment details are required by this proposal.
