# runner-toolchain-requests - OpenSpec change package

> Repo: `TheArchitectit/AIGGP-Agentic-Framework`  ·  Branch: `feature/runner-toolchain-requests`
> Change path: `openspec/changes/add-runner-toolchain-requests/`
> Validation: `openspec validate --all --strict` = 32 passed, 0 failed (31 before this change)
> Capability: `runner-toolchain-requests` (new)  ·  Requirement IDs: `mon-tc-01` .. `mon-tc-05`

---

## 1. Proposal

*source: `openspec/changes/add-runner-toolchain-requests/proposal.md`*

### Proposal: runner-toolchain-requests

#### Why

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

#### What Changes

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

#### Impact

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

---

## 2. Design

*source: `openspec/changes/add-runner-toolchain-requests/design.md`*

### runner-toolchain-requests — Design

#### Context

A fleet runner that lacks a toolchain cannot ask for one. This design adds the
request channel, the decision surface, and the fulfillment path that keeps the
digest-pinned property the fleet already has.

The measured facts the design rests on are in `proposal.md` §Why. The three
that constrain it:

1. Stock runner image = `git`, `python3`, `jq`, `bash`. Nothing else.
2. Runners are uid 1001 with `NOPASSWD: ALL` and unrestricted egress.
3. Provisioning happens by rebuilding a lane image and repointing a quadlet.

#### Decisions

### D1 — The hub owns request state; Mission Control owns the decision

The hub is the only component that authenticates every runner (per-runner
heartbeat tokens, salted hashes at rest per mon-sec-02). Adding `missing_tools`
to the existing heartbeat needs no new credential and no new network path.

The alternative — runners POST directly to MC — would create a second source of
truth for fleet state. This fleet already carries that class of drift: ten
registry rows that recorded `OWNER/<repo>` placeholders instead of resolved
repositories (repaired 2026-10-04), and helper scripts that had drifted from
their checkout. MC reads and decides; the hub remembers.

**Rejected:** MC as system of record. It has no hub client today, and putting
fleet state there would mean two components disagreeing about which runners
exist.

### D2 — A request states a gap, never a remedy

The runner reports what it lacks: `missing_tools: ["cargo"]`. It does not name
a package, version, URL, or command.

This is the security boundary of the whole feature. With free text, the
approval button becomes "run this string as root on a machine that executes
private-repo code" — a remote package installer with a UI. With a closed
vocabulary, approval is "add toolchain profile X to lane Y", a decision about a
reviewed artifact.

The vocabulary is declared in the spec and versioned with it. An unknown tool
name is rejected at the boundary, not stored and not displayed.

### D3 — Approval means a pinned image change, not a live install

An approved request is fulfilled by rebuilding the lane image with the toolchain
added and recording the resulting digest. It is not fulfilled by
`apt-get install` on the running runner.

If approval mutated a live runner, then what a lane contains would depend on
what got clicked, in what order, and on which of its jobs asked first. That
breaks the property `image_digest` records and `image_pin_divergence`
(img-cycle-05) detects — both would become noise — and it would leave no
artifact to audit.

**Rejected:** live install. It is the intuitive reading of "approve software
installation", and it is the one that costs the fleet its supply-chain
guarantee.

### D4 — Decision auth is separate from runner auth

The hub has no user authentication today: `/enroll`, `/heartbeat`, and
`/revoke` authenticate with one-time enrollment tokens and per-runner heartbeat
tokens. There is no operator identity anywhere in the system.

An approve action cannot ride on a heartbeat token — those are held by every
job on the lane, and the operator approving is not the lane asking. This change
introduces an operator credential distinct from `HEARTBEAT_TOKEN`, and the
request record stores who decided and when.

The exact mechanism (bearer token, mTLS, existing MC session forwarded) is
implementation detail; the requirement is that a runner cannot decide its own
request, and that a decision is attributable.

### D5 — Requested, not blocking

A runner reports a gap and continues. The heartbeat still exits 0. The job that
needed `cargo` still fails — correctly, and before this change it failed without
saying why.

