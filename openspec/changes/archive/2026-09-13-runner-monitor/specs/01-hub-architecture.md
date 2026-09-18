# Spec: Hub-and-spoke monitor architecture

## Requirement: Single hub on monitor-hub
<!-- id: mon-hub-01 -->
The monitor shall run as ONE hub service on the monitor-hub machine, deployed as a
container under the repo's self-hosted runner standard (Podman quadlet,
persistent volume, env-drop-in secrets); every DevGate runner shall report
directly to that hub over the local network and no runner shall require a
peer connection to any other runner.

#### Scenario: hub is the only well-known endpoint
- **WHEN** a new runner is deployed from templates/runner/
- **THEN** the only monitoring endpoint it is configured with is the monitor-hub
  hub's local-network URL

## Requirement: Local-only network posture
<!-- id: mon-local-01 -->
The system shall require no inbound network opening into the owner's
environment: spoke-to-hub enrollment and heartbeat traffic shall travel
only over the local network (same host or LAN), the hub shall bind to
loopback or LAN addresses only and shall expose no internet-facing
listener, and every external interaction — GitHub API polling, alert-issue
filing, and hub status publication — shall be an outbound connection
initiated by the hub.

#### Scenario: no inbound firewall rules
- **WHEN** the hub and spokes are deployed per the monitor-hub runbook
- **THEN** no inbound firewall rule into the owner's environment is
  required and no component listens on a public interface

#### Scenario: external checks stay outbound
- **WHEN** the hub polls GitHub or files an alert issue
- **THEN** the connection is initiated outbound by the hub and nothing
  internet-side connects into the environment

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
