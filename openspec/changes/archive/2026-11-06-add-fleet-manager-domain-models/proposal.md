# Change: Fleet Manager desired-state models

## Why

Sprint 1 built the boundary and the contracts. Sprint 2 starts the product: the
Fleet Manager has to hold a description of what the fleet should be — which
repositories may run where, which pools exist, which hosts may run them, what
is assigned, what is draining, what is being rolled out — before anything can
plan, apply, or reconcile it (FLEET-001..003).

The failure this change is written against is the one that makes every later
sprint unreviewable: desired state that lives in several places. A runner
process that edits its own host record, a host agent that reports "two runners
running" and thereby *becomes* the database, a pool whose image tag moves under
a revision that claims to be pinned. All three are cheap to build and
impossible to unwind.

## What changes

`fleet-manager/fleet_manager/model.py` — frozen values for repository, host,
pool, assignment, capacity, drain and rollout, plus `DesiredState`, an
aggregate whose every transition returns a **new revision**.

`fleet-manager/fleet_manager/observation.py` — what a host reports, as a type
that desired state cannot be built from. The separation is structural, not a
convention: the two modules do not import each other, and there is no
constructor path from an observation to a desired-state value.

`fleet-manager/fleet_manager/documents.py` — the store's wire form, closed in
both directions (unknown field refused, missing field named), with the one rule
the program states everywhere else: secrets are referenced, never carried.

## What this deliberately does not do

- **No plan or apply.** A transition here is a single operation on one
  aggregate; computing a bounded plan with capacity impact is 2.2 and needs
  this model first.
- **No reconciler.** Nothing polls, retries, or converges. 2.3 builds
  deterministic reconciliation fixtures on top.
- **No persistence.** `to_document()`/`from_document()` define the shape the
  store will keep; the store itself is not in this change.
- **No runtime contact.** Docker and Podman appear as an enum. Nothing here
  opens a socket, reads a file, or shells out.

## Impact

- New: `fleet_manager/model.py`, `fleet_manager/observation.py`,
  `fleet_manager/documents.py`, `tests/test_model_v1.py`, this change package.
- No core file changes; the boundary gate's declared paths already cover
  `fleet-manager/fleet_manager/**`.
