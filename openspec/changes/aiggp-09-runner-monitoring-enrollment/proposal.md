## Summary

Define the AIGGP runner protocol: authenticated short-lived enrollment, declared capabilities and trust classes, signed desired state, secret-class boundaries, continuous monitoring with verified heartbeats, and lifecycle operations (rollout, canary, drain, rollback) - all emitting kernel-verifiable evidence, with monitoring built into the protocol rather than bolted on beside it.

## Problem

The Mission Control audit showed what unmanaged runner control looks like: an unauthenticated runner-control surface, where anyone who can reach the endpoint can drive execution. Meanwhile the ai01 monitor-of-runners spec exists only as a local side monitor - useful, but a monitor that invents its own picture of truth instead of verifying protocol evidence is the same mistake in a smaller hat. The superseded fleet package had good runner machinery (enrollment, secret classes, rollout, canary, drain, rollback, drift detection) trapped inside a paid-tier design. This spec frees that machinery into the open protocol.

## Desired outcomes

- Runners enroll with short-lived, authenticated credentials; long-lived static runner secrets are eliminated.
- Each runner declares capabilities and a trust class mapping to AIGGP-05 isolation levels; work is scheduled only to runners whose class covers the workload.
- Desired state (what to run, which bundle, which images) is signed; runners verify before executing and reject unsigned or stale instructions.
- Secrets are divided into declared classes; a runner receives only the classes its trust level and current workload require, delivered ephemerally.
- Monitoring is protocol-native: verified heartbeats and execution evidence flow to the ledger; absence of verifiable evidence marks a runner suspect and triggers drain.
- Lifecycle operations (rollout, canary, drain, rollback) are first-class, rehearsed, and evidenced.
- A compromised or invalid runner is provably rejected: the acceptance suite includes a hostile-runner drill.

## Product boundary

This spec owns the runner protocol and its monitoring. It does not make Mission Control an authority: Mission Control displays runner state and triggers workflows, but runner truth comes from verified evidence. Isolation level definitions are AIGGP-05's; this spec consumes them as trust classes. Forge-specific runner setup is AIGGP-07's runner standard.

## Users and calling systems

- Fleet operators enrolling and lifecycle-managing runners.
- The kernel verifying enrollment, heartbeats, and execution evidence.
- Mission Control rendering runner state from ledger data (read-only on truth).
- Workload schedulers (AIGGP-02 container runs, gate execution) requesting trust-class-appropriate runners.

## Success measures

- Hostile-runner drill: a runner with forged or expired credentials is rejected and its evidence refused, proven in CI.
- Drain drill: a suspect runner is drained and its workloads rescheduled without verdict loss.
- 100 percent of runner-executed results carry envelopes from an enrolled, in-class runner.
- Rollback drill: a bad bundle rollout is rolled back with ledger evidence of both directions.

## Risks

- Enrollment becomes the new single point of failure. Control: enrollment service is small, its decisions are ledger-recorded, and offline queueing lets enrolled runners keep working through an enrollment outage.
- Monitoring theater: dashboards showing green while runners rot. Control: monitor outputs are kernel-verified evidence, and absence of evidence is itself an alertable state.
- Secret-class sprawl. Control: classes are few, named, and bundle-declared; new classes require spec amendment.
