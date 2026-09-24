# Tasks: add-runner-image-cycling

## Sprint 1 — Decision and spec (this change)

- [x] 1.1 Record the problem: no mechanism provisions the pinned image
  (measured: not in `templates/runner/*`, not in `scripts/runner-enroll.sh`,
  not in `hub/`; the runner container mounts only `/_work`), and the publish
  job advances `:main` past the record on every push (measured: served
  `61170a5c…` vs recorded `f470110c…`, stable across two runs)
- [x] 1.2 Record the refusal: runners cycle, they do not advance the pin
  (`design.md` D4) — no repo write authority on fleet hosts
- [x] 1.3 Delta spec `specs/runner-image-cycling/spec.md` with
  `img-cycle-01` … `img-cycle-06`

## Sprint 2 — The convergent cycle

- [x] 2.1 `scripts/runner-image-cycle.sh`: resolve the pinned digest, pull the
  digest-qualified ref only when absent, prune the superseded build, verify
  through the job-side path, exit non-zero on store mismatch (img-cycle-01,
  img-cycle-02). The store is a required input (`COHERENCE_PODMAN_STORE`,
  design D3.1) — every call carries `--root`, and the tick asks podman which
  graph root that resolves to before it pulls anything; exit 5 names both paths
- [ ] 2.2 Unit the tick beside the heartbeat in `runner-enroll.sh` (same
  install path, same per-runner EnvironmentFile, same "never inline into
  ExecStart" constraint), and document the store-namespace choice in
  `templates/runner/README.md` + `add-a-runner.md` — including that
  `COHERENCE_PODMAN_STORE` must name the store the runner container's job
  reaches (design D3.1's residual limitation)
- [x] 2.3 Tests: absent → pull; present → no pull; wrong-store verification →
  non-zero naming the mismatch; tag ahead of record → tag not followed.
  Mutation-kill each guard by exactly one named test — 17 tests, 18-mutation
  battery, no survivors. Two guards were strengthened after the audit pass:
  a required-env guard must name the variable (a `set -u` crash looks
  identical to a refusal to any caller checking only rc), and the stub honours
  `--format` field order (a format/parse drift would have silently stopped
  pruning with every behavioral test still green)
- [x] 2.4 Prune scope, measured not assumed (2026-09-24, real podman): the
  `reference=` filter matches image NAME and crosses registries; `rmi <id>`
  takes every name an ID carries; a digest-pulled image lists `Tag <none>`
  while a local build lists a tag. So an ID is reaped only when every row it
  appears in is this repository *and* tag-less *and* not the pinned digest —
  a host's local `devgate-coherence:<tag>` (the very tag the CI build job
  makes) survives

## Sprint 3 — Reporting

- [ ] 3.1 Extend the heartbeat payload with `image_digest` / `image_reason`
  (`scripts/runner-heartbeat.sh`), accepting the fields in the hub
  (`hub/registry.py`, `hub/schema/runners.schema.json`) with nullable
  defaults, rendered as unknown rather than healthy
- [ ] 3.2 Fleet view: a host with no pinned image shows the deficiency and
  reason (mon-registry-01, mon-online-01)
- [ ] 3.3 Tests for the null-vs-true distinction and for the schema's
  acceptance of the new fields

## Sprint 4 — Divergence reporting

- [ ] 4.1 Compare served `:main` digest against the record on the tick and
  raise an advisory (mon-alert-01) naming both digests; never fail the host's
  tick for it (img-cycle-05)
- [ ] 4.2 Replace the publish job's `::notice::`-only divergence report with
  the same advisory path

## Sprint 5 — The deliberate re-pin

- [ ] 5.1 Single operation that moves the registry digest, the template's
  `COHERENCE_IMAGE` / `COHERENCE_IMAGE_MANIFEST_DIGEST`, and `DEVGATE_PIN`
  together (img-cycle-04, design D7)
- [ ] 5.2 Re-run the chain guard as part of it; a pin whose tree does not
  carry the moved record fails closed
- [ ] 5.3 Tests: partial re-pin fails; pin predating the record fails;
  successful re-pin leaves every literal in agreement

## Sprint 6 — Make CI honest

- [ ] 6.1 Publish only on a deliberate trigger; the comment names that exact
  trigger (img-cycle-06)
- [ ] 6.2 A test that fails when the comment and the `if:` disagree

## Sprint 7 — Fleet evidence

- [ ] 7.1 Run the cycle on a real enrolled host and capture the log; confirm
  the gate on that host resolves the pinned ref without pulling
- [ ] 7.2 Record which storage shape the host uses (design D3 a or b)
