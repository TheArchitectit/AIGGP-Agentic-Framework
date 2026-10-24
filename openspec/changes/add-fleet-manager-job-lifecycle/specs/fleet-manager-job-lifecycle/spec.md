# Spec: Fleet Manager one-job lifecycle

## ADDED Requirements

### Requirement: One job per instance, and no way back to warm
<!-- id: fleet-008-01 -->
A job runner instance SHALL accept at most one job. The lifecycle SHALL be a
closed state machine whose states are `PREPULLED`, `ASSIGNED`, `RUNNING`,
`REFUSED`, `COMPLETED`, `TIMED_OUT`, `CANCELLED`, `DISCONNECTED`, `DESTROYED`,
`PROVEN_CLEAN`, and `QUARANTINED`.

The terminal states of a job are `COMPLETED`, `TIMED_OUT`, `CANCELLED`, and
`DISCONNECTED`, where `DISCONNECTED` is an uncertain disconnect. Every terminal
state SHALL lead to destruction. A terminal state SHALL NOT return to a warm
state, and the warm pool SHALL NOT count an instance that has accepted a job.

Offering a job to an instance that has already accepted one SHALL be refused as
a policy denial.

#### Scenario: a second job is refused

- **WHEN** an instance in `ASSIGNED` or `RUNNING` is offered another job
- **THEN** the offer is refused as `POLICY_DENIAL`, and the instance's state is
  unchanged

#### Scenario: a used instance is not warm

- **WHEN** an instance has accepted a job and reached a terminal state
- **THEN** it is not in `WARM_STATES`, and `WarmPool` does not count it

#### Scenario: an uncertain disconnect is a terminal state

- **WHEN** a running instance loses its connection without a clean completion
- **THEN** it is `DISCONNECTED`, which is terminal, and it is destroyed

#### Scenario: no transition back to warm

- **WHEN** a lifecycle is asked to move a terminal instance to `PREPULLED` or
  `STOPPED_CLEAN`
- **THEN** the request is refused as `UNKNOWN_STATE` naming the state pair

### Requirement: Cleanup is proved before a replacement joins capacity
<!-- id: fleet-008-02 -->
A replacement instance SHALL NOT join capacity while a previous instance's
cleanup is unproven and its resources are not quarantined. Cleanup SHALL be
evidenced by a value carrying instance identity, image digest, job identity if
known, the volume disposal result, the network disposal result, and the start
and finish timestamps.

Every field except job identity SHALL be required; a proof missing one SHALL be
refused at construction. Job identity SHALL be optional, and its absence SHALL
not invalidate a proof. A disposal result SHALL be one of `DISPOSED`, `ABSENT`,
or `FAILED`, and a proof whose volume or network result is `FAILED` SHALL NOT be
admitted as proof of cleanup.

#### Scenario: an incomplete proof is refused

- **WHEN** a cleanup proof is built without a volume disposal result, or without
  timestamps, or without an image digest
- **THEN** construction is refused, naming the missing field

#### Scenario: a proof without a job identity

- **WHEN** an instance is disconnected and its job identity is never learned
- **THEN** a proof with no job identity is still a proof

#### Scenario: a failed disposal is not a proof

- **WHEN** a proof reports `FAILED` for volume disposal or network disposal
- **THEN** it does not satisfy clean-by-proof and the replacement is not admitted

#### Scenario: admission waits for the proof

- **WHEN** an instance has been destroyed but no proof and no quarantine exist
- **THEN** the pool reports the shortfall and does not admit a replacement

### Requirement: Quarantine is a state with a reason
<!-- id: fleet-008-03 -->
An instance whose cleanup cannot be proved SHALL be quarantined rather than
returned to any pool. A quarantine SHALL name the instance, the failure kind,
and the time of quarantine. Quarantined stock SHALL NOT count as capacity.

An instance SHALL be provable clean or quarantined; an instance that is neither
SHALL leave its pool short of the replacement capacity it would otherwise hold.

#### Scenario: a failed proof quarantines

- **WHEN** cleanup evidence reports a failed disposal
- **THEN** the instance is `QUARANTINED`, the reason names the failure kind, and
  the pool does not count it

#### Scenario: a quarantine is inspectable

- **WHEN** a quarantined instance is observed
- **THEN** the observation carries the instance id, the failure kind, and the
  quarantine time

#### Scenario: quarantine is not deletion

- **WHEN** an instance is quarantined
- **THEN** it still exists as a value with its identity, and is not silently
  dropped from the pool's record

### Requirement: Resource limits are required and rendered
<!-- id: fleet-008-04 -->
An ephemeral instance SHALL carry memory, cpu, and process-count limits. Each
limit SHALL be required, SHALL be positive, and SHALL be bounded above. A
missing, non-positive, or unbounded limit SHALL be refused at construction.

The rendered command SHALL include the limits it was constructed with, so that
the executed command is the same value the limits were validated against.

#### Scenario: a missing limit is refused

- **WHEN** an ephemeral instance is built without a memory limit
- **THEN** construction is refused naming the memory limit

#### Scenario: an unbounded limit is refused

- **WHEN** a process-count limit is zero, negative, or above the bound
- **THEN** construction is refused naming the process-count limit

#### Scenario: the command carries the limits

- **WHEN** an ephemeral instance with limits is asked for its command
- **THEN** the command names each limit with the value it was constructed with

### Requirement: Lifecycle failures are the closed typed errors
<!-- id: fleet-008-05 -->
A lifecycle failure SHALL be raised as one of the eight typed error kinds of the
adapter contract, and SHALL NOT introduce a ninth. A lifecycle call SHALL NOT
propagate a bare exception to its caller: anything unexpected SHALL be
classified into `RUNTIME_FAILURE` naming the exception's type only.

The kind SHALL match the failure: a refused job offer and a refused admission
are `POLICY_DENIAL`; a failed or incomplete cleanup is `CLEANUP_FAILURE`; a pool
at its ceiling is `CAPACITY_EXHAUSTION`; a state transition with no rule is
`UNKNOWN_STATE`.

#### Scenario: a refused offer is a policy denial

- **WHEN** a second job is offered to an assigned instance
- **THEN** the error kind is `POLICY_DENIAL`

#### Scenario: an incomplete cleanup is a cleanup failure

- **WHEN** a proof is refused for a missing field or a failed disposal
- **THEN** the error kind is `CLEANUP_FAILURE`

#### Scenario: an unexpected exception is classified

- **WHEN** a lifecycle step raises a `ValueError` from deeper code
- **THEN** the caller sees `RUNTIME_FAILURE` whose detail names `ValueError`
  only
