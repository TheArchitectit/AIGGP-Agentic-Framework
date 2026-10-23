# Spec: Runner toolchain requests

## ADDED Requirements

### Requirement: A runner reports a capability gap drawn from a closed vocabulary
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

Two bounds are fixed here, numerically, because a bound an operator can set is
a bound nobody is measured against:

- `TOOL_PROBE_TIMEOUT_S` is **10 seconds**. A probe that has not answered in
  time is `unknown`, never `absent` and never `present`. Probing all 17 names
  serially at the full bound costs 170 seconds against a 300-second heartbeat
  cadence (design.md, Sec. Risks), so a worst-case probe run cannot overrun the
  tick it reports into.
- `MISSING_TOOLS_MAX_ENTRIES` is **32**. A longer list is rejected whole. The
  vocabulary has 17 members, so a correct spoke cannot approach the cap by
  reporting honestly, and a list that reaches it is a broken spoke rather than a
  lane with unusual needs.

The vocabulary above is **17 names**. The list is normative and any count of it
is derived from the list, never asserted alongside it: where a count elsewhere
in this package disagrees with the list, the list is right and the count is
stale. (Task 0.1 read "16 names", a value written before `shellcheck` joined the
list, and is corrected by this amendment.) Adding a name to the vocabulary is a
change to this capability, reviewed as one, and is never a config edit or a
spoke-side addition.

A **toolchain profile** is a named subset of that vocabulary, and the profiles
are spec-governed data shipped with the capability:

| Profile id | Requires |
|---|---|
| `none` | (nothing) |
| `base` | `gcc`, `make`, `python`, `pip` |
| `rust` | `cargo`, `gcc`, `make` |
| `node` | `node`, `npm` |
| `go` | `go` |
| `jvm` | `java`, `maven`, `gradle` |
| `dotnet` | `dotnet` |
| `web-js` | `node`, `npm`, `pnpm` |
| `ci-hygiene` | `shellcheck`, `gitleaks` |

Every profile SHALL be a subset of the vocabulary. The `rust` profile lists
`gcc` and `make` because a `cargo` build needs a linker and `build.rs` scripts
need `make`; the probe for `cargo` checks only the `cargo` binary, so the
profile, not the probe, is what makes the compiler a requirement of the lane.
Each profile is the union of the tools its lanes actually call, and a profile
SHALL NOT include a tool merely because a lane could use it — a profile is a
requirement list, not a wish list.

Which **lane** carries which profile is a reviewed assignment held outside this
repository, because lane names, host aliases and host posture are deliberately
not reproduced here (Sec. Why). This capability therefore specifies the shape of
that assignment and what the hub does when it is missing, and does not
enumerate it:

- The hub holds the lane→profile mapping as trusted input, never spoke-supplied.
  A heartbeat SHALL NOT be able to set, widen, or rename a lane's profile; a
  body that tries is rejected whole, by the same all-or-nothing rule as a bad
  vocabulary entry.
- A profile id outside the table above is refused rather than treated as empty.
  An unknown profile is not a lane that needs nothing.
- A lane with no reviewed assignment carries `toolchain_profile_id: null` and
  reports no gaps, because there is nothing required to diff against. It SHALL
  be presented as `profile-unassigned` and SHALL NOT be presented as a lane with
  a complete toolchain. `none` (reviewed, requires nothing) and
  `profile-unassigned` (nobody has decided) are different answers and SHALL NOT
  render the same way. This is a presentation of the lane's profile field; it is
  not a fifth coverage state, and `mon-tc-06`'s four states are unchanged.
- Profiles are versioned with the capability, and a request records the profile
  id it was opened against, so a fulfilled request can name what it was
  fulfilled against when the profile later changes.

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

### Requirement: The hub is the system of record, and lane identity is explicit
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

The request-set read is what a queue is built from, so it SHALL carry what a
consumer needs to **render a row and act on it** rather than only its identity:
the lane's repository and host alias (held on the hub's runner record, since a
consumer forbidden a copy has nowhere else to ask), the lane's coverage state as
derived at read time by `mon-tc-06`, and the row's `version`. A consumer cannot
satisfy `mon-tc-04`'s compare-and-set from a payload that omits the version it
must submit; an exposure that cannot be acted on is not an exposure. Fields the
hub does not hold for a lane — a lane never enrolled, a repository never
published — are `null`, not guessed and not omitted, so a consumer renders
absence rather than inventing a value.

