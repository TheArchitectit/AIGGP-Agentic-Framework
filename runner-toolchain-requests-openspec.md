# runner-toolchain-requests - OpenSpec change package (rev 2)

> Repo: `TheArchitectit/AIGGP-Agentic-Framework`  ·  Branch: `feature/runner-toolchain-requests`
> Change path: `openspec/changes/add-runner-toolchain-requests/`
> Revised after external architecture review (v2) + Mission Control fit review, 2026-10-03 CDT
> Validation: `openspec validate --all --strict` = 32 passed, 0 failed
> Capability: `runner-toolchain-requests` (new)  ·  Requirement IDs: `mon-tc-01` .. `mon-tc-06`
> Traceability: 72/123 covered; all 6 `mon-tc-*` uncovered (advisory gate - correct pre-implementation)

---

## 1. Proposal

*source: `openspec/changes/add-runner-toolchain-requests/proposal.md`*

### Proposal: runner-toolchain-requests

> Revised after external architecture review, 2026-10-03 CDT. See `design.md`
> §Findings this revision corrects.

#### Why

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

#### What Changes

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

#### Impact

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

#### Honest limit

This capability makes operator decisions attributable and the images they
produce digest-pinned. It does not make a runner hermetic: a job on a lane can
still install software for itself. The boundary is on the decision channel and
the audit trail, not on the runner.

---

## 2. Design

*source: `openspec/changes/add-runner-toolchain-requests/design.md`*

### runner-toolchain-requests — Design

> Revised after external architecture review (v2) and Mission Control fit
> review, 2026-10-03 CDT. Findings F1–F11 and M1–M6 are addressed below; the
> six questions the review left open are answered in §Decisions taken.

#### Context

A fleet runner that lacks a toolchain cannot ask for one. This design adds the
request channel, the decision surface, and the fulfillment path.

