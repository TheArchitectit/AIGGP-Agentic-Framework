# Spec: Hub-and-spoke monitor architecture

## Requirement: Single hub on monitor-hub
<!-- id: mon-hub-01 -->
The monitor shall run as ONE hub service on the monitor-hub machine, deployed as a
container under the repo's self-hosted runner standard (Podman quadlet,
persistent volume, env-drop-in secrets); every DevGate runner shall report
to that hub and no runner shall require a peer connection to any other
runner.

#### Scenario: hub is the only well-known endpoint
- **WHEN** a new runner is deployed from templates/runner/
- **THEN** the only monitoring endpoint it is configured with is the monitor-hub
  hub URL

## Requirement: Dual evidence channels
<!-- id: mon-channels-01 -->
The hub shall combine hub-side GitHub API polling with spoke-posted
heartbeats, and shall treat them as independent: polling alone shall be
sufficient to detect an offline runner or a stalled queue, and heartbeats
alone shall be sufficient to mark a spoke stale.

#### Scenario: unenrolled runner still watched
- **WHEN** a registered repo's runner has never sent a heartbeat
- **THEN** the hub still evaluates its API-side checks (online, queue,
  gates, drift) and alerts on them

## Requirement: Registry is instance state, never committed
<!-- id: mon-registry-01 -->
The runner registry (runners.json) shall live on the hub's persistent
volume on monitor-hub; this repository shall contain only the registry schema and
an example with placeholder values, and no committed file shall contain
host IPs, hostnames with credentials, tokens, or live runner instance data.

#### Scenario: public-repo hygiene
- **WHEN** the repo is scanned for secrets/host detail
- **THEN** no runner-monitor file contains tokens, IPs, or real hostnames

## Requirement: Hub death is detected by a spoke
<!-- id: mon-deadman-01 -->
The hub shall not be relied upon to report its own death, and the check shall
not run on GitHub-hosted runners. Each enrolled spoke shall install a local
watchdog that polls the hub's `/health` and fails its own systemd unit when the
hub is unreachable or its poll loop has gone stale; the watchdog shall
distinguish polling-disabled (`polling_enabled: false`, where `last_poll_at` is
null by design) from a wedged poll loop, and shall exit non-zero rather than
pass when it cannot perform the check at all.

#### Scenario: hub container dies
- **WHEN** the hub stops responding to `/health` and a spoke's watchdog runs
- **THEN** that spoke's watchdog unit enters the failed state without
  requiring a GitHub-hosted runner or an issue-writing token on the spoke

#### Scenario: hub alive but polling disabled
- **WHEN** the hub serves `/health` with `polling_enabled: false`
- **THEN** the watchdog warns that nothing is monitored and exits 0, rather
  than reporting the hub as dead
