# Tasks: runner-toolchain-requests

Every normative clause in the spec gets a positive test and a negative control.
Nothing here is marked complete from spec authoring.

`mon-tc-*` requirements are currently uncovered by source markers; that count
must be **read** at the end gate, not assumed. Proposed test files do not exist
yet.

## S0 — Contract, decided before code

- [x] 0.1 Freeze the tool vocabulary as spec-governed data, with the
      rule that adding one is a change, not a config edit. **The spec list has
      17 names, not the 16 this line used to assert**: `cargo`, `cmake`,
      `dotnet`, `gcc`, `g++`, `gitleaks`, `go`, `gradle`, `java`, `make`,
      `maven`, `node`, `npm`, `pnpm`, `pip`, `python`, `shellcheck`. The count
      was written before `shellcheck` joined the list (`98737e1` revised the
      spec, `db09f10` proposed it as "currently 17"); the list is normative and
      `mon-tc-01` now states the count as derived from it. No implementation
      hardcodes a count.
- [x] 0.2 Add the reviewed per-lane **toolchain profile** table mapping a lane
      to its required tools. Trusted input, never runner-supplied. Landed in
      `mon-tc-01` as 9 spec-governed profiles over the vocabulary. The
      lane→profile **assignment** is not in this repository: the proposal
      excludes lane names and host posture from a public repo, so the hub ships
      an empty assignment set (every lane `profile-unassigned`, reporting no
      gaps and never rendered as complete) and the reviewed mapping is populated
      by the operator as trusted input. That is the decision's real shape, not a
      placeholder to be filled by guessing lane names.
- [x] 0.3 Add `lane_image_ref`, `lane_image_digest`, `toolchain_profile_id` and
      `coverage` to the runner record. **Do not** touch `image_digest`,
      `image_reason`, or `image_pin_divergence` — they are evaluator-image
      fields (schema lines 49–60). Landed in `enroll()`, plus two fields the
      coverage requirement needs on the same record (`last_gap_report_at`,
      `toolchain_rejections`). All five default to `None`/empty, never to a
      clean-looking value: a default of `"none"` for the profile id would make
      every freshly enrolled lane report itself provisioned. The evaluator triple
      is untouched and pinned by an isolation test. `coverage` stores only
      `reported`/`probe-failed`/null; `stale` is **derived at read time**
      (`effective_coverage`) because a stored `stale` is a lie the moment the next
      heartbeat arrives. The schema declares all of these — adding them without
      declaring them broke `test_hub_registry_schema` (2 tests) exactly as the
      drift-guard intends, since `additionalProperties: false`.
- [x] 0.4 Define the credential classes and the builder/operator split from
      `design.md` Sec. Credentials. Operator auth is **decided there**, not here.
      Landed: the four classes are named in `mon-tc-03`; refusal is a single
      `rejected_credential_class` code carrying the class name and never the
      secret; a class not in the table is refused as `unknown`, so a new
      credential type cannot acquire a decision right by being unlisted.
- [x] 0.5 Set the numeric staleness threshold and fulfillment window in the
      spec; no operator judgement. Landed in `mon-tc-06`: probe bound **10s**,
      max reported entries **32**, staleness **900s** (three missed heartbeats at
      the 300s cadence, design.md Sec. Risks), fulfillment window **86400s**,
      suppression **14 days**, decision-note cap **512 chars** (the existing
      `FIELD_CAPS` value for `image_digest`, hub/server.py). Two are recorded in
      the spec as **judgements**, not derivations — the fulfillment window (turns
      on build-queue latency this repo cannot observe) and the suppression window
      — so a reviewer can overrule them rather than inherit them silently.
      `mon-tc-04`'s transition table now reads the suppression window from
      `mon-tc-06` instead of restating it, so the window cannot acquire two
      values.
- [x] 0.6 Record the single-principal v1 attribution limit in the audit-record
      format, per `mon-tc-03`. Landed: the record format is fixed in `mon-tc-03`
      and `principal` is stored exactly as claimed, with no display name or email
      invented by the hub. Because v1 issues from one operator credential every
      record shares a `credential_id`, and the request set exposes that rather
      than implying per-operator attribution the deployment cannot support.

## S1 — Hub: record requests (mon-tc-01, mon-tc-02)

