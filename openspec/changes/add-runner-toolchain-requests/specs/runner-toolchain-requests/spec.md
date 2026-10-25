# Spec: Runner toolchain requests

## ADDED Requirements

### Requirement: A runner reports a capability gap drawn from a closed vocabulary
<!-- id: mon-tc-01 -->
A spoke MAY report `missing_tools` on its heartbeat. A reported gap SHALL be
the set difference of **the toolchain profile required for that lane** and
**the tools observed present in the runner image itself**. A lane whose profile
requires nothing reports nothing.

A submitted list SHALL be parsed all-or-nothing: a list carrying any entry
outside the vocabulary, any non-string entry, or more entries than the maximum
length SHALL be rejected whole.

#### Scenario: an entry is matched exactly against the vocabulary

- **WHEN** a submitted entry is matched
- **THEN** the match is by exact byte comparison, case-sensitive, with no
  trimming and no Unicode normalization, against the vocabulary below
- **AND** the observed state of each probed tool SHALL be one of `present`,
  `absent`, or `unknown`, where `unknown` means the probe could not complete
  within its bound. `unknown` SHALL NOT be recorded as `absent`, and SHALL NOT
  be recorded as `present`
- **AND** a probe failure SHALL yield an unknown, never a report of a complete
  toolchain
- **AND** the initial vocabulary is: `cargo`, `cmake`, `dotnet`, `gcc`, `g++`,
  `gitleaks`, `go`, `gradle`, `java`, `make`, `maven`, `node`, `npm`, `pnpm`,
  `pip`, `python`, `shellcheck`

#### Scenario: a probe has a fixed definition

- **WHEN** a tool is probed
- **THEN** probes are fixed and are not host-specific: `python` is `python3`
  present; `pip` is `python3 -m pip` succeeding (a `python3` without the module
  is `absent`); `maven` and `java` require a working JDK; `g++` is its own probe
  and is not inferred from `gcc`
- **AND** probe duration SHALL be bounded

#### Scenario: a submitted list is rejected whole

- **WHEN** any entry of a submitted list is outside the vocabulary, is not a
  string, or the list is longer than `MISSING_TOOLS_MAX_ENTRIES`
- **THEN** the whole list is rejected, and no request is created or updated
- **AND** a rejection is recorded as a code and an incrementing counter
- **AND** the rejected value SHALL NOT be stored in any field, any log line,
  any audit row, or any other place

#### Scenario: the bounds are fixed, not configured

- **WHEN** the bounds are read
- **THEN** `TOOL_PROBE_TIMEOUT_S` is **10 seconds**: a probe that has not
  answered in time is `unknown`, never `absent` and never `present`, and probing
  all 17 names serially at the full bound costs 170 seconds against a
  300-second heartbeat cadence (design.md, Sec. Risks), so a worst-case probe run
  cannot overrun the tick it reports into
- **AND** `MISSING_TOOLS_MAX_ENTRIES` is **32**: a longer list is rejected whole,
  and the vocabulary has 17 members, so a correct spoke cannot approach the cap
  by reporting honestly, and a list that reaches it is a broken spoke rather than
  a lane with unusual needs
- **AND** two bounds are fixed here, numerically, because a bound an operator can
  set is a bound nobody is measured against

#### Scenario: the vocabulary count is derived, never asserted

- **WHEN** a count of the vocabulary appears anywhere
- **THEN** it is derived from the list, never asserted alongside it: where a
  count elsewhere in this package disagrees with the list, the list is right and
  the count is stale. (Task 0.1 read "16 names", a value written before
  `shellcheck` joined the list, and is corrected by this amendment.)
- **AND** the vocabulary above is **17 names**, and adding a name to it is a
  change to this capability, reviewed as one, and is never a config edit or a
  spoke-side addition

#### Scenario: a profile is spec-governed data

