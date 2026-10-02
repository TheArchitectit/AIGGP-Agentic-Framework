## Required conformance fixtures

- Fixture A: filesystem escape attempt - fails, recorded.
- Fixture B: network escape under default-deny - fails, recorded.
- Fixture C: process-namespace escape attempt - fails, recorded.
- Fixture D: undeclared secret access - fails, recorded.
- Fixture E: host missing mechanism - workload refused with diagnostic.
- Fixture F: induced runtime fault - ERROR verdict, no green.

## Release acceptance criteria

- All fixtures pass on reference hosts and in CI; envelopes carry level and runtime identity; certification report published per release.

## Open questions requiring owner decisions

### Q9.1 — Reference container backend

**ANSWERED 2026-10-01 (owner).**

**Rootless Podman is the reference backend.** The shipped fleet runner
and house container security model (tailnet-IP-only bind) already run
rootless Podman; it is the natural anchor for the escape suite
("&nbsp;Build the escape suite alongside the first enforcer, but not
after, so the fixtures define what the levels mean&nbsp;" — handoff).

**Docker is supported as a first-class option, not a walk-won't-have.**
The `devgate-product-tiers-fleet-manager` package already flagged
"runtime adapters (Docker/Podman first, ARC later)" — this answers that
with a binding decision rather than leaving it open: Podman is the
reference *implementation* (escape fixtures run first-class against
it), Docker is the *supported non-reference* (contract-level
verification, smaller escape suite, no claim that Docker holds the
same rootless namespace contract in the fixture set). When Docker
support ships, the capability matrix (handoff) marks which levels are
verified on Docker vs Podman.

Rejected: "rootless Docker as reference" (B) — fleet already depends on
rootless Podman as the shipped runner; switching the reference would
mean re-validating every escape fixture against new cgroup/userns
defaults without a consumer to justify the churn. "Backend-agnostic"
(C) — the escape fixtures from the handoff's build-as-you-go principle
want a concrete backend to test against from day one.

### Q9.2 — Does the `ephemeral` level require dedicated hosts at launch?

**ANSWERED 2026-10-01 (owner).**

**Hybrid, tier-scaled, either-or allowed per deployment class.** The
proposal's level-correctness spine (levels are *capability-defined*)
does not dictate one physical deployment posture; the question is
whether physical co-residency is required to make "no persistence"
honestly true, and the answer differs by who is buying the product.

| Deployment tier | Ephemeral posture (recommended) | Why |
|---|---|---|
| **Personal** | Shared "contained" infrastructure is acceptable. Fresh ephemeral namespace per run, namespace teardown between runs. | Solo deployer, one trust boundary, one blast radius (theirs); cost of dedicated hosts is disproportionate to risk. |
| **Business** | Either-or allowed; **dedicated hosts available as an opt-in upgrade**. Shared contained is the default; a business that sets `ephemeral_hosts: dedicated` gets zero co-residency. | Teams have real state-carry risk (multi-tenant workloads across one org) but a shared-cost baseline is normal. Opt-in matches the aiggp-00 Q1 crash-radius rule (dedicated hosts are an org-scale infra decision — understand before you flip). |
| **Enterprise** | Dedicated hosts at launch mandatory for `ephemeral` workloads. | Enterprise buys the "no persistence" claim as literal zero-co-residency; a shared kernel / containerd can leak across tenants via same-machine side channels (cache, `/tmp` residue, kernel niche). Any workload declared `ephemeral` on enterprise must not co-reside. |

Invariant, binding regardless of tier: **a deployment whose `ephemeral`
posture is shared must be told so.** The capability matrix (handoff)
discloses which posture a given tier's `ephemeral` level actually
provides — cannot be silent about this — so an enterprise buyer never
*thinks* they're getting dedicated hosts when they're on shared. That
disclosure itself is a blast-radius mitigation: a creep from
"shared-ephemeral" to "dedicated-ephemeral" is a contract change, so
it's opt-in with a schema-version bump on the capability matrix,
never default-on.

Rejected: "dedicated hosts mandatory at launch for all tiers" (A
uniform) — would make `ephemeral` unreachable at personal tier and
doesn't answer the deployment-class question the user asked. "Shared
only" (B uniform) — enterprise buyers legitimately buy zero-co-residency
as the definition of `ephemeral`; they need somewhere to put it.

## Handoff

Build the escape suite alongside the first enforcer, not after: the fixtures define what the levels mean. Publish the capability matrix early - it is the contract every other spec (and every third-party runner) builds against.
