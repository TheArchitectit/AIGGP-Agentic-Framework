# Spec: Fleet Manager reconciliation

## ADDED Requirements

### Requirement: Reconciliation is a deterministic diff, never a state
<!-- id: fleet-003-01 -->
A reconciliation SHALL compare one desired-state revision with one observation
per host and SHALL return a diff: the drifts it found, the changes it would
submit, and the work it deferred with the reason. It SHALL NOT produce a new
desired-state revision; the changes SHALL be the same `Change` values that
planning and applying accept.

The reconciliation SHALL have an identity that is a digest of exactly its base
revision, the observations and the convergence limits, recomputed when the
value is constructed. Two reconcilers reading the same revision and the same
reports under the same limits SHALL produce the same identity and the same
document, byte for byte.

#### Scenario: two runs over the same fixtures

- **WHEN** the same fixtures are reconciled twice, in processes with different
  hash seeds
- **THEN** both produce the same reconciliation identity and the same document

#### Scenario: an edited reconciliation

- **WHEN** a reconciliation is constructed whose identity does not match its
  revision, reports, limits and halt state
- **THEN** it is refused as an edited value

#### Scenario: an order that is not a total order

- **WHEN** a reconciliation is constructed with drifts out of `(kind, host,
  pool)` order, or with submitted changes that are not the candidates that
  were not deferred
- **THEN** it is refused

### Requirement: Convergence is bounded and every deferral is named
<!-- id: fleet-003-02 -->
A reconciler SHALL submit at most the declared number of drains, replacements
and host mutations in one batch, and SHALL respect each affected pool's
disruption budget for destructive changes. A candidate that does not fit SHALL
be returned as a deferral carrying the change and the reason, naming the cap
that was reached; it SHALL NOT be dropped.

A limit of zero SHALL submit nothing. A halted reconciler SHALL submit nothing
while still returning the drifts and the deferrals, so the work it would have
done is preserved for controlled recovery.

#### Scenario: more work than the cap

- **WHEN** a pool is three slots below its warm floor and the host-mutation cap
  is two
- **THEN** two assignments are submitted and the third is deferred with a
  reason naming the cap

#### Scenario: a halted reconciler

- **WHEN** the same shortfall is reconciled with `halted` set
- **THEN** no change is submitted, every candidate is deferred with the halt as
  its reason, and the drifts are unchanged

#### Scenario: a pool's disruption budget

- **WHEN** two draining hosts may complete and their shared pool allows one
  parallel disruption
- **THEN** one drain is submitted and the other is deferred naming the pool's
  budget

#### Scenario: every candidate accounted for

- **WHEN** a batch is bounded
- **THEN** each candidate appears exactly once, as submitted or as deferred

### Requirement: The reconciler never disturbs work it cannot prove finished
<!-- id: fleet-003-03 -->
The reconciler SHALL NOT emit a destructive change against a host whose report
shows a runner, SHALL NOT assign work to a host that has not reported, SHALL
report a runner that no assignment accounts for without touching it, and SHALL
NOT adopt a report from a host that is not in the desired state.

More than one report for the same host SHALL be refused, because deciding
between them is not this layer's guess.

#### Scenario: a drain with a runner still reported

- **WHEN** a draining host has no assignment but its report lists a runner
- **THEN** the drift is `drain_blocked`, and no `complete_drain` is submitted

#### Scenario: an unmanaged runner

- **WHEN** a host reports a runner the desired state does not account for, with
  or without a job
- **THEN** it is reported as `unmanaged_runner` and no change touches it

#### Scenario: a silent host

- **WHEN** an active host has no observation
- **THEN** it is reported as `host_not_reporting` and receives no assignment

#### Scenario: an unknown host

- **WHEN** a report arrives from a host that is not in the desired state
- **THEN** it is reported as `unknown_host` and is not adopted

#### Scenario: two reports for one host

- **WHEN** two observations carry the same host id
- **THEN** reconciliation is refused naming the conflict

### Requirement: Deterministic fixtures are the evidence
<!-- id: fleet-003-04 -->
The reconciliation SHALL be exercised by fixtures that are data: a desired-state
document, the reports, the limits and the halt state, with expected drifts,
changes and deferrals written by hand. Each fixture SHALL be compared exactly,
including order, and the same fixture SHALL produce the same document on every
run.

The report form used by fixtures SHALL be closed: a missing field SHALL be
named, an unknown field SHALL be refused, and a value that is not a report
SHALL be refused rather than crashed on.

#### Scenario: a fixture whose expectation drifts

- **WHEN** the reconciler's output for a fixture differs from the hand written
  expectation in content or order
- **THEN** the suite fails for that fixture by name

#### Scenario: a malformed report

- **WHEN** a fixture or caller supplies a report with a missing or unknown field
- **THEN** it is refused naming the field, and no reconciliation is produced
