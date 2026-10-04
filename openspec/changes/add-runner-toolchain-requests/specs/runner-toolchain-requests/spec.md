# Spec: Runner toolchain requests

## ADDED Requirements

### Requirement: A runner reports a capability gap from a closed vocabulary
<!-- id: mon-tc-01 -->
A spoke MAY report a `missing_tools` list on its heartbeat. Each entry
SHALL name a tool from the vocabulary this spec defines, and SHALL NOT carry a
version, package name, URL, or command. A `missing_tools` entry outside the
vocabulary SHALL be rejected: the heartbeat SHALL record the rejection and SHALL
NOT create or update a request. A heartbeat reporting no gap SHALL be
indistinguishable in effect from one sent before this capability existed.

The initial vocabulary is: `cargo`, `cmake`, `dotnet`, `gcc`, `g++`, `gitleaks`,
`go`, `gradle`, `java`, `make`, `maven`, `node`, `npm`, `pnpm`, `pip`,
`python`, `shellcheck`.

#### Scenario: a job needs a tool the image lacks
- **WHEN** a heartbeat carries `missing_tools: ["cargo"]`
- **THEN** the hub records the gap against that runner and reports success for
  the heartbeat

#### Scenario: a report names something that is not a known tool
- **WHEN** a heartbeat carries `missing_tools: ["curl … | sh"]` or any string
  outside the vocabulary
- **THEN** the hub records the rejection, creates no request, and does not
  echo the value into any stored field

#### Scenario: the image gains the tool
- **WHEN** a heartbeat no longer reports a gap previously reported
- **THEN** the request's state does not change on that heartbeat alone; only
  fulfillment (recorded with a digest) closes it

### Requirement: The hub is the system of record for requests
<!-- id: mon-tc-02 -->
The hub SHALL persist each request with its id, requesting runner, missing
tools, state, reason, first and last observation, decision author and
timestamp, decision note, and — once fulfilled — the pinned digest and its
timestamp. The hub SHALL expose the current request set and SHALL expose a
transition action for `open` → `approved` and `open` → `denied`. Mission
Control SHALL read the request set from the hub and SHALL NOT hold a
divergent copy of fleet request state.

#### Scenario: the same gap recurs across heartbeats
- **WHEN** a runner reports `missing_tools: ["cargo"]` on five consecutive
  heartbeats
- **THEN** one request exists, its `last_seen` advances, and no additional row
  is created

#### Scenario: Mission Control restarts
- **WHEN** the MC dashboard process is restarted
- **THEN** the open-request queue is served from the hub and is unchanged by
  the restart

### Requirement: A runner cannot decide its own request
<!-- id: mon-tc-03 -->
The approve and deny actions SHALL require an operator credential that is
distinct from the per-runner heartbeat token, and SHALL record the deciding
identity and the decision timestamp. A presented heartbeat token SHALL NOT
authorize a transition. A request SHALL NOT leave `open` without a recorded
decision author and timestamp.

#### Scenario: a job on the requesting lane calls the approve action
- **WHEN** a heartbeat token for `ucs03-zhm` is presented to the approve action
- **THEN** the action is refused, no state changes, and the refusal is recorded

#### Scenario: an operator denies with a reason
- **WHEN** an operator denies a request with a decision note
- **THEN** the state becomes `denied`, the author and timestamp are recorded,
  and the note is retained with the request

### Requirement: Fulfillment is a digest-pinned image change
<!-- id: mon-tc-04 -->
A request SHALL reach `fulfilled` only when a fulfillment record carrying the
image digest of the rebuilt lane is written against it. No transition in this
capability SHALL execute a package manager or otherwise install software on a
running runner. The recorded digest SHALL be the value the lane subsequently
reports in its existing `image_digest` field, so that the existing
`image_pin_divergence` check (img-cycle-05) continues to detect drift.

#### Scenario: approval without a build
- **WHEN** a request is approved but no fulfillment record follows
- **THEN** the state remains `approved` with no fulfilled digest, and the
  dashboard shows it as outstanding rather than complete

#### Scenario: fulfillment is recorded
- **WHEN** a fulfillment record with digest `sha256:…` is written against an
  approved request
- **THEN** the state becomes `fulfilled`, the digest and timestamp are
  retained, and the request joins to the lane's `image_digest`

### Requirement: A gap the fleet has not answered stays visible
<!-- id: mon-tc-05 -->
An open or approved request SHALL remain visible in the request set until it is
fulfilled or denied. An approved request that has not been fulfilled within the
fulfillment window SHALL be reported as outstanding. Absence of a request for a
lane SHALL NOT be presented as evidence that the lane's toolchain is complete.

#### Scenario: an approved request never gets built
- **WHEN** an approved request passes the fulfillment window with no
  fulfillment record
- **THEN** it is reported as outstanding, naming the age

#### Scenario: a lane is fully provisioned
- **WHEN** a lane's requests are all fulfilled
- **THEN** the lane appears with no open requests, and that absence is
  distinguishable from a lane that has never reported