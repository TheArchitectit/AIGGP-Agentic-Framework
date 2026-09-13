# Spec: Runner health monitoring

## Requirement: Runner online detection
<!-- id: mon-online-01 -->
The hub shall evaluate each registered runner's online state from the
GitHub API runner status AND heartbeat freshness; a runner whose API status
is not `online`, or whose heartbeat is older than two heartbeat intervals,
shall raise an alert.

#### Scenario: dead quadlet
- **WHEN** a runner container stops and two heartbeat intervals pass
- **THEN** the hub raises an alert naming the runner and its repo

## Requirement: Queue-drain detection
<!-- id: mon-queue-01 -->
The hub shall alert when any workflow run queued for a registered runner
label remains queued beyond a threshold (default 30 minutes, per-repo
override), so a runner that stops draining — the `example-runner` failure
class of 2026-09-12 — is caught in minutes, not days.

#### Scenario: stalled queue
- **WHEN** a run targeting a registered label is queued for 30 minutes
- **THEN** the hub raises an alert naming the repo, run, label, and age

## Requirement: Gate-result tracking
<!-- id: mon-gates-01 -->
The hub shall track the latest check-run conclusion per watched branch
(default branch at minimum) for every registered repo and shall alert on
`failure` or `timed_out`, naming the repo, gate, and commit SHA.

#### Scenario: red gate on main
- **WHEN** a gate check run concludes `failure` on a watched branch
- **THEN** an alert names the repo, the gate, and the failing commit

## Requirement: Drift-scan recency
<!-- id: mon-drift-01 -->
For every registered repo with a scheduled drift scan, the hub shall alert
when no scan has completed within one scheduled period plus a grace window,
or when the latest completed scan failed.

#### Scenario: overdue drift scan
- **WHEN** a repo's drift scan is overdue by more than one period plus grace
- **THEN** the hub raises an alert naming the repo and the last run time