The request exists to convert an unexplained failure into a visible, owned
decision. Making the job wait on a human would turn a missing toolchain into a
stuck queue on every lane at once.

**Rejected:** fail-closed heartbeat. A gap that blocks the heartbeat would
also block the report of that same gap.

#### Data shape

New top-level collection in `runners.json`, alongside `runners`:

```
toolchain_requests: [
  {
    id:                  "tcr-0001",      # monotonic, per-registry
    runner_name:         "ucs03-zhm",     # the lane that reported the gap
    missing_tools:       ["cargo"],       # closed vocabulary only (D2)
    state:               "open",          # open|approved|denied|fulfilled
    reason:              "ci.yml needs cargo for the Bevy build",
    first_seen:          "<iso8601>",
    last_seen:           "<iso8601>",     # re-reported while still open
    decided_by:          "<operator id>", # null until decided
    decided_at:          "<iso8601>",     # null until decided
    decision_note:       "<free text>",   # null until decided
    fulfilled_digest:    "sha256:…",      # the pinned image, when fulfilled
    fulfilled_at:        "<iso8601>"      # null until fulfilled
  }
]
```

`fulfilled_digest` is the join to the lane's existing `image_digest`: when a
fulfilled request's digest matches what the runner reports, the gap is closed
by construction rather than by a second mechanism noticing.

#### Data flow

1. Runner's job needs `cargo`; the image lacks it. The spoke compares the
   image's toolchain against the vocabulary and adds `missing_tools` to its next
   heartbeat.
2. Hub verifies the heartbeat token as usual, upserts an `open` request per
   `(runner_name, tool)`, and records `last_seen`.
3. MC's dashboard route lists open requests with the lane's repo, host alias,
   and current `image_digest`, so the operator decides with context.
4. Operator approves (with operator auth, D4). State → `approved`.
5. A build produces a lane image containing the toolchain. Its digest is
   recorded as `fulfilled_digest`; state → `fulfilled`.
6. Lane redeploys; the next heartbeat reports a new `image_digest`. The gap
   closes because the tool is present, and `image_pin_divergence` continues to
   do its job.
7. Deny, or approve-then-build-fails: state → `denied` or back to `open`, with
   `decision_note`. Never silently closed.

#### Risks

- **Vocabulary drift.** A lane needing a tool the vocabulary lacks cannot
  express it. Mitigation: the vocabulary is spec-governed and extended by
  change, and an unknown name is rejected loudly rather than dropped.
- **Request spam.** A lane whose image never gains the tool re-reports every
  300s. Mitigation: `last_seen` updates in place; no new row per heartbeat.
- **Stale approvals.** Approved but never fulfilled. Mitigation: an approved
  request older than the rebuild window is surfaced as such in the dashboard —
  the same "absence is not health" rule the rest of the hub follows.

#### Open questions for implementation

- Does approval trigger the build, or does a separate CI job build and report
  the digest back? The spec requires only that fulfillment is recorded with a
  digest; the trigger is a delivery decision.
- Should a fulfilled request for a tool the image later loses re-open
  automatically? Leaning yes — it is the same gap, and the vocabulary makes it
  expressible.

---

## 3. Spec Delta (ADDED Requirements)

*source: `openspec/changes/add-runner-toolchain-requests/specs/runner-toolchain-requests/spec.md`*

### Spec: Runner toolchain requests

#### ADDED Requirements

##### Requirement: A runner reports a capability gap from a closed vocabulary
<!-- id: mon-tc-01 -->
A spoke MAY report a `missing_tools` list on its heartbeat. Each entry
SHALL name a tool from the vocabulary this spec defines, and SHALL NOT carry a
version, package name, URL, or command. A `missing_tools` entry outside the
vocabulary SHALL be rejected: the heartbeat SHALL record the rejection and SHALL
NOT create or update a request. A heartbeat reporting no gap SHALL be
indistinguishable in effect from one sent before this capability existed.

The initial vocabulary is: `cargo`, `cmake`, `dotnet`, `gcc`, `g++`, `gitleaks`,
`go`, `gradle`, `java`, `make`, `maven`, `node`, `npm`, `pnpm`, `pip`,
`python`, `shellcheck`.

