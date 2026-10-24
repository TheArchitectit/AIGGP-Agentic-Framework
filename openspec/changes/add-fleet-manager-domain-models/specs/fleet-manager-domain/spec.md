# Spec: Fleet Manager desired-state models

## ADDED Requirements

### Requirement: Desired state is held by the manager, and it is immutable
<!-- id: fleet-001-01 -->
The Fleet Manager SHALL represent desired state as immutable values with an
increasing revision. Every transition SHALL return a new value with a new
revision and SHALL leave the value it was given unchanged, so an applied
revision always names a complete world rather than a set of edits.

What a host reports SHALL be a separate type. No desired-state value SHALL be
constructible from an observation, and the observation type SHALL NOT be
accepted where desired state is required: turning a host's report into desired
state requires an explicit manager operation that produces a new revision.

#### Scenario: a transition does not mutate its input

- **WHEN** an assignment or a drain is applied to a `DesiredState`
- **THEN** the original value keeps its revision and its collections, and the
  new value carries revision + 1

#### Scenario: an observation is offered as desired state

- **WHEN** an `Observation` is passed where a `DesiredState` (or any part of
  one) is expected
- **THEN** it is refused as a wrong type rather than coerced

#### Scenario: the two modules stay apart

- **WHEN** either module gains an import of the other
- **THEN** the test that reads both module sources fails

### Requirement: A pool declares its whole contract or is refused by field
<!-- id: fleet-001-02 -->
A pool SHALL declare every field the program's desired-state model requires —
identity and revision, trust class, allowed repositories or runner group,
required labels, runtime adapter, pinned image digest, architectures, ephemeral
mode, warm and scale bounds, the three timeouts, network and filesystem
profiles, secret profile reference, update channel and rollback image,
maintenance window, disruption budget, owner and escalation route. A pool
missing a field SHALL be refused, and the refusal SHALL name the field.

Documents SHALL be closed: an unknown field is refused, because a store that
silently drops what it does not understand cannot be trusted to keep what it
promised.

#### Scenario: a required field is absent

- **WHEN** a pool document omits, say, `image_digest`
- **THEN** the refusal names `image_digest` and no other field

#### Scenario: an unknown field appears

- **WHEN** a pool document carries a field the model does not declare
- **THEN** the document is refused and the field is named

#### Scenario: Phase 1 is ephemeral-only

- **WHEN** a pool declares `ephemeral: false`
- **THEN** it is refused, because the v1 capacity contract's `ephemeral`
  is `const true` and the model must not describe a fleet the contract cannot
  serve

### Requirement: Secrets are referenced, never carried
<!-- id: fleet-001-03 -->
The model SHALL hold secret profiles by reference only. A document SHALL be
refused when any key outside the declared reference fields looks like a secret
value (`token`, `password`, `secret`, `api_key`, `private_key`, `credential`
and their plurals), and a reference field's value SHALL be reference-shaped
(lowercase identifier), not a blob.

Refusals SHALL name the field and the rule and SHALL NOT repeat the rejected
value, so a diagnostic cannot become the place a secret is stored.

#### Scenario: a value-shaped key appears

- **WHEN** any desired-state document carries `registration_token` or
  `password`
- **THEN** it is refused by path, and the value is not echoed

#### Scenario: a reference carries a blob

- **WHEN** `secret_profile` holds a long unpinned string rather than an
  identifier
- **THEN** it is refused as a reference-shape violation

### Requirement: A host may run a pool only where capabilities, allow-list and state agree
<!-- id: fleet-001-04 -->
An assignment SHALL be refused unless the host lists the pool's runtime and one
of its architectures, the pool is on the host's allow-list, and the host is
active. The refusal SHALL name which of those did not hold.

#### Scenario: architectures do not intersect

- **WHEN** a pool requires `arm64` and the only allowed host is `x86_64`
- **THEN** the assignment is refused naming the architecture

#### Scenario: the pool is not on the host's allow-list

- **WHEN** the host does not list the pool id
- **THEN** the assignment is refused naming the allow-list

### Requirement: Capacity, drain and rollout refuse impossible states
<!-- id: fleet-001-05 -->
Capacity SHALL be computed from assigned (not released) assignments against the
host's slot count, and an assignment that would exceed it SHALL be refused.
Drain SHALL follow `active → draining → drained` and back, and completing a
drain SHALL be refused while the host still has assigned work. A rollout SHALL
refuse an unpinned digest and a digest identical to the pool's current one, and
on success SHALL move the image, keep the previous image as the rollback, and
bump the pool revision.

#### Scenario: over-capacity

- **WHEN** a host with two slots already has two assignments
- **THEN** a third is refused and the capacity it names shows `free: 0`

#### Scenario: drain with work in flight

- **WHEN** a drain is completed on a host that still has an assignment
- **THEN** it is refused, naming the outstanding assignment count

#### Scenario: a rollout to the current image

- **WHEN** a rollout names the image the pool already runs
- **THEN** it is refused, because it would record a change that is not one
