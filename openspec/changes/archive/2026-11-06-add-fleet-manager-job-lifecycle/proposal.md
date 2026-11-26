# Proposal: Fleet Manager one-job lifecycle (Sprint 4.2)

## Why

Sprint 4.1 gave the thing that acts a shape: eleven calls, eight typed errors,
an image pinned by the digest the fleet standard records, warm defined as a
state, and an ephemeral instance defined by what its command lacks. What the
package still cannot do is say what happens to an instance *after* it is
started — and that is the half the program puts its strongest words on.

RUN-001: one registered runner instance accepts at most one job and is
destroyed after completion, timeout, cancellation, or uncertain disconnect, and
a warm pool MUST NOT keep a previously used job filesystem.

RUN-002: a replacement instance SHALL NOT join capacity until the previous
instance's cleanup is proven or its resources are quarantined, and the cleanup
evidence SHALL include instance identity, image digest, job identity if known,
volume/network disposal result, and timestamps.

Without those as values and rules, "ephemeral" is a flag on a command line and
"clean by proof" is a comment. The first adapter that forgets to quarantine a
failed destroy reintroduces exactly the used-filesystem reuse RUN-001 forbids,
and nothing in the package would notice.

## What changes

- `fleet-manager/fleet_manager/lifecycle.py` — the one-job lifecycle as a
  closed state machine, `CleanupEvidence` (the five things RUN-002 names),
  quarantine as a typed outcome rather than an absence, and resource limits as
  required fields on the ephemeral instance's command.
- `fleet-manager/fleet_manager/adapters.py` — `EphemeralInstance` gains the
  resource limits the command must render, and the states a used instance may
  and may not return to.
- `fleet-manager/tests/test_lifecycle_v1.py` — the suite, floor-pinned, with
  planted failures at every transition the rules have to catch.

## What this deliberately does not do

- **No adapter implementation and no process.** The lifecycle is still a set of
  values and checks; 4.3 is where a controlled job runs on a real runtime and
  the receipts are produced by a host rather than by a test.
- **No change to the closed error taxonomy.** The eight kinds of Sec. 5.2 are
  already closed; this change makes lifecycle failures land in them rather than
  inventing a ninth.
- **No host-side evidence collection.** `CleanupEvidence` is the shape the
  evidence must have. Where the volume and network disposal results come from —
  `podman volume ls`, a network inspect, a declared absence — is the adapter's
  job in 4.3, not this one's.