#### Scenario: a job needs a tool the image lacks
- **WHEN** a heartbeat carries `missing_tools: ["cargo"]`
- **THEN** the hub records the gap against that runner and reports success for
  the heartbeat

#### Scenario: a report names something that is not a known tool
- **WHEN** a heartbeat carries `missing_tools: ["curl … | sh"]` or any string
  outside the vocabulary
- **THEN** the hub records the rejection, creates no request, and does not
  echo the value into any stored field

#### Scenario: the image gains the tool
- **WHEN** a heartbeat no longer reports a gap previously reported
- **THEN** the request's state does not change on that heartbeat alone; only
  fulfillment (recorded with a digest) closes it

##### Requirement: The hub is the system of record for requests
<!-- id: mon-tc-02 -->
The hub SHALL persist each request with its id, requesting runner, missing
tools, state, reason, first and last observation, decision author and
timestamp, decision note, and — once fulfilled — the pinned digest and its
timestamp. The hub SHALL expose the current request set and SHALL expose a
transition action for `open` → `approved` and `open` → `denied`. Mission
Control SHALL read the request set from the hub and SHALL NOT hold a
divergent copy of fleet request state.

#### Scenario: the same gap recurs across heartbeats
- **WHEN** a runner reports `missing_tools: ["cargo"]` on five consecutive
  heartbeats
- **THEN** one request exists, its `last_seen` advances, and no additional row
  is created

#### Scenario: Mission Control restarts
- **WHEN** the MC dashboard process is restarted
- **THEN** the open-request queue is served from the hub and is unchanged by
  the restart

##### Requirement: A runner cannot decide its own request
<!-- id: mon-tc-03 -->
The approve and deny actions SHALL require an operator credential that is
distinct from the per-runner heartbeat token, and SHALL record the deciding
identity and the decision timestamp. A presented heartbeat token SHALL NOT
authorize a transition. A request SHALL NOT leave `open` without a recorded
decision author and timestamp.

#### Scenario: a job on the requesting lane calls the approve action
- **WHEN** a heartbeat token for `ucs03-zhm` is presented to the approve action
- **THEN** the action is refused, no state changes, and the refusal is recorded

#### Scenario: an operator denies with a reason
- **WHEN** an operator denies a request with a decision note
- **THEN** the state becomes `denied`, the author and timestamp are recorded,
  and the note is retained with the request

##### Requirement: Fulfillment is a digest-pinned image change
<!-- id: mon-tc-04 -->
A request SHALL reach `fulfilled` only when a fulfillment record carrying the
image digest of the rebuilt lane is written against it. No transition in this
capability SHALL execute a package manager or otherwise install software on a
running runner. The recorded digest SHALL be the value the lane subsequently
reports in its existing `image_digest` field, so that the existing
`image_pin_divergence` check (img-cycle-05) continues to detect drift.

#### Scenario: approval without a build
- **WHEN** a request is approved but no fulfillment record follows
- **THEN** the state remains `approved` with no fulfilled digest, and the
  dashboard shows it as outstanding rather than complete

#### Scenario: fulfillment is recorded
- **WHEN** a fulfillment record with digest `sha256:…` is written against an
  approved request
- **THEN** the state becomes `fulfilled`, the digest and timestamp are
  retained, and the request joins to the lane's `image_digest`

##### Requirement: A gap the fleet has not answered stays visible
<!-- id: mon-tc-05 -->
An open or approved request SHALL remain visible in the request set until it is
fulfilled or denied. An approved request that has not been fulfilled within the
fulfillment window SHALL be reported as outstanding. Absence of a request for a
lane SHALL NOT be presented as evidence that the lane's toolchain is complete.

#### Scenario: an approved request never gets built
- **WHEN** an approved request passes the fulfillment window with no
  fulfillment record
- **THEN** it is reported as outstanding, naming the age

