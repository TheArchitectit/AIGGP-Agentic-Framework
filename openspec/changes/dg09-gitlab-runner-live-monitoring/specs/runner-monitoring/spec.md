# Spec Delta

## MODIFIED Requirements

### Requirement: Runner online detection
<!-- id: mon-online-01 -->
The hub SHALL evaluate each registered runner's online state from its declared forge API status AND heartbeat freshness. GitHub runners SHALL continue to use the GitHub API and existing two-heartbeat stale bound. GitLab runners SHALL use the declared GitLab forge adapter only after an operator activates a live instance declaration. A non-online, unknown, or error API observation, or a heartbeat older than two heartbeat intervals, SHALL raise an alert or explicit unverified/error status and SHALL NOT be reported healthy.

#### Scenario: dead quadlet
- **WHEN** a runner container stops and two heartbeat intervals pass
- **THEN** the hub raises an alert naming the runner and its repo

#### Scenario: dormant optional GitLab support
- **WHEN** no operator declaration activates a live GitLab instance
- **THEN** GitLab remains an optional fixture-tested forge and no live GitLab probe is required or reported as passing

#### Scenario: activated GitLab runner health
- **WHEN** an operator declares an adopted GitLab instance and registers a runner against it
- **THEN** the hub combines status from that declared GitLab API adapter with the runner heartbeat and never uses GitHub API data for GitLab runner status

#### Scenario: GitLab status is unknown or errors
- **WHEN** an activated GitLab status observation is missing, unknown, or returns an API error
- **THEN** the hub reports the check as unverified/error and raises an alert; it does not treat the heartbeat alone as proof that GitLab reports the runner online