#### Scenario: a queue renders a row from the read alone
- **WHEN** a consumer reads the request set for a lane that has enrolled and
  published a repository
- **THEN** the row names its lane, repository, host alias, tool, state, version
  and coverage state without a second lookup

#### Scenario: a row whose lane has never enrolled
- **WHEN** a request exists for a lane the hub has no runner record for
- **THEN** the row still appears, and its repository, host alias and coverage
  state are `null` rather than empty strings or a defaulted state

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

### Requirement: Decisions are attributable and cannot be made by a runner
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

The credential classes are closed and are named here so that a refusal can name
the class it saw rather than a reason derived from it:

| Class | Holder | May |
|---|---|---|
| `enrollment` / `heartbeat` | runner spoke | enroll, heartbeat |
| `runner_key` | runner spoke | report a gap |
| `operator` (scope `toolchain:decide`) | Mission Control service | decide |
| `builder` | build job | report build evidence |

A refusal SHALL be recorded as one `rejected_credential_class` code carrying the
class name and SHALL NOT carry the secret that was presented, its prefix, or a
derivation of it (matching how heartbeat tokens are stored only as salted
digests, mon-sec-02). A class not in the table above is refused as `unknown`, so
a new credential type cannot acquire a decision right by being unlisted.

`DECISION_NOTE_MAX_CHARS` is **512**, the cap the hub already applies to
`image_digest` (FIELD_CAPS, hub/server.py). A note longer than the cap is
refused rather than truncated: a truncated reason is a different reason, and a
denial note is read as the operator's decision.

Each decision, refusal and transition appends one record to the request's
history, and the record format is fixed here so that attribution is a property
of the format rather than of whoever wrote the transition:

```
{ seq, at, actor: "<claim as presented>", principal: "<principal as presented>",
  credential_id, event, from, to, version_before, version_after, note }
```

`principal` is recorded exactly as the credential presents it and the audit
record SHALL NOT add a display name, an email, or any other identity the hub did
not receive. Because v1 issues decisions from a single operator credential
(design.md, Sec. Q2), every record in a v1 deployment carries the same
`credential_id`, and the request set SHALL expose that fact — a reader of the
audit history can tell that all decisions share one credential, and is not shown
per-operator attribution the deployment cannot support. `actor` may differ
between records only if Mission Control begins forwarding distinct identities,
and the hub SHALL NOT infer an actor from the credential when none was claimed.

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

### Requirement: Request state changes only through a guarded transition
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
append-only. `report-suppressed` and `report-after-window` are decided against
`TOOL_REQUEST_SUPPRESSION_DAYS` as defined in `mon-tc-06`; this table names the
event and that paragraph owns the number, so the window cannot acquire two
values.

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

### Requirement: Fulfillment requires evidence from a trusted builder and a later convergence
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

### Requirement: Absence is never reported as health
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
values defined by this capability, not left to an operator's judgement. They
are fixed here, in one place, and `mon-tc-04`'s transition table reads its
suppression window from this paragraph rather than restating it — the two-places
failure that made task 0.1 read "16 names" beside a 17-name list is the exact
defect this avoids:

- `TOOL_REQUEST_STALE_AFTER_S` is **900 seconds** — three missed heartbeats at
  the 300-second cadence (design.md, Sec. Risks). Derived: a lane silent for two
  cadences may be mid-tick; three is the first count that cannot be a skipped
  tick, and coverage is `stale` rather than `reported` after it.
- `TOOL_REQUEST_FULFILL_WINDOW_S` is **86400 seconds** (24 hours). An `approved`
  request with no build report past this age is reported outstanding with its
  age; approval produces an image rebuild, and a day is the point at which a
  rebuild that has not happened is itself the finding. This is a judgement
  within an envelope, not a derivation — it is the one number here whose correct
  value depends on the fleet's build-queue latency, which this repository cannot
  observe. It is stated as a judgement so a reviewer can overrule it rather than
  inherit it silently.
- `TOOL_REQUEST_SUPPRESSION_DAYS` is **14 days**. A `denied` request re-reported
  inside the window leaves the row `denied` and advances the suppression
  counter; reported after it, the row reopens to `open`. Also a judgement: a
  denial means the lane does not need the tool, and two weeks is the shortest
  interval at which a re-report is more likely a changed decision or profile
  drift than the same request again.

A value set to zero or to an unbounded sentinel is a specification violation,
not a configuration: it makes `stale` unreachable or the suppression counter
meaningless, and both are states `mon-tc-06` exists to make visible.

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