- **WHEN** a lane's profile is resolved
- **THEN** a **toolchain profile** is a named subset of the vocabulary, and the
  profiles are spec-governed data shipped with the capability: `none` requires
  nothing; `base` requires `gcc`, `make`, `python`, `pip`; `rust` requires
  `cargo`, `gcc`, `make`; `node` requires `node`, `npm`; `go` requires `go`;
  `jvm` requires `java`, `maven`, `gradle`; `dotnet` requires `dotnet`;
  `web-js` requires `node`, `npm`, `pnpm`; `ci-hygiene` requires `shellcheck`,
  `gitleaks`
- **AND** every profile SHALL be a subset of the vocabulary
- **AND** the `rust` profile lists `gcc` and `make` because a `cargo` build needs
  a linker and `build.rs` scripts need `make`; the probe for `cargo` checks only
  the `cargo` binary, so the profile, not the probe, is what makes the compiler a
  requirement of the lane
- **AND** each profile is the union of the tools its lanes actually call, and a
  profile SHALL NOT include a tool merely because a lane could use it — a
  profile is a requirement list, not a wish list

#### Scenario: the lane-to-profile assignment is reviewed elsewhere

- **WHEN** the lane-to-profile assignment is consulted
- **THEN** which **lane** carries which profile is a reviewed assignment held
  outside this repository, because lane names, host aliases and host posture are
  deliberately not reproduced here (Sec. Why). This capability specifies the
  shape of that assignment and what the hub does when it is missing, and does
  not enumerate it
- **AND** the hub holds the lane-to-profile mapping as trusted input, never
  spoke-supplied. A heartbeat SHALL NOT be able to set, widen, or rename a
  lane's profile; a body that tries is rejected whole, by the same
  all-or-nothing rule as a bad vocabulary entry
- **AND** a profile id outside the table is refused rather than treated as
  empty, because an unknown profile is not a lane that needs nothing
- **AND** a lane with no reviewed assignment carries `toolchain_profile_id:
  null` and reports no gaps, because there is nothing required to diff against.
  It SHALL be presented as `profile-unassigned` and SHALL NOT be presented as a
  lane with a complete toolchain. `none` (reviewed, requires nothing) and
  `profile-unassigned` (nobody has decided) are different answers and SHALL NOT
  render the same way. This is a presentation of the lane's profile field; it is
  not a fifth coverage state, and `mon-tc-06`'s four states are unchanged
- **AND** profiles are versioned with the capability, and a request records the
  profile id it was opened against, so a fulfilled request can name what it was
  fulfilled against when the profile later changes

#### Scenario: the host PATH is not a source

- **WHEN** a gap is computed
- **THEN** it is never a difference against the vocabulary as a whole and never
  a difference against the host `PATH`

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
other divergent copy.

The hub's `runner_name` SHALL be the canonical lane identifier, and each
Mission Control runner record SHALL carry an explicit link to that identifier.

#### Scenario: the request set carries what a row needs

- **WHEN** the request set is read
- **THEN** it carries what a consumer needs to render a row and act on it rather
  than only its identity, because the request-set read is what a queue is built
  from
- **AND** each row carries the lane's repository and host alias (held on the
  hub's runner record, since a consumer forbidden a copy has nowhere else to
  ask), the lane's coverage state as derived at read time by `mon-tc-06`, and
  the row's `version`
- **AND** a consumer cannot satisfy `mon-tc-04`'s compare-and-set from a payload
  that omits the version it must submit; an exposure that cannot be acted on is
  not an exposure
- **AND** fields the hub does not hold for a lane — a lane never enrolled, a
  repository never published — are `null`, not guessed and not omitted, so a
  consumer renders absence rather than inventing a value

#### Scenario: a heartbeat without the field

- **WHEN** a heartbeat omits `missing_tools`
- **THEN** it is indistinguishable, in effect, from a heartbeat sent before this
  capability existed

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
- **AND** a hub read that cannot complete SHALL be reported to the operator as a
  failure with the time of the last good read, and SHALL NOT be rendered as an
  empty result

#### Scenario: a request for a lane MC has not linked
- **WHEN** a request names a lane with no established MC registry link
- **THEN** it is reported as `unmapped` rather than omitted or silently joined to
  an unrelated record