#### Scenario: a lane is fully provisioned
- **WHEN** a lane's requests are all fulfilled
- **THEN** the lane appears with no open requests, and that absence is
  distinguishable from a lane that has never reported

---

## 4. Tasks

*source: `openspec/changes/add-runner-toolchain-requests/tasks.md`*

### Tasks: runner-toolchain-requests

Work is grouped so that each group leaves the system in a state that is
explained rather than silently broken. Nothing here is marked complete on
authoring a spec.

#### S0 — Vocabulary and contract

- [ ] 0.1 Freeze the tool vocabulary as spec-governed data (currently 17
      names), with the rule that adding one is a spec change, not a config edit.
- [ ] 0.2 Define the request record shape (`design.md` §Data shape) and add it
      to `hub/schema/runners.schema.json` as `toolchain_requests`.
- [ ] 0.3 Decide operator auth (design D4) and record the choice in the
      decision log; the requirement is that it is not a heartbeat token.
- [ ] 0.4 Update `AGENTS.md` namespaces to include `mon-tc-*`.

#### S1 — Hub: record requests

- [ ] 1.1 `hub/registry.py`: persist `toolchain_requests`; upsert by
      `(runner_name, tool)` so a recurring gap advances `last_seen` instead of
      duplicating (mon-tc-02).
- [ ] 1.2 Accept `missing_tools` on the heartbeat path; validate every entry
      against the vocabulary and reject the unknown ones without storing them
      (mon-tc-01).
- [ ] 1.3 Expose the request set over `GET` with the lane's `repo`,
      `host_alias`, and `image_digest` attached, so MC can render context.
- [ ] 1.4 Boundary tests: unknown tool rejected and not stored; a presented
      value never reaches a persisted field; heartbeat still exits 0 on a
      rejected gap (mon-tc-01).
- [ ] 1.5 Regression test: a heartbeat that omits `missing_tools` entirely
      behaves exactly as it did before the change.

#### S2 — Hub: decide requests

- [ ] 2.1 Add the transition endpoint; require operator auth distinct from
      `HEARTBEAT_TOKEN`; record author and timestamp (mon-tc-03).
- [ ] 2.2 Negative control: heartbeat token presented to approve is refused,
      state unchanged, refusal recorded (mon-tc-03).
- [ ] 2.3 Deny path with a retained decision note.

#### S3 — Hub: fulfillment

- [ ] 3.1 Fulfillment record carrying a digest; state → `fulfilled` (mon-tc-04).
- [ ] 3.2 Negative control: approval alone does not reach `fulfilled`, and no
      code path in this capability invokes a package manager.
- [ ] 3.3 Outstanding reporting for approved-but-unbuilt requests past the
      window (mon-tc-05).

#### S4 — Spoke

- [ ] 4.1 `scripts/runner-heartbeat.sh`: detect the image's toolchain against
      the vocabulary and report the difference.
- [ ] 4.2 Host-side unit test with a synthetic toolchain manifest; the
      heartbeat must exit 0 whether or not a gap exists.

#### S5 — Mission Control (separate repo `mission-control-rs`)

- [ ] 5.1 Hub client under `src/adapters/`; MC holds no fleet request state of
      its own (mon-tc-02).
- [ ] 5.2 Dashboard route beside `src/api/dashboard.rs` listing open requests
      with lane context.
- [ ] 5.3 Approve / deny actions carrying operator auth.
- [ ] 5.4 Frontend queue; absence of requests must not read as
      "toolchain complete" (mon-tc-05).
- [ ] 5.5 MC-side OpenSpec change in `mission-control-rs` governs this work;
      this repo governs only the hub contract.

#### S6 — Gate + docs

- [ ] 6.1 `scripts/spec_traceability.py` coverage for every `mon-tc-*`
      requirement; the gate is advisory today, so this must be verified by
      running it and reading the count, not assumed.
- [ ] 6.2 `openspec validate --all --strict` green.
- [ ] 6.3 Operator documentation: the request loop, and the explicit statement
      that approval produces an image rebuild, never a live install.
- [ ] 6.4 Failure-registry entry if any incident surfaces during the work.

---