- [x] 1.1 `hub/registry.py`: persist `toolchain_requests`, keyed `(lane, tool)`,
      with the version counter and append-only history. Landed as a collection on
      the registry document, with row identity `(lane, tool)` and row ids derived
      from the stored rows (`tcr-NNNN`, highest+1) rather than a counter field —
      a counter that drifts from the rows mints duplicate ids after a restart, and
      duplicate ids are the exact failure the identity rule exists to prevent. A
      pre-change registry loads with no such key and reads as an empty set, which
      mon-tc-06 insists is not the same statement as "every lane is provisioned".
      - The writing half lives in **`hub/toolchain_store.py`**, not inline: with
        the feature inline `registry.py` was **572 lines against DevGate's 500-line
        source hard limit**, and over that limit is a *blocking* `regression_check`
        failure in CI, not a warning (`tests/test_regression_sizes.py` stays green
        either way because it judges fixtures, so `pytest` alone does not see it).
        `Registry.record_gap_report` is the delegator. This is the same remedy
        `scan_view.py`'s own docstring records for `monitor.py` at 433 lines.
- [x] 1.2 Heartbeat accepts `missing_tools`; all-or-nothing validation against
      the vocabulary; unknown values rejected as a code plus counter, never
      stored.
      - `tests/test_hub_toolchain_requests.py::test_vocab_*`
      - negatives: non-member, wrong case, trailing newline, zero-width
        character, over-length list, non-string, nested list — each asserts a
        200 heartbeat, zero rows, and no submitted byte in any stored field or
        log line
      - Landed. Three details the task did not predict: the heartbeat **still
        returns 200** when the list is refused (a malformed gap report is a broken
        gap report, not a dead runner; a 400 would trade a visible health reading
        for an invisible one) and reports `toolchain_requests_recorded: 0` plus a
        `toolchain_rejection` code, so a discarded report is observable rather than
        silent — which is what mon-tc-02's "silently discarded is worse than
        rejected" actually asks for. The response echoes **no tool names**, so it
        cannot become a channel for reading back a rejected value. And the read is
        presence-aware (`data["missing_tools"] if "missing_tools" in data else
        UNREPORTED`) rather than `data.get(...) or []`: an `or []` turns a
        malformed report into "the lane said nothing" and hides a hostile value
        behind a null. A refused report still counts as the lane having *spoken*
        (mon-tc-06's question is "has a gap field ever arrived", not "was it
        valid"), so coverage advances while the rows do not.
- [x] 1.3 `g++` end-to-end: JSON, URL path, URL query, CSV export, HTML render.
      `tests/test_hub_toolchain_requests.py::test_gpp_*`, plus a static scan
      asserting the value never reaches a shell string or an unescaped regex.
      **Corrected against the spec, per "spec is source of truth": two of the five
      channels named here do not exist in this repository.** `hub/` has no CSV
      export and no HTML render; the operator surface is the JSON registry plus
      `hub/scan_view.py`/`hub/coherence_view.py`, which build plain-text sentences
      (the only `<tr>` in the tree is in `tests/test_regression_sizes.py`).
      Writing those two tests would have meant *inventing* both channels, and an
      invented channel tests the invention — so `test_gpp_byte_for_byte_end_to_end`
      asserts the property each channel must preserve (POST body → stored bytes) and
      pins the two failure modes an export would hit, `+` under urldecode and `g++`
      as a regex pattern (it is `g` with a doubled quantifier, i.e. it degenerates
      to matching a bare `g`, so `re.sub(tool, ...)` would strip every `g` from the
      wrong lines silently). The spec's own wording — "stored, exported, and
      rendered" — is forward-looking, not a claim that the exports exist; the
      exports arrive with the operator surface, and this task is done for the
      channels that exist.
- [x] 1.4 Concurrent identical reports (20 threads) still yield one row. Landed
      (20 live heartbeats over HTTP → one row, `version == 1`); lives in
      `tests/test_hub_toolchain_requests_wire.py`. The lock in
      `HubState.with_registry` is the mechanism, so the test is here for the day
      someone decides that lock is too coarse.
- [x] 1.5 Heartbeat omitting `missing_tools` leaves the registry byte-identical
      to pre-change behaviour and sets coverage `never-reported`.
      **These two clauses contradict each other and the spec, so they cannot both
      be satisfied as written** — the task is corrected here and the spec wins.
      `record_gap_report` is not called on absence, so a plain heartbeat leaves the
      rows untouched (byte-identical, satisfied). But *setting*
      `coverage: never-reported` on an omitting heartbeat would downgrade a lane
      that reported yesterday, and mon-tc-06's coverage turns on whether the spoke
      has **ever** sent a gap field — so absence can never revoke a prior report,
      and `note_gap_coverage` is never cleared. What is asserted is the direction
      that matters: `never-reported` is the **derived** state of a lane that has not
      reported (freshly enrolled → `never-reported`, per `effective_coverage`),
      while a lane that reported stays `reported` across later plain heartbeats.
      `never-reported` is therefore a read-side conclusion, not a field a heartbeat
      writes.
- [x] 1.6 **Evaluator-isolation regression:** a heartbeat omitting the
      evaluator `image_digest` leaves it exactly as today. Note the real
      behaviour: `heartbeat()` defaults the field to `UNREPORTED` and assigns
      only when it is not, so *omitting* preserves the stored value and an
      explicit `null` clears it (`hub/registry.py:309`). Assert that, not the
      review's paraphrase. Files: `tests/test_hub_registry.py`,
      `tests/test_runner_heartbeat_image.py`, `tests/test_hub_monitor_image.py`.
      Confirmed by reading the code — that is exactly the shipped behaviour, and the
      new `missing_tools` parameter was appended **after** `address`, so no existing
      positional call changed meaning. Pinned by
      `test_evaluator_image_fields_are_untouched_by_the_gap_path`: the gap path must
      not write `lane_image_digest` (the *lane's* toolchain image), an omitted
      evaluator digest survives a gap heartbeat, and the evaluator triple keeps its
      `UNREPORTED` semantics. The pre-existing image suites are green unmodified.
- [x] 1.7 **Static scan:** no `subprocess`, `os.system`, `apt`, `pip`, `npm`,
      or `dnf` reference anywhere in the new hub module.
      **Corrected against the spec, per "spec is source of truth": as literally
      worded this scan fails the spec it protects.** `pip` and `npm` are *mandated
      members of the vocabulary* mon-tc-01 defines (as are `make`, `gcc`, `g++`), so
      they appear in the module by necessity and a grep for those strings would
      reject the spec's own list. The prohibition that actually exists is mon-tc-05's
      (no code path in this capability installs software) plus mon-tc-01's (nothing
      derives a shell word from a tool name), so the scan is an **AST walk for
      execution primitives** over `toolchain_requests.py`, `toolchain_store.py` and
      `registry.py`: shell modules (`subprocess`, `pty`, `pexpect`, …) and exec
      attributes (`system`, `popen`, `execv*`, `spawn*`, `Popen`, `run`, `call`,
      `check_output`). `import os` is allowed — atomic saves call `os.replace` — and
      a docstring that *mentions* shell handling is not flagged, which a string grep
      gets exactly backwards. A literal whole-word audit of command strings
      (`os.system`, `apt-get`, `pip install`, …) is kept alongside as the
      belt-and-braces check the task intended. **Positive control included**
      (`test_scan_has_a_positive_control`): a scan with no control also passes when
      it looks for nothing.

## S2 — Hub: transitions (mon-tc-03, mon-tc-04)

- [x] 2.1 Implement the normative transition table from `mon-tc-04` with
      compare-and-swap under the registry lock. Landed in
      `hub/toolchain_transitions.py` (`TRANSITIONS` mirrors the spec's own
      column order so it can be diffed page by page; CAS runs under the
      registry lock, the caller owns it and the save). `hub/toolchain_api.py`
      carries the HTTP seam (`POST /toolchain/decide`, id in the body) and
      `hub/registry.py`'s toolchain delegators moved to
      `hub/toolchain_registry.py` as a mixin because `registry.py` sat at the
      500-line source hard limit — now 477/500. Commit `1d51289`.
- [x] 2.2 Concurrent decisions: exactly one 200, one 409, both in audit
      history. `tests/test_hub_operator_auth.py::test_concurrent_decisions`
      and its wire twin `test_wire_concurrent_decisions`.
- [x] 2.3 Idempotency: an identical decision at an already-applied version
      returns that outcome and applies no second transition.
      `test_idempotent_decision`. The content match is event + actor + note —
      v1 has one shared operator credential, so a different actor presenting
      the same content at an applied version is a conflict, not that
      outcome's replay (the docstring states this; the shared-credential
      limit is task 0.6's recorded v1 attribution limit).
- [x] 2.4 Replay: a consumed nonce is refused.
      `tests/test_hub_operator_auth.py::test_replay_nonce`.
- [x] 2.5 Negative controls, each asserting refusal, unchanged state, and an
      audit row: heartbeat token, runner key, builder credential, ordinary MC
      write key, expired nonce. `test_negative_control_*` (three) +
      `test_expired_nonce` + `test_rejected_credential_classes`. The "expired
      nonce" control is a replayed consumed nonce: mon-tc-06 owns the numbers
      and names no TTL for the claim timestamp, so a nonce goes stale by being
      consumed, not by the clock — an earlier substring check on the fixture
      year (`"2020-"`) plus a dead 5-minute freshness helper were removed;
      both made the test pass for the wrong reason.
- [x] 2.6 `decision_note` capped, stored, and rendered escaped; static scan plus
      fixture asserting it never reaches a builder input, command or profile
      lookup. Cap is **512 imported** from
      `hub/toolchain_requests.DECISION_NOTE_MAX_CHARS`, refused-not-truncated
      (`test_note_cap`), stored verbatim and rendered escaped
      (`test_note_rendered_escaped_and_not_in_builder_input`, incl. the static
      scan). The schema caps the stored field at 512 too.
- [x] 2.7 Denied-recurrence and suppression-window behaviour, including
      fulfilled → open regression. `test_denied_suppression_window`,
      `test_fulfilled_gap_regressed`, plus `report_event` in
      `toolchain_transitions.py` for the three heartbeat cases.

## S3 — Hub: fulfillment evidence (mon-tc-05)

- [x] 3.1 `built` requires builder credential + matching profile id + build id +
      digest; mismatched profile refused.
      `tests/test_hub_toolchain_evidence.py` (engine, 29) and
      `tests/test_hub_build_report_wire.py` (route, 9). Three calls the spec
      left open, recorded because each is arguable:
      (a) **A new route, not a heartbeat field.** Build evidence is
      authenticated by a *builder* credential; the heartbeat channel
      authenticates a lane. Putting it on the heartbeat would either let a lane
      report its own image built or bolt a second credential type onto a route
      whose security story is one token. `POST /toolchain/build-report`
      classifies the presented secret server-side (mon-tc-03) and refuses every
      other class — the body carries no `class` field to believe.
      (b) **`digest: null` means `build-failed`.** mon-tc-04's table has a
      builder-guarded `build-failed` event and the spec never says how a failure
      arrives; a null digest is the only shape that already means "no image
      exists". An *omitted* digest key is refused 400 as ambiguous — a client
      that forgot a field must not reopen a request it never observed. A failed
      build clears `build_id`/`lane_image_digest`: a dead build's digest must not
      linger as something a lane could later converge onto.
      (c) **"Matching the approved profile" is strict equality** — both sides
      must name a profile and agree. A row whose assignment was cleared after
      approval refuses rather than matching None to whatever got built.
      `expected_version` is **required** on this route (400 without): mon-tc-05
      asks no nonce of build reports — CI retries are the normal case — so CAS
      is the ONLY duplicate defence, and a report with no version is the one
      case it cannot guard. No nonce-replay test exists here by design; the
      asymmetry against the operator path is the spec's, and the engine's
      docstring says so where a future reader will look for it.
- [x] 3.2 `fulfilled` requires a later heartbeat with that digest **and** a
      passing probe. Digest present, probe failing → stays `built`.
      `test_digest_plus_clean_probe_fulfills`,
      `test_digest_with_the_tool_still_missing_stays_built`,
      `test_a_refused_gap_list_never_reads_as_a_passing_probe`,
      `test_no_gap_field_and_no_prior_report_never_converges`,
      `test_probe_failed_coverage_never_converges`,
      `test_the_lanes_digest_alone_can_satisfy_nothing`.
      **"The probe passes" is strictly same-tick**: an accepted gap list from
      THIS heartbeat without the row's tool, and no spoke-flagged incomplete
      run. The tempting staleness fallback ("last clean report was under 900s
      ago") was written, tested green, and deleted: coverage `reported` is set
      even by a *refused* report (mon-tc-06 counts a malformed report as
      "spoke"), so the fallback would credit presence to a report that never
      said clean, and no stored timestamp separates "last accepted clean" from
      "last spoke somehow". A spoke predating the probe field therefore never
      converges a row — mon-tc-05 demands probe evidence; a hub that fulfilled
      without it would fulfill on absence, the sentence this capability exists
      to deny. The halves may land on different ticks **in the safe direction**:
      a stored digest converges against a later clean list; never the reverse.
      A bug this test suite killed at birth: `registry.py` first forwarded
      `[] if rejection is None` instead of the accepted list — every honest
      "cargo is still missing" became "nothing is missing" and rows converged
      that had no business converging.
      `test_digest_with_the_tool_still_missing_stays_built` is its keeper.
      **The spoke cannot report its own digest in this deployment, and no fake
      was wired to pretend otherwise.** Lanes are host systemd units with no
      container identity (`RUNNER_CONTAINER` does not exist in the tree), so
      "the image this lane is running" has no honest source on the tick; the
      digest env key is fleet-side work. The hub half is complete and wired
      (presence-aware `lane_image_digest` on `/heartbeat`, capped like the
      evaluator's); convergence activates the day a lane can report truthfully.
- [x] 3.3 Digest under operator or runner credential refused.
      `test_digest_under_the_operator_credential_is_refused`,
      `test_digest_under_a_heartbeat_token_is_refused` — the latter presents the
      lane's REAL captured token so "runner credential" is proven for the class,
      not approximated by an unknown string; also
      `test_build_report_refuses_operator_credential_over_the_wire` (the refusal
      is the route's, not a client courtesy),
      `test_an_unpresented_credential_is_401_not_403`, and
      `test_a_builder_credential_without_an_identity_is_refused` (attribution
      comes FROM the credential; a nameless builder is a hub misconfiguration
      and refusing says so rather than storing unattributable evidence).
- [x] 3.4 Approval alone never reaches `fulfilled`.
      `test_approved_never_converges_no_matter_what_the_lane_reports` — the row
      holds the digest, the lane reports the same digest, a clean probe arrives:
      still `approved`, because the awaited digest lives on the BUILDER's report
      and `(approved, converge)` has no table rule. The awaited-vs-reported
      asymmetry is stated in the engine's docstring and tested directly:
      `test_an_unmatched_digest_clears_the_dead_wait_once_and_stays_visible` —
      a lane reporting a different digest clears the dead wait (state stays
      `built`, visible per mon-tc-06 — reopening under `build-failed` would
      misattribute to a builder credential the lane does not hold), logged ONCE
      per digest, not every 300s tick.

## S4 — Spoke detection (mon-tc-01)

- [x] 4.1 `scripts/runner-heartbeat.sh`: required-profile minus observed, probed
      inside the runner image, never host `PATH`.
      `tests/test_runner_toolchain_probe.py`
      **Two things the task text assumed and the code had to decide, recorded
      because they are load-bearing.** (a) *How the spoke learns the profile.* The
      spec makes the required profile trusted hub input a heartbeat cannot set, and
      forbids the spoke computing it — so the hub now echoes this lane's resolved
      requirement list on the `/heartbeat` response and the tick caches it for the
      next one. design.md's Sec. Detection never says where that value crosses the
      wire, so this is an addition to the design, not a reading of it. A first tick
      has no cache and sends **neither** gap field (absent, never `[]`: mon-tc-06
      says absence means the hub has no evidence). The echo travels on every
      successful heartbeat, including one carrying no gap field, because gating it
      on an incoming gap field deadlocks the capability: no cache → no gap field →
      no echo → no cache. (b) *"Never host PATH" is only true when the operator
      sets the knob.* The probe observes `RUNNER_PROBE_PATH` when set, else the
      process `PATH` — and today's units run on the host, so an unset knob observes
      the host. That is the deployment's limitation rather than the probe's, and
      the honest wording is that the suite never runs with it unset, so "never host
      PATH" is enforced for everything the suite can see and asserted nowhere in
      prose. A containerised lane needs the knob set, and that is a fleet-side
      change this repository cannot make for it.
      Absent probe library, torn cache and an unreadable cache all end as absent
      fields with exit 0, the shape the evaluator-image probe already used: a
      heartbeat that dies blinds the fleet, which is worse than a toolchain field
      that reads unknown. Installed as a sibling by `lib/runner-installs.sh` (a
      new sourced library; the install set crossed the size gate's hard limit and
      the gate's own history says to move the operation, not widen the limit).
- [x] 4.2 Synthetic manifest `{required: [cargo, gcc], observed: [gcc]}` →
      reports `[cargo]`, exit 0.
      `test_the_manifest_the_task_names_required_cargo_gcc_observed_gcc` — the
      literal pair, its own stub directory, asserting `(["cargo"], True)`. It was
      first written reusing the neighbouring test's directory, which contains
      `cargo`, and it asserted the opposite of the truth while passing nothing: a
      missing tool needs a directory that lacks it.
- [x] 4.3 Required equals observed → empty list, not a vocabulary dump.
      `test_a_lane_that_has_everything_reports_the_empty_list` — `[]` posted, exit
      0. This case was **not covered before it was written for this box**: every
      earlier test had a gap by construction, so "vocabulary minus what I have"
      would have passed the whole suite while opening a request per tool nobody
      required.
- [x] 4.4 Probe timeout → `unknown`, exit 0, never "complete".
      `test_a_probe_that_outlives_its_bound_is_unknown_not_absent` (through a real
      tick) and `test_required_excludes_unknowns_from_missing_and_reports_incomplete`
      (at the library). Both halves are asserted because the first alone is not
      enough: excluding the unknown tool from `missing` without setting the flag
      would hand the hub an empty gap list from an incomplete run — absence
      reported as health, which is the one thing `probe-failed` exists to prevent.
      The stub is named `mvn`, since mon-tc-01 fixes maven's probe as
      `mvn -version`; a stub named `maven` would be a file the probe never looks
      at, and an earlier draft of this test passed for that reason.
- [x] 4.5 `python3` present without the pip module → `pip` reported absent.
      `test_python_is_python3_and_pip_is_the_module_not_the_binary` — a stub
      `python3` that exits 1 under `-m pip` yields `absent` while `python` itself
      is `present`. The probe runs the **resolved** interpreter rather than a bare
      `python3`, because a bare name falls through to the process PATH and would
      probe the host while claiming to probe the image.


## S5 — Mission Control (separate repository)

Live tree is the `mission-control-rs/` directory inside
`TheArchitectit/missioncontrol` (Askama + HTMX + axum). The standalone
`TheArchitectit/mission-control-rs` repository is **not** the live tree; retire
or label it.

- [ ] 5.0 Write the MC companion OpenSpec change **first**, including the
      auth-gate-coverage classification of the decide route. Pin both commit
      SHAs in the pull request.
- [x] 5.1 Hub adapter: `src/adapters/` alongside `hermes.rs`, `loki.rs`,
      `rad_a2a.rs`. Explicit timeout. No local cache.
      **Landed in MC `d084f78`.** `src/adapters/toolchain.rs`; timeout on every
      call (`TOOLCHAIN_HUB_TIMEOUT_SECS`, default 10, clamped 1..=120); the only
      in-memory state is `LAST_GOOD_READ`, a timestamp for the failure banner,
      explicitly not a cache (the served queue comes only from the live hub
      response).
- [x] 5.2 Protected read `GET /api/v1/fleet/toolchain-requests` proxying to the
      hub, no storage. Fleet code belongs in `src/api/fleet/`, routes register
      in `src/router/builder.rs` — there is no `src/api/dashboard.rs`.
      **Landed in MC `d084f78`.** Handler in `src/api/fleet/toolchain.rs`,
      registered under `/api/v1/fleet` in `src/router/builder.rs`; anonymous
      read is 401 and by construction cannot reach the hub
      (`read_anonymous_is_401`).
- [x] 5.3 Decide POST behind session auth + CSRF + an administrative-tier check
      modelled on `/api/v1/keys`. Proxies to the hub with the actor claim.
      **Landed in MC `d084f78`.** Session+CSRF (`decide_cookie_without_csrf_is_403`),
      admin tier via the existing prefix match
      (`decide_write_only_key_is_403`); the forwarded claim is principal,
      timestamp and nonce plus the operator credential, all body fields — the
      signed claim once assumed here never existed on the hub and was removed
      (see MC tasks 3.3's correction and the seam findings).
- [x] 5.4 Askama + HTMX queue page in the page-gated tier.
      `tests/toolchain_queue_contract.rs`
      **Landed in MC `d084f78`.** `templates/pages/toolchain_queue.html`; the
      decide controls are real forms carrying the row's `expected_version`, and
      the urlencoded form post is exercised end to end in
      `tests/toolchain_wire_contract.rs::form_encoded_decide_from_the_page_reaches_the_hub`
      — no prior test in either repo could see that path.
- [x] 5.5 Schema-scan test: the MC database contains no toolchain table.
      **Landed in MC `d084f78`.** `tests/toolchain_no_local_state.rs` queries
      `information_schema` for any public table matching `%toolchain%`.
      Mutation-checked: creating `toolchain_requests_mutation_probe` turns it
      red naming the table; dropping it returns green; residue verified zero.
- [x] 5.6 Hub unreachable → explicit payload naming the last good read time,
      never `[]`.
      **Landed in MC `d084f78`.** `render_unreachable` names the last good read
      when one exists and says "no successful read since start" when none does;
      `unreachable_read_is_502_never_empty` asserts the payload never contains
      `"requests":[]`, and a hub that answers empty is a separate test proving
      empty ≠ unreachable.
- [ ] 5.7 Reconcile the stale `frontend-architecture` spec text as part of the
      companion change (it still says the React SPA "SHALL be removed" while a
      later decision admits React islands on six routes).
- [x] 5.8 **Hub-side, executed in this repo:** make the request-set read carry
      what a queue needs to render a row and act on it — the lane's repository
      and host alias, the lane's coverage state derived at read time, and the
      row's `version`. Opened because S5 could not otherwise close: MC is
      forbidden a copy to join against (mon-tc-02), so those fields have no
      other source, and a consumer that cannot read `version` cannot satisfy
      mon-tc-04's compare-and-set from the only surface an operator has. The
      seam decision and the measurements behind it are in
      `repo-brainstorming/FINDINGS-2026-10-23-toolchain-queue-seam-decision.md`:
      **MC moves to the hub's contract, and the hub does not adopt MC's
      HMAC**, because that signature appears in no spec in either repo
      (`grep -rn "X-Actor\|CLAIM_SIGNING_KEY" openspec/` → no matches in both)
      while MC's own spec asks only for "a principal, a timestamp and a unique
      nonce" — the three mon-tc-03 already names.

      Landed as `hub/toolchain_queue_read.annotate_requests`, a **read-time
      projection** called from `handle_list_requests`: nothing is written onto a
      row, because copying lane facts onto the request would make the hub the
      second divergent copy mon-tc-02 forbids everyone else, and it would go
      stale against the runner record on re-enroll. Unknowns are `null`, never
      `""` and never a defaulted coverage state — a blank cell says "lane with
      no repository", `null` says "the hub does not know", and mon-tc-06's whole
      vocabulary rests on not collapsing a verdict into an absence.

      Two claims in my own first draft of this box did not survive checking and
      are corrected here rather than left in place: the row-gone-lane case is
      **not** reachable via revoke (`revoke` marks `enrolled=False` and clears
      the verifier, `hub/registry.py:417-425`; nothing in `hub/` removes a
      runner record), so the null branch is a robustness case for a partially
      restored registry, and the test says so; and the four unit tests failed
      under `pytest` while passing standalone because the hand-rolled registry
      double had no `runners()` method — I had written "7/7 both ways" before
      running the dual runner, which is the same unverified-green claim this
      program keeps recording in other people's commits.

      Evidence: `tests/test_hub_queue_read_fields.py` → **6 passed** under
      `pytest` and **6 ok** via the file's own `__main__` runner, exit 0, both
      measured. Mon-tc-02's requirement text amended (the read's obligation +
      two scenarios) and `openspec validate --all --strict` re-run after the
      amendment.

      **Correction 2026-10-23 (spec audit):** this box said "Hub toolchain
      suites together: **71 passed**". That number does not reproduce and never
      matched the set — the six toolchain test files sum to **89 test
      definitions at `019f6a3`**, which is also the pytest count today (89
      passed). The `71` is replaced rather than explained: no grouping of the
      files yields it. The reproducible figure, measured by running
      `pytest` over `tests/test_hub_*toolchain*.py` +
      `tests/test_hub_queue_read_fields.py`: **89 passed**.

## S6 — Gates and docs

- [x] 6.1 `python3 -m pytest tests/test_hub_toolchain_requests.py
      tests/test_hub_operator_auth.py tests/test_runner_toolchain_probe.py` →
      **57 passed**, measured by running that command verbatim. It was left open
      while two of the three files did not exist; both now do —
      `test_hub_operator_auth.py` (S2, credential classes) and
      `test_runner_toolchain_probe.py` (S4, spoke probe, 15 tests). The S1 half
      that was green alone is now joined by `test_hub_toolchain_record.py` (6
      tests, measured 2026-10-23 — the "13" this box carried does not reproduce;
      the file is 148 lines with six `def test_`, no subtests, and no later
      commit splits it) and `test_hub_toolchain_requests_wire.py` (9), split out
      when the requests module crossed the suite's own 600-line test gate. Whole
      suite for reference: **1664 passed, 182 subtests passed**, exit 0;
      re-measured 2026-10-23 → **1708 passed, 182 subtests**.
- [x] 6.2 `python3 -m pytest tests/test_hub_registry.py
      tests/test_hub_registry_schema.py tests/test_hub_enroll_heartbeat.py` →
      **44 passed** (re-measured 2026-10-23, still 44). Whole suite for
      reference: **1623 passed, 182 subtests passed** at authoring time;
      re-measured 2026-10-23 → **1708 passed, 182 subtests**, the growth being
      tests added after this box was written.
- [x] 6.3 `python3 scripts/spec_traceability.py --root . --report` — **read**, not
      just run. **81/127 requirements covered** (was 78 before this work). The
      three newly covered are exactly `mon-tc-01`, `mon-tc-02`, `mon-tc-06`;
      `mon-tc-03`, `mon-tc-04`, `mon-tc-05` remain **UNCOVERED** because they are
      S2/S3 (transitions and fulfillment evidence), which this increment does not
      implement. Advisory, so a clean exit proves nothing — the number above is the
      evidence, and it says plainly that half the capability's requirements are
      still untested.
- [x] 6.4 `npx openspec validate --all --strict` → **33 passed, 0 failed (33
      items)**. Needed `npm install --no-save @fission-ai/openspec@1.13.0` per
      ci.yml; `npx` resolving a global copy is not equivalent for 6.5, which
      deliberately refuses a PATH binary.
- [x] 6.5 `bash scripts/specs-validate-negative-control.sh` → **passed**: strict
      validation refused the malformed fixture and named its designed defect
      (missing `## Purpose`), exit 1. The script requires
      `<repo>/node_modules/.bin/openspec`; a repo-root install is therefore part of
      the setup (`npm install --prefix . --no-save …`) — a bare `npm install`
      resolves the nearest `package.json` **upward**, which outside CI is a parent
      directory, and silently installs into the wrong tree.
      Also from this work: `scripts/regression_check.py --all` → **0 over hard
      limit**. Worth recording because `pytest` does not see it: `hub/registry.py`
      measured 572 lines against the 500-line source hard limit and that is a
      **blocking** CI failure, while `tests/test_regression_sizes.py` judges
      fixtures and stayed green throughout.
- [ ] 6.6 In Mission Control: `cargo fmt --all -- --check`,
      `cargo clippy --all-targets --all-features -- -D warnings`,
      `cargo test --all-features` with migrations applied, plus the auth-gate
      mutation gate showing the decide route classified and returning 401
      anonymous / 403 with a write-only key / 200 with admin.
- [ ] 6.7 Named green CI runs on the hub commit and the MC commit, with both
      SHAs and run URLs in the PR.
- [x] 6.8 Operator documentation stating the loop **and** that approval
      produces an image rebuild, never a live install.

      `docs/runbooks/toolchain-request-loop.md` (2026-10-23): actors and what
      each may do, the state machine and its three numeric windows (900 s
      stale, 86400 s fulfil, 14-day suppression), the decide wire and its
      refusals (credential class server-side, deny-requires-note, 512-char cap,
      409 version_conflict), and a plain statement that approval changes a row
      and produces an image rebuild — it never installs on a running host.
      Hosts and credentials stay out of this public repo.

> Format validation is not acceptance. `openspec validate` passes an untestable
> spec; the tests above are what make it real.