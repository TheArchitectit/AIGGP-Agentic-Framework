# Proposal: Fleet Manager adapter contract (Sprint 4.1)

## Why

Sprint 3 closed with two hosts reconciling a signed no-op desired state. Nothing
in the package can yet act on a host: `operations` names what an adapter may be
asked to do and `reconcile` says which changes should be submitted, but there is
no agreed shape for the thing that actually starts and destroys a runner. The
program's Sec. 5.2 fixes that shape as a list of eleven calls, and Sec. 5.3
fixes the execution property that makes the list safe: one job per instance, and
a warm pool that never keeps a used job filesystem.

Without the contract written down and checked, the first Docker adapter defines
the interface by being first, the Podman adapter copies whatever it got away
with, and "the same runner image, entrypoint contract, cleanup contract and job
receipt schema SHOULD apply to both runtimes" becomes a hope. This change makes
the contract a value the package can check an implementation against, without
calling it and without importing a runtime.

## What changes

- `fleet-manager/fleet_manager/adapters.py` — the contract as data
  (`ADAPTER_CALLS`, the mutating subset), a structural checker
  (`check_contract`), a closed error taxonomy (`ErrorKind`, `AdapterError`,
  `classify`), the pinned runner image reference, and the ephemeral instance and
  warm-pool values.
- `fleet-manager/tests/test_adapters_v1.py` — the suite, floor-pinned, with
  planted fakes for every refusal.

## What this deliberately does not do

- No Docker or Podman adapter implementation. Box 4.1 is the contract; 4.2 is
  the lifecycle that implements it.
- No process execution. The module builds a command as a value and never runs
  it; the adapter that runs it arrives in 4.2 and will be the only thing in the
  package with a subprocess in it.
- No image build. The repository's runner standard (`templates/runner/README.md`)
  explicitly says not to hand-roll a runner image and not to fork the shared
  entrypoint. The "pinned ephemeral runner image" of this box is the stock
  official image at the digest the standard already validated, made ephemeral by
  the instance contract rather than by a fork.

## Impact

- New module and suite inside the `fleet-manager/` boundary; no core change.
- One new constant (the standard's pin) that a test binds to the quadlet, so the
  two cannot drift.
- No schema change: pools already carry `runtime`, `image_digest`, `warm_min`,
  `warm_max`, `scale_ceiling`, the timeouts, and `ephemeral: true`.
