# Tasks: runner-toolchain-requests

Work is grouped so that each group leaves the system in a state that is
explained rather than silently broken. Nothing here is marked complete on
authoring a spec.

## S0 — Vocabulary and contract

- [ ] 0.1 Freeze the tool vocabulary as spec-governed data (currently 17
      names), with the rule that adding one is a spec change, not a config edit.
- [ ] 0.2 Define the request record shape (`design.md` §Data shape) and add it
      to `hub/schema/runners.schema.json` as `toolchain_requests`.
- [ ] 0.3 Decide operator auth (design D4) and record the choice in the
      decision log; the requirement is that it is not a heartbeat token.
- [ ] 0.4 Update `AGENTS.md` namespaces to include `mon-tc-*`.

## S1 — Hub: record requests

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

## S2 — Hub: decide requests

- [ ] 2.1 Add the transition endpoint; require operator auth distinct from
      `HEARTBEAT_TOKEN`; record author and timestamp (mon-tc-03).
- [ ] 2.2 Negative control: heartbeat token presented to approve is refused,
      state unchanged, refusal recorded (mon-tc-03).
- [ ] 2.3 Deny path with a retained decision note.

## S3 — Hub: fulfillment

- [ ] 3.1 Fulfillment record carrying a digest; state → `fulfilled` (mon-tc-04).
- [ ] 3.2 Negative control: approval alone does not reach `fulfilled`, and no
      code path in this capability invokes a package manager.
- [ ] 3.3 Outstanding reporting for approved-but-unbuilt requests past the
      window (mon-tc-05).

## S4 — Spoke

- [ ] 4.1 `scripts/runner-heartbeat.sh`: detect the image's toolchain against
      the vocabulary and report the difference.
- [ ] 4.2 Host-side unit test with a synthetic toolchain manifest; the
      heartbeat must exit 0 whether or not a gap exists.

## S5 — Mission Control (separate repo `mission-control-rs`)

- [ ] 5.1 Hub client under `src/adapters/`; MC holds no fleet request state of
      its own (mon-tc-02).
- [ ] 5.2 Dashboard route beside `src/api/dashboard.rs` listing open requests
      with lane context.
- [ ] 5.3 Approve / deny actions carrying operator auth.
- [ ] 5.4 Frontend queue; absence of requests must not read as
      "toolchain complete" (mon-tc-05).
- [ ] 5.5 MC-side OpenSpec change in `mission-control-rs` governs this work;
      this repo governs only the hub contract.

## S6 — Gate + docs

- [ ] 6.1 `scripts/spec_traceability.py` coverage for every `mon-tc-*`
      requirement; the gate is advisory today, so this must be verified by
      running it and reading the count, not assumed.
- [ ] 6.2 `openspec validate --all --strict` green.
- [ ] 6.3 Operator documentation: the request loop, and the explicit statement
      that approval produces an image rebuild, never a live install.
- [ ] 6.4 Failure-registry entry if any incident surfaces during the work.