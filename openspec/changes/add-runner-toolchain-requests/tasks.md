# Tasks: runner-toolchain-requests

Every normative clause in the spec gets a positive test and a negative control.
Nothing here is marked complete from spec authoring.

`mon-tc-*` requirements are currently uncovered by source markers; that count
must be **read** at the end gate, not assumed. Proposed test files do not exist
yet.

## S0 — Contract, decided before code

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

## S1 — Hub: record requests (mon-tc-01, mon-tc-02)

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