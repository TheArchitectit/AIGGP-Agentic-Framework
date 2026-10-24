# Spec: Fleet Manager plan and apply

## ADDED Requirements

### Requirement: A plan is deterministic, complete, and impossible to edit
<!-- id: fleet-002-01 -->
Every planned mutation SHALL describe its creates, drains, replacements,
deletions and capacity impact before it is applied. A plan SHALL be a value:
its identity SHALL be a digest of exactly its base revision and its ordered
changes, so that two callers planning the same work against the same revision
produce the same plan, and a plan whose changes no longer match its identity
SHALL be refused.

Planning SHALL simulate every change against the state and SHALL refuse an
impossible change at plan time, naming the change's index and the reason. The
capacity impact SHALL be computed from that simulation rather than accepted
from the caller.

#### Scenario: the same work against the same revision

- **WHEN** two callers plan the same ordered changes against the same base
  revision
- **THEN** both plans carry the same identity and the same document

#### Scenario: a plan is edited after it was built

- **WHEN** a plan is constructed whose changes do not match its identity
- **THEN** it is refused as an edited plan, not applied

#### Scenario: a change that cannot happen

- **WHEN** a plan contains a change the state cannot accept, for example an
  assignment to a host whose slots are full
- **THEN** planning fails naming the change's index and the underlying reason,
  and no plan is produced

#### Scenario: capacity impact

- **WHEN** a plan assigns work to, or releases work from, a host
- **THEN** the plan reports that host's free slots before and after the plan

### Requirement: An apply is bound to its revision and its principal
<!-- id: fleet-002-02 -->
An apply SHALL only accept a plan whose base revision is the state's current
revision, and SHALL refuse a plan planned against any other revision, naming
both revisions. An apply SHALL require the `fleet.apply` scope, and an apply of
a plan containing any destructive change SHALL additionally require the
`fleet.admin` scope.

An apply SHALL revalidate each change against the real state and time before
producing the new revision, even though the plan already simulated it: a plan is
a prediction.

#### Scenario: the state moved on

- **WHEN** a plan planned against revision N is applied to revision N+1
- **THEN** the apply is refused as stale, naming both revisions

#### Scenario: a destructive change without authority

- **WHEN** a principal holding `fleet.apply` but not `fleet.admin` applies a
  plan that releases, drains or replaces running work
- **THEN** the apply is refused before any change, naming the missing scope

#### Scenario: a plan that no longer holds

- **WHEN** a plan is applied to the revision it names but one of its changes is
  no longer possible
- **THEN** the apply is refused and no new revision is produced

### Requirement: Retry is idempotent by key, and a key covers one plan
<!-- id: fleet-002-03 -->
An apply SHALL take an idempotency key. Re-sending an applied key with the same
plan SHALL return the recorded result without applying again, and SHALL record
the replay in the audit log. Re-using a key for a different plan SHALL be
refused. The ledger of keys SHALL be append-only.

#### Scenario: the client retries after a timeout

- **WHEN** the same key and the same plan are applied a second time
- **THEN** the recorded resulting revision is returned, the state is unchanged,
  and the audit log records a replay rather than a second apply

#### Scenario: a key is widened to cover other work

- **WHEN** a key already recorded for one plan is presented with a different plan
- **THEN** both plan identities are named in the refusal, and nothing is applied

### Requirement: The audit log is append-only and cannot be back-dated
<!-- id: fleet-002-04 -->
Every applied change and every refused apply SHALL be recordable as an audit
event carrying the principal, the action, the subject, the plan identity, the
key and the outcome. The log SHALL be append-only: an event SHALL NOT be edited
or removed. Sequence numbers SHALL be contiguous from 1, timestamps SHALL NOT go
backwards, and a recorded reason SHALL NOT contain a credential value.

Entries for a plan SHALL be committed only if the whole plan applied, and a
refusal SHALL carry the entry that records it.

#### Scenario: a gap or a rewrite

- **WHEN** a log is constructed with a missing, duplicated or reordered
  sequence number, or with an entry earlier than its predecessor
- **THEN** it is refused as not a log

#### Scenario: a refusal is recorded

- **WHEN** an apply is refused
- **THEN** the refusal carries the log with its refusal entry appended, so the
  attempt cannot be made invisible

#### Scenario: a value offered as a reason

- **WHEN** a refusal reason matches a credential shape
- **THEN** it is refused, and the refusal does not repeat the value
