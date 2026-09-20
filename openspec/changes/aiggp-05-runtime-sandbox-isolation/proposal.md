## Summary

Define and implement sandbox isolation levels for agent-driven execution, with declared per-workload levels, fail-closed behavior on containment failure, escape-attempt fixtures in conformance, and isolation level recorded in every evidence envelope.

## Problem

Classification and mediation (AIGGP-03/04) decide what may run; nothing yet guarantees that what runs stays inside its lane. Guardrails main has sandbox work in progress, but "sandbox" without declared levels and escape testing is a marketing word. The platform promise - prove what was checked, under which policy, against which subject - is incomplete without "inside which containment."

## Desired outcomes

- A small set of named isolation levels (observer, restricted, contained, ephemeral) with precise capability definitions: filesystem, network, process, secrets, and persistence rights per level.
- Workloads declare their required level in the bundle; the runtime enforces it or refuses to run.
- Containment failure at any component fails closed: execution stops, the event is evidence, and the workload's verdict is ERROR, never degraded-pass.
- Conformance includes escape fixtures: attempts to read outside the filesystem scope, reach the network under default-deny, escape the process namespace, and access undeclared secrets. Any success fails the level's certification.
- Every envelope records the isolation level and runtime identity, so evidence consumers know the walls the result was produced behind.

## Product boundary

This spec owns execution containment for agent-driven workloads. It does not classify content (AIGGP-03/04) and does not define runner fleet enrollment (AIGGP-09), though runner trust classes consume these levels. Container image supply-chain policy is referenced, not defined here.

## Users and calling systems

- Guardrails runtime module executing mediated actions.
- Runner modules executing workloads at a trust class (AIGGP-09 consumes levels).
- The spec-coherence container runtime (AIGGP-02) aligning its isolation claims with named levels.

## Success measures

- All escape fixtures fail to escape at every certified level, proven in CI per release.
- Any induced containment fault produces ERROR verdicts and evidence, never green.
- 100 percent of envelopes carry isolation level and runtime identity.
- Level definitions are public and stable enough for third-party runners to certify against.

## Risks

- Level proliferation until "sandbox" means nothing again. Control: four levels, fixed; new levels require a spec amendment.
- Performance cost of strong containment pushes users to weaker levels. Control: measure and publish overhead per level; make restricted-to-contained the comfortable default band.
- Host-specific behavior makes claims unverifiable. Control: conformance fixtures run on reference hosts and in CI; host deviations are reported, not hidden.