### Requirement: Decisions are attributable and cannot be made by a runner
<!-- id: mon-tc-03 -->
A decision SHALL be authorized by an operator credential carrying the scope
`toolchain:decide` together with an actor claim naming the deciding principal,
a timestamp, and a unique nonce. The hub SHALL verify the credential, SHALL
store the actor claim with the decision, and SHALL reject any presented nonce
it has already consumed.

A request SHALL NOT leave `open` without a recorded actor, credential
identifier, and timestamp.

#### Scenario: a credential class is not an authorization

- **WHEN** a credential other than an operator credential carrying
  `toolchain:decide` is presented to a decision action
- **THEN** it is refused, because a per-runner heartbeat token, a runner key, a
  builder credential, and an ordinary Mission Control API key SHALL NOT
  authorize a decision
- **AND** the credential classes are closed and are named here so that a refusal
  can name the class it saw rather than a reason derived from it: `enrollment` /
  `heartbeat` (runner spoke, enrolls and heartbeats), `runner_key` (runner
  spoke, reports a gap), `operator` with scope `toolchain:decide` (Mission
  Control service, decides), `builder` (build job, reports build evidence)
- **AND** a refusal SHALL be recorded as one `rejected_credential_class` code
  carrying the class name and SHALL NOT carry the secret that was presented, its
  prefix, or a derivation of it (matching how heartbeat tokens are stored only
  as salted digests, mon-sec-02)
- **AND** a class not in that table is refused as `unknown`, so a new credential
  type cannot acquire a decision right by being unlisted

#### Scenario: a decision note is too long

- **WHEN** a decision note exceeds the cap
- **THEN** it is refused rather than truncated, because a truncated reason is a
  different reason and a denial note is read as the operator's decision
- **AND** `DECISION_NOTE_MAX_CHARS` is **512**, the cap the hub already applies
  to `image_digest` (FIELD_CAPS, hub/server.py)

#### Scenario: the history record format is fixed

- **WHEN** a decision, refusal or transition is appended
- **THEN** it appends exactly one record to the request's history, in this fixed
  format: `{ seq, at, actor: "<claim as presented>", principal: "<principal as
  presented>", credential_id, event, from, to, version_before, version_after,
  note }`
- **AND** `principal` is recorded exactly as the credential presents it and the
  audit record SHALL NOT add a display name, an email, or any other identity the
  hub did not receive
- **AND** because v1 issues decisions from a single operator credential
  (design.md, Sec. Q2), every record in a v1 deployment carries the same
  `credential_id`, and the request set SHALL expose that fact — a reader of the
  audit history can tell that all decisions share one credential, and is not
  shown per-operator attribution the deployment cannot support
- **AND** `actor` may differ between records only if Mission Control begins
  forwarding distinct identities, and the hub SHALL NOT infer an actor from the
  credential when none was claimed

#### Scenario: the human-to-credential binding belongs to Mission Control

- **WHEN** a decision reaches the hub
- **THEN** MC authenticates the operator and enforces its own administrative tier
  before issuing it, since the human-to-operator-credential binding is Mission
  Control's responsibility
- **AND** for the first version the hub SHALL record the actor claim as
  presented and SHALL NOT assert that it identifies a distinct human; a
  configuration where every decision shares one principal SHALL be visible as
  such in the audit record rather than presented as per-operator attribution

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

Transitions SHALL NOT be performed outside the transition table. History SHALL
be append-only.

#### Scenario: two writes against one version

- **WHEN** a decision and a report could both apply to the same version
- **THEN** exactly one SHALL win and the other SHALL be refused with `409
  Conflict`
- **AND** submitting an identical decision at an already-applied version SHALL
  return that version's existing outcome rather than applying a second time

#### Scenario: the transition table is normative