Measured 2026-10-04 02:40–02:55 UTC (read-only, via `podman run` against the
images the fleet's own quadlets reference). Evidence is held in private
operational documentation; lane names, host aliases, image sizes and host
posture are deliberately not reproduced in this public repository — see F7.

- The stock runner image carries `git`, `python3`, `jq`, `bash` and no
  toolchain beyond those. Five lanes run on it.
- Lanes with a toolchain carry it baked into the image.
- The consequence is a per-job tax: stock lanes fetch a toolchain in every job,
  so the knowledge lives in workflow YAML and drifts from the image.

#### Findings this revision corrects

**F1 — evaluator image fields are not lane images.** The previous draft claimed
fulfillment's digest "SHALL be the value the lane reports in its existing
`image_digest` field". Verified against `hub/schema/runners.schema.json:50`,
that field is the **coherence evaluator** ref, assembled from
`COHERENCE_IMAGE` plus `COHERENCE_IMAGE_MANIFEST_DIGEST`. It does not describe
a runner lane image, and img-cycle-05 compares the *evaluator* tag's served
digest. Overloading it would have been a silent join to nothing, and
`hub/registry.py` clears the field when a heartbeat sends an explicit null, so
evidence held there can vanish. Lane image identity now lives in separate
fields and the spec states the two are unrelated.

> Correction to the review: F1 states the hub "clears a stored `image_digest`
> when a heartbeat omits it". It does not. `heartbeat()` defaults the field to
> `UNREPORTED` and assigns only when it is not `UNREPORTED`
> (`hub/registry.py:309`), so omitting leaves the stored value alone and an
> explicit `null` clears it. The conclusion is unchanged; the regression test
> must assert the real behaviour.

**F3 / M2 — there are two runner registries.** Mission Control maintains its own
Postgres runner registry (enroll, heartbeat, fleet reads) alongside the hub's
`runners.json`. The previous draft asserted Mission Control "holds no fleet
state", which was true of the hub client and false of the registry.

**M3 — the previous draft read the wrong Mission Control.** Its file paths came
from the standalone `TheArchitectit/mission-control-rs` repository, last pushed
2026-09-15. The live tree is the `mission-control-rs/` directory inside
`TheArchitectit/missioncontrol`, last pushed 2026-10-03. Verified in that tree:
`askama` + `askama_axum` + `axum` (not Inertia), `src/api/runners/` and
`src/api/fleet/` present, no `src/api/dashboard.rs`.

**F4 — the detector compared against the vocabulary.** That is a permanent gap
on every stock lane, because the vocabulary is the union of what *some* lane
needs. The gap is now *required profile minus observed*, which is empty on a
provisioned lane.

#### Decisions taken

Answers to the six questions the review left open.

### Q1 — Registry ownership and lane mapping

The hub owns toolchain **requests**. Mission Control owns its runner registry
and keeps it; the two are not merged.

`runner_name` in the hub is the canonical lane identifier. Each Mission
Control runner record carries an explicit `hub_runner_name` link. The queue
joins on that link only, and a request whose lane has no link renders as
`unmapped` rather than being dropped or joined to a same-named record.

Rejected: making Mission Control the system of record (a second writer for
state the hub already owns), and a merged registry (two deployments, one
migration, no incremental value).

### Q2 — Operator identity depth

For v1: one operator, an actor claim, and honesty about it.

Mission Control authenticates the human through its existing session and CSRF
guard plus an administrative-tier check, then calls the hub with a dedicated
service credential carrying scope `toolchain:decide` and a signed actor claim
(principal, timestamp, nonce). The hub stores the claim and the credential
identifier, refuses replay, and refuses every other credential class it knows.

The hub records the actor claim as presented. It does not assert the claim
identifies a distinct human, and `mon-tc-03` requires that a single-principal
configuration be visible as such in the audit record. Per-operator accounts are
a prerequisite for multi-operator operation, not for v1 — there is one human
today — but the spec must not imply attribution it cannot deliver.

Rejected: letting the decide action ride on an ordinary Mission Control API
key (write scope, shared secret, no actor), and inventing an operator identity
in the hub before Mission Control has one to forward.

### Q3 — Who builds, and what triggers it

A build job, not Mission Control.

Mission Control records the approval. A CI job — triggered by the approval and
holding a **builder credential**, distinct from both the operator credential
and runner credentials — builds the lane image with the toolchain profile
added, then reports back with profile id, build id and digest. The hub moves
the request `approved → built`, and a later heartbeat carrying that digest with
a passing probe moves it `built → fulfilled`.

Rejected: Mission Control triggering builds (puts an operator-facing service in
the build path for no gain), and the hub executing a build (the hub must never
run a package manager — `mon-tc-05`).

### Q4 — Row identity

Per `(lane, tool)`.

Approving one tool of three has to be expressible, and a bundle row cannot
represent a partial approval. A **toolchain profile** groups tools for
provisioning; the **request** stays per tool so partial progress is visible.

Rejected: one row per bundle (partial approval becomes a lie) and one row per
lane (the common case of two tools from two different profiles collides).

### Q5 — Queue UI surface

An Askama + HTMX page in the page-gated tier.

It matches what the live tree actually ships, escapes by default, and needs no
cookie-session bridge. Mission Control's own `frontend-architecture` spec still
says the React SPA "SHALL be removed" while a later decision admits React
islands on six routes; reconciling that stale spec text is part of the Mission
Control companion change, not something this change should silently pick a side
on.

Rejected: a React island tab (requires the bridge the decision describes, for a
queue that is a list and two buttons).

### Q6 — Ownership of observed lane-image evidence

The hub.

Mission Control's `fleet-runner-dashboard` spec forbids full image digests in
the podman snapshot payload. Since the fulfillment chain is digest-based, the
evidence comes from the hub's `lane_image_digest`, reported by the spoke from
the running container. No Mission Control spec change is required.

Rejected: widening the snapshot allow-list (changes a security decision in
another spec to serve this one).

#### Architecture

### Detection

    gap = required_profile(lane)  MINUS  observed(runner image)

`required_profile` is a reviewed per-lane assignment, trusted, not
runner-supplied. `observed` is probed inside the runner image — never the host
`PATH`. Each probe returns `present`, `absent`, or `unknown`; a probe that
exceeds its bound is `unknown`, and `unknown` is never collapsed into `absent`
or into `present`.

Probes are fixed: `python` is `python3` present; `pip` is `python3 -m pip`
succeeding; `maven` and `java` require a working JDK; `g++` is probed
separately from `gcc`.

### State machine

Row identity `(lane, tool)`, states `open` → `approved` → `built` →
`fulfilled`, with `denied` terminal-until-suppressed. The normative transition
table is in `mon-tc-04`; `design.md` does not restate it, so there is one
source of truth.

Concurrency: every row carries a version counter. Transitions are
compare-and-swap under the registry lock, so of two simultaneous decisions
exactly one wins and the loser receives `409 Conflict`. Re-submitting an
identical decision at the version it already produced returns that outcome
rather than applying twice — idempotency without opening a replay hole, which
is why nonce freshness is enforced separately on the credential.

History is append-only; the current state is a projection of it.

### Coverage state

The previous draft collided: one requirement said a no-gap heartbeat must be
indistinguishable from a pre-capability heartbeat, another said a provisioned
lane must be distinguishable from one that never reported.

Resolved by a separate per-lane **report-coverage state** — `reported`,
`never-reported`, `stale`, `probe-failed` — with numeric staleness and
fulfillment windows defined by the spec. Coverage is orthogonal to request
state, so both requirements can hold at once.

### Credentials

| Credential | Holder | May |
|---|---|---|
| enrollment / heartbeat | runner spoke | enroll, heartbeat |
| runner key | runner spoke | request a gap |
| `toolchain:decide` + actor claim | Mission Control service | decide |
| builder credential | build job | report build evidence |

The hub refuses every class outside the row's authorization. No credential is
stored in plaintext in the repository, and rotation is a hub restart — which is
also when enrollment tokens arm.

#### Honest limits

This boundary protects the **decision channel and the audit trail**, not the
runner. A job executing on a lane can already install software for itself; this
change makes the operator-visible decisions attributable and the resulting
images digest-pinned, and it does not make a lane hermetic. Read
`mon-tc-05` as a statement about provenance, not as a claim about confinement.

#### Data shape

New top-level collection in `runners.json`, alongside `runners`:

```
toolchain_requests: [
  {
    id:                  "tcr-0001",
    lane:                "lane-A",        # hub runner_name
    tool:                "cargo",         # one row per (lane, tool)
    required_profile:    "rust-bevy",    # reviewed, trusted
    state:               "open",         # open|approved|built|fulfilled|denied
    version:             3,              # CAS counter
    observed_at:         "<iso8601>",
    last_seen:           "<iso8601>",
    coverage:            "reported",     # reported|never-reported|stale|probe-failed
    actor:               "<claim>",      # decision identity as presented
    credential_id:       "<id>",
    decided_at:          "<iso8601>",
    decision_note:       "<capped text>",
    nonces:              ["<consumed>"], # replay defence
    build_id:            "<id>",
    builder_identity:    "<id>",
    lane_image_digest:   "sha256:...",   # when built
    fulfilled_at:        "<iso8601>",
    suppression_until:   "<iso8601>"     # when denied
  }
]
```

Per-runner, separate from the above and **not** touching the evaluator fields:
`lane_image_ref`, `lane_image_digest`, `toolchain_profile_id`, `coverage`.

#### Risks

- **Profile drift.** A lane's required profile is trusted and reviewed; a stale
  profile reports gaps nobody needs. Mitigation: profiles are versioned with the
  capability, and a fulfilled request records the profile it was fulfilled
  against.
- **Single-principal attribution.** v1 decisions share one principal by
  construction. Mitigation: stated in `mon-tc-03`, visible in the audit record.
- **Request spam.** A lane whose image never gains the tool re-reports every
  300s. Mitigation: upsert on `(lane, tool)`, `last_seen` advances, no new row.
- **Approved but never built.** Mitigation: numeric fulfillment window,
  outstanding reporting.

---

## 3. Spec Delta (ADDED Requirements)

*source: `openspec/changes/add-runner-toolchain-requests/specs/runner-toolchain-requests/spec.md`*

### Spec: Runner toolchain requests

#### ADDED Requirements

##### Requirement: A runner reports a capability gap drawn from a closed vocabulary
<!-- id: mon-tc-01 -->
A spoke MAY report `missing_tools` on its heartbeat. A reported gap SHALL be
the set difference of **the toolchain profile required for that lane** and
**the tools observed present in the runner image itself**, never a difference
against the vocabulary as a whole and never a difference against the host
`PATH`. A lane whose profile requires nothing reports nothing.

Every entry SHALL be matched by exact byte comparison, case-sensitive, with no
trimming and no Unicode normalization, against the vocabulary below. The
observed state of each probed tool SHALL be one of `present`, `absent`, or
`unknown`, where `unknown` means the probe could not complete within its bound.
`unknown` SHALL NOT be recorded as `absent`, and SHALL NOT be recorded as
`present`. A probe failure SHALL yield an unknown, never a report of a
complete toolchain.

The initial vocabulary is: `cargo`, `cmake`, `dotnet`, `gcc`, `g++`, `gitleaks`,
`go`, `gradle`, `java`, `make`, `maven`, `node`, `npm`, `pnpm`, `pip`,
`python`, `shellcheck`.

Probes are fixed and are not host-specific: `python` is `python3` present;
`pip` is `python3 -m pip` succeeding (a `python3` without the module is
`absent`); `maven` and `java` require a working JDK; `g++` is its own probe and
is not inferred from `gcc`. Probe duration SHALL be bounded.

Parsing SHALL be all-or-nothing: if any entry of a submitted list is outside
the vocabulary, is not a string, or the list exceeds the maximum length, the
whole list SHALL be rejected and no request SHALL be created or updated. A
rejection SHALL be recorded as a code and an incrementing counter. The rejected
value SHALL NOT be stored in any field, any log line, or any audit row.

#### Scenario: a lane's profile requires a tool its image lacks
- **WHEN** a lane whose required profile contains `cargo` heartbeats from an
  image in which the `cargo` probe returns `absent`
- **THEN** the hub records one open request for `(lane, cargo)` and the
  heartbeat succeeds

#### Scenario: the image has everything the profile requires
- **WHEN** a heartbeat is sent by an image whose observed tools equal the lane's
  required profile
- **THEN** an empty gap is reported, not the complement of the vocabulary

#### Scenario: a probe cannot complete
- **WHEN** the `pip` probe exceeds its bound or errors
- **THEN** that tool is recorded `unknown` and the request is not created or
  cleared on the strength of an unknown

#### Scenario: a probe proves a dependency
- **WHEN** `maven` is probed and no working JDK is present
- **THEN** `maven` is `absent` regardless of whether a `maven` binary name
  resolves

#### Scenario: a value outside the vocabulary
- **WHEN** a heartbeat submits a list containing any entry that is not an exact
  vocabulary member, is not a string, or exceeds the maximum list length
- **THEN** the entire list is rejected, a rejection code and counter are
  recorded, no request is created or updated, and no byte of the submitted
  value appears in any stored field or log line

#### Scenario: `g++` survives every channel
- **WHEN** `g++` is submitted and later stored, exported, and rendered
- **THEN** it is preserved byte-for-byte as `g++`, and is never interpolated
  into a shell string, a regular expression, or a path without the escaping
  that channel requires

##### Requirement: The hub is the system of record, and lane identity is explicit
<!-- id: mon-tc-02 -->
The hub SHALL persist every request and SHALL expose the request set and the
per-request transition actions. Mission Control SHALL read requests from the
hub and SHALL NOT persist a toolchain request table, a cache of one, or any
other divergent copy; a hub read that cannot complete SHALL be reported to the
operator as a failure with the time of the last good read, and SHALL NOT be
rendered as an empty result.

Mission Control maintains a separate runner registry. The hub's `runner_name`
SHALL be the canonical lane identifier, and each Mission Control runner record
SHALL carry an explicit link to that identifier. A request whose lane has no
established link SHALL be reported as `unmapped` rather than omitted or
silently joined to an unrelated record.

A heartbeat omitting `missing_tools` SHALL be indistinguishable, in effect,
from a heartbeat sent before this capability existed.

#### Scenario: five identical reports
- **WHEN** the same `(lane, tool)` is reported on five consecutive heartbeats
- **THEN** exactly one request row exists and its last-observed time advances

#### Scenario: concurrent identical reports
- **WHEN** twenty threads post the same `(lane, tool)` report simultaneously
- **THEN** one row exists afterwards

#### Scenario: Mission Control restarts
- **WHEN** the MC dashboard process restarts
- **THEN** the served queue is identical to the queue before the restart and
  the MC database contains no toolchain table

#### Scenario: the hub is unreachable
- **WHEN** MC cannot complete a read of the hub
- **THEN** the queue reports that the hub is unreachable with the time of the
  last good read, and does not present an empty list

#### Scenario: a request for a lane MC has not linked
- **WHEN** a request names a lane with no established MC registry link
- **THEN** it is reported as `unmapped`

##### Requirement: Decisions are attributable and cannot be made by a runner
<!-- id: mon-tc-03 -->
A decision SHALL be authorized by an operator credential carrying the scope
`toolchain:decide` together with an actor claim naming the deciding principal,
a timestamp, and a unique nonce. The hub SHALL verify the credential, SHALL
store the actor claim with the decision, and SHALL reject any presented nonce
it has already consumed.

A per-runner heartbeat token, a runner key, a builder credential, and an
ordinary Mission Control API key SHALL NOT authorize a decision. A request
SHALL NOT leave `open` without a recorded actor, credential identifier, and
timestamp.

The human-to-operator-credential binding is Mission Control's responsibility:
MC authenticates the operator and enforces its own administrative tier before
issuing a decision. For the first version the hub SHALL record the actor claim
as presented and SHALL NOT assert that it identifies a distinct human; a
configuration where every decision shares one principal SHALL be visible as
such in the audit record rather than presented as per-operator attribution.

#### Scenario: a runner attempts to decide
- **WHEN** a heartbeat token, runner key, builder credential, or ordinary MC
  write key is presented to a decision action
- **THEN** the action is refused, no state changes, and the refusal is recorded

#### Scenario: an operator approves
- **WHEN** a `toolchain:decide` credential presents a valid actor claim
- **THEN** the decision succeeds and the actor claim, credential identifier,
  and timestamp are stored with the request

#### Scenario: a replayed nonce
- **WHEN** a decision is replayed with a nonce the hub has already consumed
- **THEN** it is refused as a replay and the decision is not applied twice

##### Requirement: Request state changes only through a guarded transition
<!-- id: mon-tc-04 -->
A request SHALL carry a row identity of `(lane, tool)` and SHALL carry a version
counter that increments on every transition. Every transition SHALL satisfy a
guard, and a transition whose guard does not hold SHALL be refused with the
request left unchanged and the refusal recorded.

Where a decision and a report could both apply to the same version, exactly one
SHALL win and the other SHALL be refused with `409 Conflict`. Submitting an
identical decision at an already-applied version SHALL return that version's
existing outcome rather than applying a second time.

The transition table is normative:

| From | Event | Guard | To | Audit row |
|---|---|---|---|---|
| `open` | decide-approve | operator credential, fresh nonce | `approved` | decision + actor claim |
| `open` | decide-deny | operator credential, fresh nonce, note present | `denied` | decision + actor claim + note |
| `approved` | report-built | builder credential, profile id matches the approved profile, build id and digest present | `built` | build evidence |
| `built` | converge | a later heartbeat reports the recorded digest and the required probe passes | `fulfilled` | convergence evidence |
| `approved` | build-failed | builder credential, note present | `open` | failure + note |
| `built` | build-failed | builder credential, note present | `open` | failure + note |
| `fulfilled` | gap-regressed | a later heartbeat reports the gap again | `open` | regression |
| `denied` | report-suppressed | within the suppression window | `denied` | no state change; suppression counter |
| `denied` | report-after-window | suppression window elapsed | `open` | reopen |

Transitions SHALL NOT be performed outside this table. History SHALL be
append-only.

#### Scenario: approving one tool of three
- **WHEN** a lane reports three missing tools and an operator approves one
- **THEN** exactly one request reaches `approved` and the other two remain
  `open`

#### Scenario: two operators decide at once
- **WHEN** two decisions are submitted against the same request version
- **THEN** one succeeds and the other is refused with `409 Conflict`, and both
  attempts appear in the audit history

#### Scenario: a repeated identical decision
- **WHEN** the same decision is submitted again at the version it already
  produced
- **THEN** that version's existing outcome is returned and no second
  transition is applied

#### Scenario: a toolchain reappears after fulfillment
- **WHEN** a fulfilled request's tool is later reported absent again
- **THEN** the request returns to `open` with a regression audit row

#### Scenario: a denied lane keeps reporting
- **WHEN** a denied request is reported again within the suppression window
- **THEN** it remains `denied` and the suppression counter advances; after the
  window it returns to `open` with a reopen audit row

##### Requirement: Fulfillment requires evidence from a trusted builder and a later convergence
<!-- id: mon-tc-05 -->
`fulfilled` SHALL NOT be reachable from a digest alone. Reaching `built`
requires a builder credential, a toolchain profile identifier matching the
approved profile, a build identifier, and an image digest. Reaching `fulfilled`
additionally requires a later heartbeat in which the lane reports that same
digest and the required tool probe passes. A digest supplied under an operator
or runner credential SHALL be refused.

No code path in this capability SHALL execute a package manager or otherwise
install software on a running runner.

This capability SHALL NOT read, write, or reinterpret the registry's evaluator
image fields. `image_digest` and `image_pin_divergence` describe the coherence
evaluator image; the pin-divergence check (img-cycle-05) is unrelated to lane
images and is unchanged by this capability. Lane image identity SHALL be
recorded in separate fields.

#### Scenario: approval with no build
- **WHEN** a request is approved and no build report follows
- **THEN** the state remains `approved`, carries no digest, and is reported as
  outstanding rather than complete

#### Scenario: build reported, probe still failing
- **WHEN** a build report records a digest but a later heartbeat's probe for
  the required tool still fails
- **THEN** the state remains `built` and does not become `fulfilled`

#### Scenario: a digest offered under the wrong credential
- **WHEN** a digest is reported under an operator or runner credential
- **THEN** it is refused and no state change results

#### Scenario: a heartbeat omits the evaluator image field
- **WHEN** a heartbeat omits the evaluator `image_digest`
- **THEN** the stored evaluator field behaves exactly as it did before this
  capability existed, and no toolchain transition has altered it

##### Requirement: Absence is never reported as health
<!-- id: mon-tc-06 -->
Each lane SHALL carry a report-coverage state of `reported`, `never-reported`,
`stale`, or `probe-failed`, distinguished by whether the spoke has ever sent a
gap field, whether the last report is older than the staleness threshold, and
whether the last probe run was incomplete. A request in `open` or `approved`
state SHALL remain visible in the request set until it reaches `fulfilled` or
`denied`. An `approved` request not built within the fulfillment window SHALL
be reported as outstanding with its age. A lane with no open requests SHALL NOT
be presented as evidence that its toolchain is complete unless its coverage
state is `reported` and every request for it is fulfilled.

Both the staleness threshold and the fulfillment window SHALL be numeric
values defined by this capability, not left to an operator's judgement.

#### Scenario: an approved request is never built
- **WHEN** an approved request passes the fulfillment window with no build
  report
- **THEN** it is reported as outstanding, naming its age

#### Scenario: a lane that never reported
- **WHEN** a lane has no requests and its coverage state is `never-reported`
- **THEN** it is not presented as fully provisioned

#### Scenario: a stale lane
- **WHEN** a lane's last gap report is older than the staleness threshold
- **THEN** its coverage state is `stale` and it is distinguished from a lane
  that reported recently

#### Scenario: a probe that failed last run
- **WHEN** a lane's most recent probe run was incomplete
- **THEN** its coverage state is `probe-failed` and its toolchain is not
  presented as known

---

## 4. Tasks

*source: `openspec/changes/add-runner-toolchain-requests/tasks.md`*

### Tasks: runner-toolchain-requests

Every normative clause in the spec gets a positive test and a negative control.
Nothing here is marked complete from spec authoring.

`mon-tc-*` requirements are currently uncovered by source markers; that count
must be **read** at the end gate, not assumed. Proposed test files do not exist
yet.

#### S0 — Contract, decided before code

- [ ] 0.1 Freeze the tool vocabulary as spec-governed data (16 names), with the
      rule that adding one is a change, not a config edit.
- [ ] 0.2 Add the reviewed per-lane **toolchain profile** table mapping a lane
      to its required tools. Trusted input, never runner-supplied.
- [ ] 0.3 Add `lane_image_ref`, `lane_image_digest`, `toolchain_profile_id` and
      `coverage` to the runner record. **Do not** touch `image_digest`,
      `image_reason`, or `image_pin_divergence` — they are evaluator-image
      fields (schema lines 49–60).
- [ ] 0.4 Define the credential classes and the builder/operator split from
      `design.md` §Credentials. Operator auth is **decided there**, not here.
- [ ] 0.5 Set the numeric staleness threshold and fulfillment window in the
      spec; no operator judgement.
- [ ] 0.6 Record the single-principal v1 attribution limit in the audit-record
      format, per `mon-tc-03`.

#### S1 — Hub: record requests (mon-tc-01, mon-tc-02)

- [ ] 1.1 `hub/registry.py`: persist `toolchain_requests`, keyed `(lane, tool)`,
      with the version counter and append-only history.
- [ ] 1.2 Heartbeat accepts `missing_tools`; all-or-nothing validation against
      the vocabulary; unknown values rejected as a code plus counter, never
      stored.
      - `tests/test_hub_toolchain_requests.py::test_vocab_*`
      - negatives: non-member, wrong case, trailing newline, zero-width
        character, over-length list, non-string, nested list — each asserts a
        200 heartbeat, zero rows, and no submitted byte in any stored field or
        log line
- [ ] 1.3 `g++` end-to-end: JSON, URL path, URL query, CSV export, HTML render.
      `tests/test_hub_toolchain_requests.py::test_gpp_*`, plus a static scan
      asserting the value never reaches a shell string or an unescaped regex.
- [ ] 1.4 Concurrent identical reports (20 threads) still yield one row.
- [ ] 1.5 Heartbeat omitting `missing_tools` leaves the registry byte-identical
      to pre-change behaviour and sets coverage `never-reported`.
- [ ] 1.6 **Evaluator-isolation regression:** a heartbeat omitting the
      evaluator `image_digest` leaves it exactly as today. Note the real
      behaviour: `heartbeat()` defaults the field to `UNREPORTED` and assigns
      only when it is not, so *omitting* preserves the stored value and an
      explicit `null` clears it (`hub/registry.py:309`). Assert that, not the
      review's paraphrase. Files: `tests/test_hub_registry.py`,
      `tests/test_runner_heartbeat_image.py`, `tests/test_hub_monitor_image.py`.
- [ ] 1.7 **Static scan:** no `subprocess`, `os.system`, `apt`, `pip`, `npm`,
      or `dnf` reference anywhere in the new hub module.

#### S2 — Hub: transitions (mon-tc-03, mon-tc-04)

- [ ] 2.1 Implement the normative transition table from `mon-tc-04` with
      compare-and-swap under the registry lock.
- [ ] 2.2 Concurrent decisions: exactly one 200, one 409, both in audit history.
- [ ] 2.3 Idempotency: an identical decision at an already-applied version
      returns that outcome and applies no second transition.
- [ ] 2.4 Replay: a consumed nonce is refused.
      `tests/test_hub_operator_auth.py`
- [ ] 2.5 Negative controls, each asserting refusal, unchanged state, and an
      audit row: heartbeat token, runner key, builder credential, ordinary MC
      write key, expired nonce.
- [ ] 2.6 `decision_note` capped, stored, and rendered escaped; static scan plus
      fixture asserting it never reaches a builder input, command or profile
      lookup.
- [ ] 2.7 Denied-recurrence and suppression-window behaviour, including
      fulfilled → open regression.

#### S3 — Hub: fulfillment evidence (mon-tc-05)

- [ ] 3.1 `built` requires builder credential + matching profile id + build id +
      digest; mismatched profile refused.
- [ ] 3.2 `fulfilled` requires a later heartbeat with that digest **and** a
      passing probe. Digest present, probe failing → stays `built`.
- [ ] 3.3 Digest under operator or runner credential refused.
- [ ] 3.4 Approval alone never reaches `fulfilled`.

#### S4 — Spoke detection (mon-tc-01)

- [ ] 4.1 `scripts/runner-heartbeat.sh`: required-profile minus observed, probed
      inside the runner image, never host `PATH`.
      `tests/test_runner_toolchain_probe.py`
- [ ] 4.2 Synthetic manifest `{required: [cargo, gcc], observed: [gcc]}` →
      reports `[cargo]`, exit 0.
- [ ] 4.3 Required equals observed → empty list, not a vocabulary dump.
- [ ] 4.4 Probe timeout → `unknown`, exit 0, never "complete".
- [ ] 4.5 `python3` present without the pip module → `pip` reported absent.

#### S5 — Mission Control (separate repository)

Live tree is the `mission-control-rs/` directory inside
`TheArchitectit/missioncontrol` (Askama + HTMX + axum). The standalone
`TheArchitectit/mission-control-rs` repository is **not** the live tree; retire
or label it.

- [ ] 5.0 Write the MC companion OpenSpec change **first**, including the
      auth-gate-coverage classification of the decide route. Pin both commit
      SHAs in the pull request.
- [ ] 5.1 Hub adapter: `src/adapters/` alongside `hermes.rs`, `loki.rs`,
      `rad_a2a.rs`. Explicit timeout. No local cache.
- [ ] 5.2 Protected read `GET /api/v1/fleet/toolchain-requests` proxying to the
      hub, no storage. Fleet code belongs in `src/api/fleet/`, routes register
      in `src/router/builder.rs` — there is no `src/api/dashboard.rs`.
- [ ] 5.3 Decide POST behind session auth + CSRF + an administrative-tier check
      modelled on `/api/v1/keys`. Proxies to the hub with the actor claim.
- [ ] 5.4 Askama + HTMX queue page in the page-gated tier.
      `tests/toolchain_queue_contract.rs`
- [ ] 5.5 Schema-scan test: the MC database contains no toolchain table.
- [ ] 5.6 Hub unreachable → explicit payload naming the last good read time,
      never `[]`.
- [ ] 5.7 Reconcile the stale `frontend-architecture` spec text as part of the
      companion change (it still says the React SPA "SHALL be removed" while a
      later decision admits React islands on six routes).

#### S6 — Gates and docs

- [ ] 6.1 `python3 -m pytest tests/test_hub_toolchain_requests.py
      tests/test_hub_operator_auth.py tests/test_runner_toolchain_probe.py`
- [ ] 6.2 `python3 -m pytest tests/test_hub_registry.py
      tests/test_hub_registry_schema.py tests/test_hub_enroll_heartbeat.py`
- [ ] 6.3 `python3 scripts/spec_traceability.py --root . --report` — **read** the
      `mon-tc-*` count. The gate is advisory, so a clean exit proves nothing;
      paste the number in the PR.
- [ ] 6.4 `npx openspec validate --all --strict`
- [ ] 6.5 `bash scripts/specs-validate-negative-control.sh`
- [ ] 6.6 In Mission Control: `cargo fmt --all -- --check`,
      `cargo clippy --all-targets --all-features -- -D warnings`,
      `cargo test --all-features` with migrations applied, plus the auth-gate
      mutation gate showing the decide route classified and returning 401
      anonymous / 403 with a write-only key / 200 with admin.
- [ ] 6.7 Named green CI runs on the hub commit and the MC commit, with both
      SHAs and run URLs in the PR.
- [ ] 6.8 Operator documentation stating the loop **and** that approval
      produces an image rebuild, never a live install.

> Format validation is not acceptance. `openspec validate` passes an untestable
> spec; the tests above are what make it real.

---

