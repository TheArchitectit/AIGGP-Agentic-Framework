# Proposal: runner-toolchain-requests

## Why

Fleet runners cannot obtain the tooling a job needs. The gap is not
permissions — it is that nothing knows a runner is missing something until a
job fails.

Measured on ucs03, 2026-10-04, read-only against the live fleet:

- **Stock lanes carry almost nothing.** `ghcr.io/actions/actions-runner@sha256:5036…`
  contains `git`, `python3`, `jq`, `bash` and nothing else — no `node`, `npm`,
  `cargo`, `go`, `gcc`, `gitleaks`, and no `pip3` module. Five lanes run on it
  (`ucs03-zhm`, `ucs03-zombietoss`, `ucs03-ddfgrpg`, `ucs03-zdiver`, and the
  framework's own `devgate` lane).
- **Toolchain lanes get theirs baked into the image.** `ucs03-mc` carries
  node/cargo/rustc/gitleaks, `ucs03-game` carries go/gcc. The fleet's twenty
  locally-built images span 1.56 GB (stock) to 4.96 GB (`ucs03-biteclub`),
  which is the whole provisioning mechanism: a human rebuilt an image.
- **The consequence is a per-job tax.** `TheArchitectit/zombie-hero-match`
  runs the stock image, so its `ci.yml` calls `actions/setup-node@v7` and then
  `npm install --no-save typescript@5` on **every job**, to obtain a toolchain
  that a sibling lane already has baked in. The workflow hardcodes the answer,
  so the knowledge lives in YAML and drifts silently from what the image holds.
- **Requests are currently unexpressible.** The hub registry schema
  (`hub/schema/runners.schema.json`) closes itself to undeclared keys, and no
  runner field records a capability gap. A job that needs `cargo` has no way to
  say so; it fails, and the operator learns about it from a red run.

So the fleet can install software — runners are uid 1001 with `NOPASSWD: ALL`
and full egress (`archive.ubuntu.com`, `nodejs.org`, `registry.npmjs.org`,
`github.com`, `static.rust-lang.org` all reachable) — but it can only do so by
someone editing a workflow or rebuilding an image by hand. Nothing in the
system turns "I am missing a tool" into a decision a human makes.

## What Changes

- **A runner reports a capability gap, never a remedy.** The spoke adds
  `missing_tools` to its existing heartbeat: a list drawn from a fixed
  vocabulary, describing what the image lacks. It never names a package to
  install, a URL to fetch, or a command to run. This keeps the request a
  statement about the fleet and keeps arbitrary execution out of the system.
- **The hub records requests as first-class state.** A new `toolchain_requests`
  collection alongside `runners`, with lifecycle (`open` → `approved` /
  `denied` / `fulfilled`), the requesting lane, the reason, and the decision's
  author and timestamp. The hub is the system of record because it is already
  the only component that authenticates every runner (per-runner heartbeat
  tokens), knows each lane's `repo` and `image_digest`, and holds the audit
  trail. Mission Control reads and decides; it does not own fleet state.
- **Mission Control gains a queue and an approval action.** A dashboard route
  lists open requests across lanes; an operator approves or denies with a
  reason. MC already has authentication, a dashboard module, and a
  React/Inertia frontend, and gains a hub client.
- **Approval produces a digest-pinned image change, never a live install.**
  An approved request is fulfilled by rebuilding the lane's image with the
  toolchain added and recording the new digest — at which point the existing
  `image_digest` field updates and `image_pin_divergence` (img-cycle-05) keeps
  working as the drift detector it is. A request that approved itself into a
  mutable runner would make both fields meaningless and destroy the audit
  trail the fleet currently has.
- **A request cannot be decided by the host that raised it.** The approve and
  deny actions carry operator auth distinct from the per-runner heartbeat token.
  Today the hub has no user authentication at all — only runner tokens — and
  this change is where that gap becomes dangerous rather than merely untidy.

## Impact

- Affected specs: `runner-toolchain-requests` (new capability, `mon-tc-*`
  namespace).
- Affected code (framework side): `hub/registry.py`, `hub/server.py`,
  `hub/schema/runners.schema.json`, `scripts/runner-heartbeat.sh`.
- Affected code (Mission Control side, separate repo `mission-control-rs`):
  a hub client under `src/adapters/`, a route beside `src/api/dashboard.rs`,
  and a frontend route.
- Affected specs (external repo): `mission-control-rs`'s own OpenSpec package
  governs the MC-side work; this change governs the hub-side contract both
  sides depend on.
- Out of scope: running any installation on a live runner. The hub never
  executes a package manager, and no remediation path in this change performs
  one. Also out of scope: `image_reason` / `image_pin_divergence` semantics,
  which already exist and are unchanged.