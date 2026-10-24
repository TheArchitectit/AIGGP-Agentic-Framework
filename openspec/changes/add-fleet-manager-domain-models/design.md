# Design: Fleet Manager desired-state models

## Context

FLEET-001 says desired state is separate from execution, and that a runner
process or host must not become the authoritative database. Requirements get
weaker every sprint after this one: the reconciler (2.3), the host agent
(Sprint 3) and the adapters (Sprint 4) all touch the same state. The models are
where the separation either exists or does not.

## Decisions

### Frozen values, revision-per-transition

Every type is a frozen dataclass and every `DesiredState` operation returns a
new aggregate at `revision + 1`. The alternative — mutating one state object in
place — makes "apply against the same revision" (FLEET-002) unstateable: there
is no value to compare against. A new aggregate per transition also makes the
reconciler's fixtures (2.3) trivially deterministic: given a document and an
operation, the output document is fixed.

The cost is allocation on every step. The fleet is tens of hosts, not
thousands; correctness here is worth more than the copies.

### Observations are a separate module, and the separation is tested

`observation.py` holds what a host reports. It does not import `model.py`,
`model.py` does not import it, and neither type has a constructor accepting the
other. A test reads both module sources and fails on an import in either
direction — the same technique the boundary gate uses, and for the same reason:
a rule expressed only in prose is a rule that erodes.

An observation can be *compared* with desired state (2.3), but comparison
returns a diff, never a state.

### Errors name the field and the rule, never the value

This is both an ergonomics decision and a program rule. A model that echoes a
rejected `registration_token` back in an exception message has turned its
diagnostics into a secret store. So every `ModelError` message is built from
field paths and stated rules only.

### Closed documents

`from_document()` refuses unknown fields. The pull toward being lenient is real
— it makes forward compatibility easy — but a store that silently drops fields
it does not understand will one day drop `secret_profile` and keep serving. The
price is a `v2` when the shape changes, which is the same price the contracts
already pay.

### Validation lives in the types

Bounds (`warm_min <= warm_max <= scale_ceiling`), digest pinning, XOR of
`allowed_repositories`/`runner_group`, and the reference shape of
`secret_profile` are properties of the value, enforced in `__post_init__`, not
in the reconciler. Downstream code can then assume them, and a new code path
cannot forget a check.

### `ephemeral: false` is refused now

The v1 capacity contract declares `demand.ephemeral` as `const true`. A pool
model that permitted a long-lived ("persistent") runner would describe a fleet
the closed contract cannot request. Refusing it here keeps the model and the
contract from disagreeing in production.

## Risks

- **The model is wide.** A pool carries ~20 fields because the program's §4.3
  requires them. The alternative — a dict of extras — would move the validation
  into the store and lose the field-named refusals.
- **Rollback digest is a single previous image.** A two-step rollback needs
  history; the rollout ledger keeps one entry per transition, so history exists
  as a sequence of values rather than a field. Named here so nobody assumes a
  stack.
