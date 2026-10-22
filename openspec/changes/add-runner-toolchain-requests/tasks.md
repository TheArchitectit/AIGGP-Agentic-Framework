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

## S3 — Hub: fulfillment evidence (mon-tc-05)

- [ ] 3.1 `built` requires builder credential + matching profile id + build id +
      digest; mismatched profile refused.
- [ ] 3.2 `fulfilled` requires a later heartbeat with that digest **and** a
      passing probe. Digest present, probe failing → stays `built`.
- [ ] 3.3 Digest under operator or runner credential refused.
- [ ] 3.4 Approval alone never reaches `fulfilled`.

## S4 — Spoke detection (mon-tc-01)

- [ ] 4.1 `scripts/runner-heartbeat.sh`: required-profile minus observed, probed
      inside the runner image, never host `PATH`.
      `tests/test_runner_toolchain_probe.py`
- [ ] 4.2 Synthetic manifest `{required: [cargo, gcc], observed: [gcc]}` →
      reports `[cargo]`, exit 0.
- [ ] 4.3 Required equals observed → empty list, not a vocabulary dump.
- [ ] 4.4 Probe timeout → `unknown`, exit 0, never "complete".
- [ ] 4.5 `python3` present without the pip module → `pip` reported absent.

## S5 — Mission Control (separate repository)

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

## S6 — Gates and docs

- [ ] 6.1 `python3 -m pytest tests/test_hub_toolchain_requests.py
      tests/test_hub_operator_auth.py tests/test_runner_toolchain_probe.py`
      Stays open **because two of the three files do not exist yet**:
      `test_hub_operator_auth.py` is an S2 deliverable (credential classes) and
      `test_runner_toolchain_probe.py` is an S4 deliverable (spoke probe). The S1
      half runs green: `test_hub_toolchain_requests.py` +
      `test_hub_toolchain_requests_wire.py`, **31 passed**. Marking this done now
      would be a box ticked against files nobody has written.
- [x] 6.2 `python3 -m pytest tests/test_hub_registry.py
      tests/test_hub_registry_schema.py tests/test_hub_enroll_heartbeat.py` →
      **44 passed**. Whole suite for reference: **1623 passed, 182 subtests
      passed**.
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
- [ ] 6.8 Operator documentation stating the loop **and** that approval
      produces an image rebuild, never a live install.

> Format validation is not acceptance. `openspec validate` passes an untestable
> spec; the tests above are what make it real.