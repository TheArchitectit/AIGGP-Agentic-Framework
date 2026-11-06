# Tasks: Fleet Manager adapter contract (Sprint 4.1)

## 1. The contract as data

- [x] 1.1 `ADAPTER_CALLS` — the eleven Sec. 5.2 calls, in the order the program
      lists them, with the mutating subset named separately
- [x] 1.2 `check_contract()` — structural conformance, every missing member in
      one refusal, required parameters checked by name, `**kwargs` not accepted
      in place of a name, runtime mismatch refused
- [x] 1.3 `AdapterContract` — the value returned on success

## 2. Errors

- [x] 2.1 `ErrorKind` — exactly the eight kinds of Sec. 5.2
- [x] 2.2 `AdapterError` — kind as the enum, detail refused when credential
      shaped and never echoed, message carrying the kind
- [x] 2.3 `classify()` — unexpected exception to runtime failure, type named,
      message dropped

## 3. The image pin

- [x] 3.1 `image_reference()` — repository plus digest, a tag refused
- [x] 3.2 `STANDARD_RUNNER_IMAGE_DIGEST` — the digest the fleet standard
      validated, bound to `templates/runner/self-hosted-runner.container` by a
      skip-guarded test

## 4. Instances and the warm pool

- [x] 4.1 `InstanceState` and `WarmInstance` — warm is `PREPULLED` or
      `STOPPED_CLEAN`, nothing else
- [x] 4.2 `WarmPool` — pool id and digest on every instance, bounds both ways,
      shortfall reported
- [x] 4.3 `EphemeralInstance` — anonymous work dir, removed on exit, no durable
      volume, registration reference through an environment file only
- [x] 4.4 `command()` — the rendered argument list as a value, never executed

## 5. Evidence

- [x] 5.1 `fleet-manager/tests/test_adapters_v1.py` — 55 tests, floor-pinned
- [x] 5.2 Planted mutation battery against `adapters.py` — 33/33 killed; M25's
      survivor was a dead duplicate guard in `WarmPool.admit()`, deleted
- [x] 5.3 `docs/qa/2026-10-24-fleet-manager-adapter-contract.md` — gates,
      mutation table, residuals, and what the push's own secret gate caught

## 6. Residuals to name in the record

- [x] 6.1 No adapter implementation: 4.2 implements the contract for Podman (the
      only runtime this fleet has, per the operator: podman, rootless) and
      Docker, and until then conformance is proven against fakes
- [x] 6.2 No image build: the runner standard rejects hand-rolled runner images
      and forked entrypoints, so the "pinned ephemeral runner image" is the
      stock official image at the standard's digest, made ephemeral by the
      instance contract
- [x] 6.3 The rendered command is verified as a value; no process is started in
      this change, so "the container actually starts" is 4.3's evidence, not
      this box's
