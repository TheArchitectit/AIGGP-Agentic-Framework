# Proposal: runner-toolchain-requests

> Revised after external architecture review, 2026-10-03 CDT. See `design.md`
> §Findings this revision corrects.

## Why

Fleet runners cannot obtain the tooling a job needs, and nothing in the system
turns a missing tool into a decision a human makes.

Measured 2026-10-04 between 02:40 and 02:55 UTC, read-only against the images
the fleet's own service definitions reference. Evidence references are held in
private operational documentation; this repository is public, so lane names,
host aliases, image sizes and host posture are deliberately not reproduced here.

- **The stock runner image carries almost no toolchain** — a shell, a script
  interpreter, a JSON reader and `git`. Several lanes run on it unmodified.
- **Provisioned lanes carry their toolchain baked into the image.** Fleet-wide,
  locally-built runner images span a factor of roughly three in size, which is
  the entire provisioning mechanism: a human rebuilt an image.
- **The consequence is a per-job tax.** A stock-lane workflow calls a
  `setup-node` action and installs a compiler package on **every job**, to
  obtain a toolchain a sibling lane already has baked in. The workflow
  hardcodes the answer, so the knowledge lives in YAML and drifts silently from
  what the image actually contains.
- **Requests are currently unexpressible.** The hub registry schema closes
  itself to undeclared keys, and no runner field records a capability gap. A
  job that needs a tool has no way to say so; it fails, and the operator learns
  about it from a red run rather than from a queue.

So the fleet can install software — a runner has administrative rights inside
its own container and unrestricted egress — but it can only do so by someone
editing a workflow or rebuilding an image by hand.

## What Changes

- **A runner reports a capability gap, never a remedy.** The spoke adds
  `missing_tools` to its existing heartbeat: the set difference of the lane's
  **required toolchain profile** and the tools **observed in the runner image**.
  It never names a package to install, a URL, or a command. This keeps the
  request a statement about the fleet and keeps arbitrary execution out of the
  system.
- **The hub records requests as first-class state**, with a guarded state
  machine, a version counter, and an append-only audit history. The hub is the
  system of record for *requests* because it already authenticates every runner
  and holds each lane's identity. It is not the system of record for runners:
  Mission Control keeps its own registry, and the two are linked explicitly
  rather than merged.
- **Mission Control gains a queue and an approval action.** A page lists open
  requests with lane context; an operator approves or denies with a reason.
  Mission Control holds no toolchain tables, and an unreachable hub renders as
  unreachable with a timestamp — never as an empty list.
- **Decisions are attributable and cannot be made by a runner.** Mission Control
  authenticates the human and calls the hub with a dedicated
  `toolchain:decide` credential carrying a signed actor claim. The hub refuses
  heartbeat tokens, runner keys, builder credentials and ordinary API keys, and
  refuses a replayed nonce.
- **Fulfillment is an evidence chain, not a digest.** A build job — holding its
  own builder credential — reports a profile id, build id, builder identity and
  digest, moving the request to `built`; a later heartbeat reporting that digest
  *and* a passing tool probe moves it to `fulfilled`. Nothing executes a package
  manager on a running runner.
- **Absence is never reported as health.** Each lane carries a report-coverage
  state so a lane that never reported is distinguishable from one whose
  toolchain is complete, and an approved-but-unbuilt request is surfaced as
  outstanding with its age.

## Impact

- Affected specs: `runner-toolchain-requests` (new capability, `mon-tc-*`
  namespace).
- Affected code (framework side): `hub/registry.py`, `hub/server.py`,
  `hub/schema/runners.schema.json`, `scripts/runner-heartbeat.sh`.
- Affected code (Mission Control side): a hub adapter under `src/adapters/`, a
  fleet route under `src/api/fleet/`, route registration in
  `src/router/builder.rs`, and an Askama page.
- Affected specs (external repository): the Mission Control companion change
  governs the MC-side work, including the auth-gate classification of the new
  decide route. This change governs only the hub-side contract both sides
  depend on.
- **Explicitly unchanged:** the registry's evaluator image fields
  (`image_digest`, `image_pin_divergence`) and the img-cycle-05 divergence
  check. Those describe the coherence evaluator image, not runner lane images;
  lane image identity gets separate fields. See `design.md` §F1.
- Out of scope: running any installation on a live runner, merging the two
  runner registries, per-operator accounts, and changing the existing
  evaluator-image semantics.

## Honest limit

This capability makes operator decisions attributable and the images they
produce digest-pinned. It does not make a runner hermetic: a job on a lane can
still install software for itself. The boundary is on the decision channel and
the audit trail, not on the runner.