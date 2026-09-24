# Tasks: add-runner-image-cycling

## Sprint 1 — Decision and spec (this change)

- [x] 1.1 Record the problem: no mechanism provisions the pinned image
  (measured: not in `templates/runner/*`, not in `scripts/runner-enroll.sh`,
  not in `hub/`; the runner container mounts only `/_work`), and the publish
  job advances `:main` past the record on every push (measured: served
  `61170a5c…` vs recorded `f470110c…`, stable across two runs)
  - CORRECTION 2026-09-24: that pair was read through `podman image inspect`,
    which reports a local-storage value, so the *numbers* here are not the
    registry's. The divergence they evidence is real — it is visible in the
    registry's own `Docker-Content-Digest` too — but any future use of this
    measurement should take the registry's value; see 4.2's measured note.
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
  - MEASURED 2026-09-24, and it is worse than "notice only": the job's
    `served digest` line is **not a digest any registry serves.** After
    `podman pull --quiet "$IMAGE:main"` it prints
    `podman image inspect --format '{{.Digest}}'`, and a pull leaves that
    value on the local-storage axis — so run 36050827753 printed
    `served digest: sha256:6032c209…` for a tag the registry resolves to
    `sha256:fc7074e7…`, and an anonymous `podman pull …@6032c209…` returns
    `manifest unknown`. The remedy the comment prescribes ("re-resolve the
    pushed ref") is therefore insufficient: the source has to be the
    registry's own `Docker-Content-Digest` (or `skopeo inspect`), never
    `podman image inspect` on either axis. Recording a re-pin from that line
    is exactly how the S4 pin was recorded unpullable once already

## Sprint 5 — The deliberate re-pin

- [ ] 5.1 Single operation that moves the registry digest, the template's
  `COHERENCE_IMAGE` / `COHERENCE_IMAGE_MANIFEST_DIGEST`, and `DEVGATE_PIN`
  together (img-cycle-04, design D7)
- [ ] 5.2 Re-run the chain guard as part of it; a pin whose tree does not
  carry the moved record fails closed
- [ ] 5.3 Tests: partial re-pin fails; pin predating the record fails;
  successful re-pin leaves every literal in agreement

  EVIDENCE 2026-09-24 — the operation was performed by hand, and the hand
  version is the specification 5.1 should encode. The repository rename moved
  the publish path (`ci.yml:401` derives it from `GITHUB_REPOSITORY`, the only
  source of that path), so `:main` lands under the new name and the record
  still named the old package. Four literals moved, in **two commits and this
  order** — commit 1 is forced by `DEVGATE_PIN` needing a tree that already
  carries the new record, and the tests refuse every partial state:

  1. `dadfd1d8` — `container/execution-profiles.json`: `image` → the new path,
     `image_manifest_digest` → `fc7074e70752…`, `built` → 2026-09-24.
  2. `9dc6406f` — `templates/github-workflows/spec-coherence.yml`:
     `COHERENCE_IMAGE` → the new path, `COHERENCE_IMAGE_MANIFEST_DIGEST` →
     `fc7074e70752…`, `DEVGATE_PIN` → `dadfd1d8`.

  The digest moved because the **content** moved, not because the repository
  did: `container/Containerfile:39` COPYs `hub/`, and the rename sweep changed
  `hub/schema/runners.schema.json` (its `$id` carried the old name). Same
  bytes at a different path is not a new digest; different bytes is. Before
  the digest was recorded it was fetched the way the gate fetches it —
  anonymous pull by digest with `REGISTRY_AUTH_FILE=/nonexistent`, then
  `podman run --network=none --read-only --cap-drop=ALL` printing
  `schemas OK in fetched bytes`. Chain guard re-run as 5.2 requires: 58 tests
  across the four identity suites pass, including the pin-tree resolution.
  Still open, and the reason 5.1 is not done by this evidence: nothing here
  *enforces* the two-commit order, and nothing re-runs the guard
  automatically — a future hand re-pin can still do it in the wrong order and
  only find out from CI.

## Sprint 6 — Make CI honest

- [ ] 6.1 Publish only on a deliberate trigger; the comment names that exact
  trigger (img-cycle-06)
- [ ] 6.2 A test that fails when the comment and the `if:` disagree

## Sprint 7 — Fleet evidence

- [ ] 7.1 Run the cycle on a real enrolled host and capture the log; confirm
  the gate on that host resolves the pinned ref without pulling
- [ ] 7.2 Record which storage shape the host uses (design D3 a or b)
