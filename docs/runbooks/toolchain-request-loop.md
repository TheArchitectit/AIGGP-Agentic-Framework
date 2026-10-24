# Operator runbook — the toolchain request loop

This is the operator-facing description of the loop required by
`add-runner-toolchain-requests` (task 6.8). It states what each actor may do,
where the truth lives, and — the point operators most often get wrong — what an
approval does and does not do.

## The loop in one line

A lane reports the tool it lacks → the hub records the request → an operator
approves or denies it in Mission Control → **approval produces an image
rebuild of that lane; it never installs anything live on a host.**

## Actors and what each may do

| Actor | May | May not |
|---|---|---|
| Lane (probe) | report a missing tool and its coverage state | decide a request; carry a credential class it was not issued |
| Builder | report `built` and `converge` (with evidence) | decide a request |
| Operator (via Mission Control) | `approve` / `deny` with a note on deny | mutate a lane image directly |
| Hub | record state, enforce the transition table, expose the read | invent a transition the table does not contain |

The hub is the **system of record**. Mission Control is a surface over it:
it holds no toolchain table, no cache, and no background refresh. Every number
and state an operator sees is read from the hub at request time; an empty queue
and an unreachable hub are rendered as different things and must never be
conflated.

## States

`open → approved → built → fulfilled`, or `open → denied`.

- `denied` re-reported inside the **14-day** suppression window stays `denied`
  and increments the suppression counter; reported after it, the row reopens.
- An `approved` request with no build report after **24 hours** is shown as
  outstanding with its age. A rebuild that has not happened by then is itself
  the finding.
- Coverage is `reported`, `never-reported`, `stale` (silent for **900 s** —
  three 300-second heartbeats) or `probe-failed`. A lane with no open requests
  is **not** evidence its toolchain is complete unless its coverage state is
  `reported` and every request for it is fulfilled.

## Deciding a request

Mission Control POSTs to the hub's `/toolchain/decide` with the request id,
the action, the operator credential, the actor claim (`actor`, `principal`,
`timestamp`, `nonce`) and the `expected_version` the operator saw:

- the credential's class is classified **server-side**; a credential not
  carrying `toolchain:decide` is refused as `rejected_credential_class`
- `deny` without a note is refused (`400 deny_requires_note`); notes are capped
  at 512 characters and refused, never truncated
- a stale view is refused with `409 version_conflict` carrying
  `current_version` — re-read and decide again
- no success is synthesised locally, and there is no local retry that could
  double-apply

Never log the nonce or the credential.

## What approval does — and does not — do

Approval changes the row to `approved`. It does **not** install a package on a
running host, restart a service, or mutate a container in place. The lane's
next build produces a new **image**, and the new image digest is what carries
the change. That is deliberate: an approval that mutated a live host would be
unreviewable, unreproducible, and impossible to roll back by digest.

After the rebuild, the builder reports `built`, and `converge` marks the row
`fulfilled` only when the lane's probe reports the tool present in the new
image. A refused or failed report never counts as clean.

## Evidence an operator should expect

- a decision row with actor, principal, timestamp and nonce recorded by the hub
- for an approval: a new image digest and a build report naming the request
- for a denial: a note (required) and a suppression entry
- coverage read from the lane's own reports — never inferred from silence

Deployment topology, hosts and credentials are deliberately not in this
repository; the private infrastructure record holds those.
