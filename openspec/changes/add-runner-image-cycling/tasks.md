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
  - FIXED 2026-09-24 (commit `413167e`), and the finding was bigger than this
    item: the same wrong-axis read was in the HARD GATE too, which went red on
    a correct pin (run 36052355931 — the anonymous pull landed and the
    comparison failed it anyway). Both are fixed: the gate now decides on the
    pull alone (which verifies the fetched manifest against the requested
    digest) and never reads a local `.Digest`; the publish job reads
    `Docker-Content-Digest` from the registry API. Killed by one named test
    each, executing the step against a podman stub that refuses to echo the
    requested digest; 2 mutations, 2 killed. What remains of 4.2 is the
    advisory half — raising this as a fleet alert rather than a run notice.
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

- [x] 5.1 Single operation that moves the registry digest, the template's
  `COHERENCE_IMAGE` / `COHERENCE_IMAGE_MANIFEST_DIGEST`, and `DEVGATE_PIN`
  together (img-cycle-04, design D7) — `scripts/re-pin-evaluator-identity.sh`.
  It resolves the digest from the REGISTRY (anonymous token,
  `Docker-Content-Digest`), never from `podman image inspect`; verifies the
  bytes are fetchable anonymously *before* recording them; writes the record
  commit, then the template commit pinned at it; and refuses a dirty tree, a
  malformed template, a ref the registry serves nothing for, and unfetchable
  bytes. Exit codes 1–5 separate those refusals, so a caller can tell them
  apart. `REPIN_CHECK_ONLY=1` runs the guard alone — verified against this
  repository: it reports the pin `dadfd1d8` carries `fc7074e7…`
- [x] 5.2 Re-run the chain guard as part of it; a pin whose tree does not
  carry the moved record fails closed — `verify_pinned_identity` runs inside
  the script at the end of a re-pin and standalone under `REPIN_CHECK_ONLY=1`,
  so the guarantee the operation claims and the guarantee an operator can
  re-check are one implementation. It is not only the digest that is compared:
  a template naming a different IMAGE with the digest left alone is refused
  too, which is the rename's own failure mode
- [x] 5.3 Tests: partial re-pin fails; pin predating the record fails;
  successful re-pin leaves every literal in agreement — 20 tests in
  `tests/test_repin_operation.py`, each running the real script against a real
  (temporary) git repository with stubbed `curl` and `podman` on PATH. The
  podman stub deliberately reports a digest NO registry serves, so a run that
  recorded it would be visible. Mutation battery: 15 mutations, 0 survivors,
  each guard killable by a named test

  AUDITED 2026-09-24, and the audit mattered more than the first draft. A
  fresh-eyes pass found nine defects in a version that already passed its
  tests, four of them able to ship a broken pin:

  1. **A detached HEAD exited 0 with a pin no consumer can resolve.** The
     guard proved the pin *existed* locally (`git cat-file -e`), not that it
     was *reachable* — and reachability is the property a consumer depends on.
     Committing on a detached HEAD makes both commits dangling: printable
     here, fetchable by nobody. Now the operation refuses a detached HEAD
     before writing, and the guard requires the pin to be an ancestor of HEAD.
  2. **`REPIN_PROFILE` left a half-moved repository**, with commits and no
     rollback: it moved the record's profile but never the template's
     `COHERENCE_PROFILE`, so the guard refused *after* both commits landed.
     The option is GONE — `COHERENCE_PROFILE` decides which profile the gate
     reads, so a knob that moves a different one cannot move the pinned
     identity at all.
  3. **A re-run against an already-current identity crashed.** The record edit
     produced no diff, so there was no commit to make, and `git commit` failed
     with rc 1 — after the script had printed that it was about to move the
     pin. Nothing-to-move is now a success, and the pin is kept rather than
     re-pointed at HEAD.
  4. **Any commit failure left one side applied** and exited an out-of-table
     code (128 for a missing git identity). Commits now restore the tree and
     exit 6.

  The other five: the guard's command substitutions failed *silently* (bash
  disables errexit inside `if func`), reporting a digest mismatch where the
  real fault was a malformed pinned record; `REPIN_CHECK_ONLY` compared two of
  the four literals and printed a digest it had not verified; YAML-quoted
  literals were compared with their quotes on, refusing a correct tree with
  two indistinguishable strings; a transient registry outage was diagnosed as
  an absent image; and two test holes — deleting the entire post-write guard
  left the suite green, and the image assertion was vacuous because the
  fixture passed the same image to both files. The guard now proves four
  pairs (pinned tree *and* working tree, against the template) and every
  failure is an explicit exit naming what disagreed.

  Verified against the real registry and the real template shape, not only the
  fixture: on a scratch clone the operation resolved `fc7074e7…` from ghcr by
  anonymous token, verified the anonymous pull, correctly found nothing to
  move, and kept the pin at `dadfd1d8` — zero commits written.
  `REPIN_CHECK_ONLY=1` on this repository reports the same pin carrying the
  same digest.

  NOT DONE, and not claimed: the operation is not wired into any pipeline. CI
  still enforces the invariant independently (`test_the_pinned_commit_carries_
  the_pinned_identity` in the tests job), so a wrong re-pin is still caught
  before it ships — but the operation itself is run by hand, and nothing
  forces a maintainer to use it instead of editing the four literals.

  Also not covered: the guard proves the pin is reachable from HEAD, which is
  the right question for an operator who then pushes that branch. It does not
  prove the pin survives a rebase, a squash, or a force-push performed after
  the operation returns — nothing local can, and CI's own chain guard is what
  catches that.

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