- **WHEN** a transition is applied
- **THEN** it is one of these, and no other: `open` + decide-approve (operator
  credential, fresh nonce) to `approved`, audit row decision + actor claim;
  `open` + decide-deny (operator credential, fresh nonce, note present) to
  `denied`, audit row decision + actor claim + note; `approved` + report-built
  (builder credential, profile id matches the approved profile, build id and
  digest present) to `built`, audit row build evidence; `built` + converge (a
  later heartbeat reports the recorded digest and the required probe passes) to
  `fulfilled`, audit row convergence evidence; `approved` + build-failed
  (builder credential, note present) to `open`, audit row failure + note;
  `built` + build-failed (builder credential, note present) to `open`, audit row
  failure + note; `fulfilled` + gap-regressed (a later heartbeat reports the gap
  again) to `open`, audit row regression; `denied` + report-suppressed (within
  the suppression window) to `denied`, audit row no state change; suppression
  counter; `denied` + report-after-window (suppression window elapsed) to
  `open`, audit row reopen
- **AND** `report-suppressed` and `report-after-window` are decided against
  `TOOL_REQUEST_SUPPRESSION_DAYS` as defined in `mon-tc-06`; this table names the
  event and that paragraph owns the number, so the window cannot acquire two
  values

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

#### Scenario: nothing installs software on a runner

- **WHEN** any code path in this capability runs
- **THEN** none SHALL execute a package manager or otherwise install software on
  a running runner

#### Scenario: the evaluator image fields are not this capability's

- **WHEN** the hub records lane image identity
- **THEN** this capability SHALL NOT read, write, or reinterpret the registry's
  evaluator image fields: `image_digest` and `image_pin_divergence` describe the
  coherence evaluator image, and the pin-divergence check (img-cycle-05) is
  unrelated to lane images and is unchanged by this capability
- **AND** lane image identity SHALL be recorded in separate fields

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
`stale`, or `probe-failed`. A request in `open` or `approved` state SHALL
remain visible in the request set until it reaches `fulfilled` or `denied`. A
lane with no open requests SHALL NOT be presented as evidence that its
toolchain is complete unless its coverage state is `reported` and every request
for it is fulfilled.

#### Scenario: the coverage states are distinguished by evidence

- **WHEN** a lane's coverage state is derived
- **THEN** it is distinguished by whether the spoke has ever sent a gap field,
  whether the last report is older than the staleness threshold, and whether the
  last probe run was incomplete

#### Scenario: the windows are fixed numbers, in one place

- **WHEN** a window is read
- **THEN** both the staleness threshold and the fulfillment window are numeric
  values defined by this capability, not left to an operator's judgement; they
  are fixed here, in one place, and `mon-tc-04`'s transition table reads its
  suppression window from this paragraph rather than restating it — the
  two-places failure that made task 0.1 read "16 names" beside a 17-name list is
  the exact defect this avoids
- **AND** `TOOL_REQUEST_STALE_AFTER_S` is **900 seconds** — three missed
  heartbeats at the 300-second cadence (design.md, Sec. Risks). Derived: a lane
  silent for two cadences may be mid-tick; three is the first count that cannot
  be a skipped tick, and coverage is `stale` rather than `reported` after it
- **AND** `TOOL_REQUEST_FULFILL_WINDOW_S` is **86400 seconds** (24 hours). An
  `approved` request with no build report past this age is reported outstanding
  with its age; approval produces an image rebuild, and a day is the point at
  which a rebuild that has not happened is itself the finding. This is a
  judgement within an envelope, not a derivation — it is the one number here
  whose correct value depends on the fleet's build-queue latency, which this
  repository cannot observe. It is stated as a judgement so a reviewer can
  overrule it rather than inherit it silently
- **AND** `TOOL_REQUEST_SUPPRESSION_DAYS` is **14 days**. A `denied` request
  re-reported inside the window leaves the row `denied` and advances the
  suppression counter; reported after it, the row reopens to `open`. Also a
  judgement: a denial means the lane does not need the tool, and two weeks is the
  shortest interval at which a re-report is more likely a changed decision or
  profile drift than the same request again
- **AND** a value set to zero or to an unbounded sentinel is a specification
  violation, not a configuration: it makes `stale` unreachable or the
  suppression counter meaningless, and both are states `mon-tc-06` exists to
  make visible

#### Scenario: an approved request is never built
- **WHEN** an approved request passes the fulfillment window with no build
  report
- **THEN** it is reported as outstanding, naming its age
- **AND** an `approved` request not built within the fulfillment window SHALL be
  reported as outstanding with its age

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