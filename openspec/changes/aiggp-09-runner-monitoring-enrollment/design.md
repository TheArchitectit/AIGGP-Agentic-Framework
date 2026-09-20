## Design principles

- No evidence, no trust: a runner is exactly as trustworthy as its last verified envelope.
- Short-lived everything: enrollment, credentials, secret delivery, and desired-state validity all expire.
- Signed instructions, verified before execution: runners authenticate what they are told, not just who tells them.
- Protocol-native monitoring: observation is a property of the protocol, not a side process guessing.

## Locked decisions

- Enrollment: short-lived certificates or tokens with rotation; static runner secrets are prohibited.
- Trust classes: map 1:1 to AIGGP-05 isolation levels; scheduling requires class coverage of the workload's declared level.
- Desired state: signed by the control side, verified by the runner, carrying bundle digest, image digests, and validity window. Stale or unsigned state is refused.
- Secret classes: declared set (for example: none, read-only repo, deploy-capable); ephemeral per-workload delivery; no ambient credentials on runners.
- Heartbeats: signed, ledger-recorded; missing heartbeats transition runner state to suspect, then drained.
- Lifecycle: rollout with canary stages, drain with workload migration, rollback to prior signed state - all evidenced.
- Offline queueing: enrolled runners cache signed desired state and continue within its validity window during control outages.

## Major components

1. Enrollment service (issuance, rotation, revocation).
2. Runner agent (verification of signed state, evidence emission, heartbeat).
3. Scheduler (class-aware workload placement).
4. Secret broker (class-scoped ephemeral delivery).
5. Ledger-integrated monitor (heartbeat and execution evidence verification).
6. Lifecycle controller (rollout, canary, drain, rollback).
7. Drill harness (hostile runner, drain, rollback).

## Trust boundaries

- The enrollment service never executes workloads; the scheduler never holds secrets; the broker never schedules.
- Mission Control triggers lifecycle workflows through authenticated requests; the kernel validates the resulting evidence. The UI cannot declare a runner trusted.
- Runners are hostile until enrolled, and enrolled-until-proven-otherwise on every heartbeat.
