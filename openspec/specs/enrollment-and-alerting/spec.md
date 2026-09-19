# Enrollment, heartbeat, and alerting

## Purpose

Spokes enroll with one-time tokens, authenticate heartbeats with per-runner revocable tokens, and the hub raises deduplicated GitHub issue alerts keyed by (repo, check-class, runner) with an append-only JSONL audit trail.

## Requirements


### Requirement: Talk-home enrollment over the local network
<!-- id: mon-enroll-01 -->
A new runner SHALL enroll by a single operator command on its host
(`scripts/runner-enroll.sh <hub-url> <enrollment-token>`), where the hub
URL is a local-network address (loopback or LAN); the hub SHALL verify a
one-time enrollment token, record the runner identity
(name, repo, labels, host alias), issue a per-runner heartbeat token, and
the script SHALL install a systemd user timer that posts heartbeats to the
same local address. The hub SHALL reject enrollment or heartbeat posts
bearing unknown or revoked tokens.

#### Scenario: first enrollment
- **WHEN** the operator runs runner-enroll.sh with a valid token against
  the hub's local-network URL
- **THEN** the runner appears in runners.json and heartbeats begin within
  one interval

#### Scenario: revoked runner
- **WHEN** a runner's heartbeat token is revoked
- **THEN** its subsequent heartbeat posts are rejected and it is marked
  unenrolled

### Requirement: Deduplicated failure alerts, outbound-only
<!-- id: mon-alert-01 -->
The hub SHALL raise alerts as GitHub issues (default channel) on the
affected repo — outbound-only API writes initiated by the hub, requiring
no inbound path — deduplicated by (repo, check-class, runner): one open
issue per key, with recurrence posted as a comment, and every alert
appended to an append-only JSONL alert log on the hub volume.

#### Scenario: repeated stall
- **WHEN** the same runner stalls again while its alert issue is open
- **THEN** the hub comments on the open issue instead of filing a new one

### Requirement: monitor-hub machine duties stay off-repo
<!-- id: mon-monitor-hub-01 -->
Everything requiring the monitor-hub machine itself — creating the hub volume,
minting the GitHub API token and enrollment tokens into chmod-600 env
drop-ins, binding the hub listen address to loopback or LAN only (with no
inbound firewall opening into the owner's environment), enabling linger,
starting the quadlet — SHALL be documented as a runbook
(docs/runner-monitor-monitor-hub.md) and SHALL not be represented by any
committed credential, token, or host detail.

#### Scenario: fresh monitor-hub rebuild
- **WHEN** the hub is redeployed from a bare monitor-hub machine
- **THEN** the runbook alone is sufficient and no step requires reading a
  secret from this repository or opening an inbound firewall rule
