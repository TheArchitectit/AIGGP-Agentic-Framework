## Requirement: short-lived authenticated enrollment

Runners SHALL enroll with short-lived rotating credentials. Static long-lived runner secrets SHALL be prohibited.

### Scenario: static secret rejected

Given a runner presenting a long-lived static credential, when enrollment is evaluated, then it SHALL be rejected and the attempt logged.

### Scenario: expired credential

Given a runner whose enrollment expired, when it presents evidence or heartbeats, then they SHALL be refused and the runner SHALL transition to unenrolled.

## Requirement: declared capabilities and trust class

Each runner SHALL declare capabilities and a trust class at enrollment. The scheduler SHALL place workloads only on runners whose class covers the workload's declared level.

### Scenario: under-classed scheduling attempt

Given a workload requiring contained level and a runner at restricted class, when scheduling is attempted, then it SHALL be refused.

## Requirement: signed desired state

Desired state SHALL be signed, carry bundle and image digests plus a validity window, and SHALL be verified by the runner before execution. Unsigned or stale state SHALL be refused.

### Scenario: stale instruction

Given desired state past its validity window, when the runner evaluates it, then execution SHALL be refused and the refusal evidenced.
