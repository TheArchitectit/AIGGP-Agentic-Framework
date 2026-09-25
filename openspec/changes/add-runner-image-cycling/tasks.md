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

- [x] 3.1 Extend the heartbeat payload with `image_digest` / `image_reason`
  (`scripts/runner-heartbeat.sh`), accepting the fields in the hub
  (`hub/registry.py`, `hub/schema/runners.schema.json`) with nullable
  defaults, rendered as unknown rather than healthy. The probe is REPORTING
  ONLY: every fault becomes an absence with a reason and the tick still exits
  0, because a heartbeat that dies blinds the whole fleet — strictly worse
  than an image field that reads unknown. Reasons are the cycle's own
  vocabulary (not provisioned, podman not on PATH, store mismatch, absent)
  because each names a different fix. Two design notes worth keeping:
  - **The store is verified before the image is.** The probe asks
    `podman --root "$STORE" info --format '{{.Store.GraphRoot}}'` and compares
    it to `COHERENCE_PODMAN_STORE` before asking whether the ref is present;
    a host pointed at the wrong store would otherwise answer "present" about
    a store its own gate never reads. This is D3.1's failure mode, from the
    fleet view rather than from the tick.
  - **`registry.UNREPORTED` exists so that `null` can mean something.** Every
    other field in the registry treats `None` as "no news": omitting `disk_ok`
    leaves the last reading. Correct for a health boolean, wrong for the
    image, which needs three states — a host that converged yesterday and lost
    its image today reports an explicit JSON null, and if null were also "no
    news" the hub would keep the superseded ref and the fleet view would show
    that host as ready to gate. JSON has one null, so the distinction has to
    be made from the PRESENCE of the key on the way in; without the sentinel
    the two cases are indistinguishable and the safe-looking default is the
    harmful one. Both directions are pinned by named tests (a null clears; an
    omission leaves alone), which is what keeps the sentinel from being
    decoration.
- [x] 3.2 Fleet view: a host with no pinned image shows the deficiency and
  reason (mon-registry-01, mon-online-01) — `MonitorLoop._check_image_readiness`,
  check-class `runner_image_missing`, detail carrying the host's own reason.
  There is no dashboard renderer in this repository, so the fleet view IS the
  alert path; the check is deliberately separate from `_check_runner_status`
  rather than folded into it, because that function returns early when the
  runners API call fails and a rate limit would then silence an image
  deficiency exactly when an operator is looking. `registry.image_missing()`
  keys readiness on the digest alone and never on a reason being present: a
  host whose image state was never reported is as unable to gate as one that
  reported a fault, and requiring a reason would quietly count the entire
  already-enrolled fleet as ready.
- [x] 3.3 Tests for the null-vs-true distinction and for the schema's
  acceptance of the new fields. The schema test is a DRIFT invariant, not
  validation, because nothing in this repository validates a registry against
  `hub/schema/runners.schema.json` — `jsonschema` is not installed and CI
  installs only pytest, so a field the registry writes and the schema does not
  declare is invisible until a human reads both files side by side (which is
  how the two new fields would have shipped undeclared). The invariant also
  checks the redacted example, and that check found a pre-existing defect
  immediately: the example carried a top-level `_comment` while the schema set
  `additionalProperties: false` and declared no such key, so **the example
  violated its own schema**. An example that does that teaches the wrong shape
  to whoever copies it, so `_comment` is now declared in both the root and the
  runner shape.
  Also pinned: a registry file written BEFORE this change (no image keys at
  all) loads without raising and reads as NOT ready — the state monitor-hub's
  volume is actually in.

### Sprint 3, audited 2026-09-24 — and the audit was worth more than the first draft

A fresh-eyes pass over the diff found twelve things, three of them real defects
in this change and one of them a defect in how I had reported the work. Fixed
here; the rest are recorded with a disposition rather than absorbed.

1. **The store check compared spellings, not stores (fixed).** `podman --root
   /tmp/ps1/ info` answers `/tmp/ps1` — podman NORMALISES the path it reports
   (measured on podman 6.1.1, both trailing and doubled slashes). Comparing the
   two strings byte-for-byte therefore made an ordinary EnvironmentFile typo
   read as a store mismatch — and the mismatch branch SKIPS the presence check,
   so a correctly provisioned host was reported as unable to gate for as long
   as nobody edited a path that was already right. The comparison is now on the
   directory each name denotes (`cd` + `pwd -P` — builtins, so a bare runner
   host gains no new dependency). The old test could not catch this: the podman
   stub echoed its argument verbatim, encoding the same false premise. The stub
   now normalises the way podman does, which is what turns the audit's
   measurement into a reproducible test.
2. **A failing podman was reported as a mismatch (fixed).** `graph_root="$( …
   || true)"` collapsed "podman could not answer" into an empty string, which
   never equals the configured store — so a broken store, a permission problem,
   or a podman that will not start all sent the operator to edit a path. It has
   its own reason now.
3. **The probe CREATED the store (fixed).** `podman --root X info` materialises
   X when it is missing (measured: one run left `X/{db.sql,libpod}`). On a host
   whose store mount has not come up that is worse than a wrong answer: an
   empty store is left on the underlying filesystem, outliving the mount. The
   store is now checked for existence before podman is asked anything, and the
   test asserts the directory is still absent — an assertion the stub's own
   side effect keeps honest (both are mutated in the battery).
4. **The suite was coupled to the ambient environment (fixed).** `Spoke` built
   its env from `os.environ`, so a host that IS provisioned decided which probe
   branch the not-provisioned test exercised — red on a provisioned host, and in
   CI a silent choice of the branch under test. This is this repository's
   recurring defect class (third instance: the podman-absence test's symlink
   farm, the stale bytecode, now this). The three `COHERENCE_*` variables are
   scrubbed at the fixture, not per test, so no later test can reintroduce the
   coupling by forgetting.
5. **Prose that contradicted the code (fixed).** The `UNREPORTED` note said
   "`None` still means no-news for a caller that passes it directly" — false for
   the image fields, where passing `None` IS the report that there is no image
   and therefore CLEARS a stored ref. An implementer trusting that sentence
   wipes a converged host's digest. `image_missing`'s docstring likewise claimed
   more than it computes: it does not check the digest is still the PINNED one,
   so a host that has not ticked since a re-pin reads as ready. The claim is
   corrected and the residual named; catching it needs the current pin in hand
   and belongs to Sprint 4's served-vs-recorded advisory, not to this predicate.
6. **My mutation report was wrong (corrected).** I reported "19/19 killed" from
   a battery in /tmp — reproducible by nobody, and never run against the
   repository's own tool, which refuses a dirty tree. Run against a clean copy
   of this tree, `scripts/mutation_check.py` reports survivors on all three
   touched Python files, and five of the registry's were caused by MY code: the
   `UNREPORTED` note was a bare string literal, not a docstring, so the tool
   mutated prose as if it were logic (`bool:and->or`) and reported blind spots
   that can never be killed — exactly the noise that trains an operator to
   ignore the report. The note is now `#` comments. The battery itself is
   committed (`tests/mutation_battery_image_state.py`) so "no survivors" is
   re-checkable: **25/25 killed, each by one named test**, plus one negative
   control that must and does survive (see below).

Dispositions for what was NOT changed here, so nothing is silently absorbed:

- **The provisioning path does not exist yet.** Nothing writes `COHERENCE_*`
  into a host's EnvironmentFile, `runner-enroll.sh` truncates that file on
  re-enroll (destroying an operator's hand-added lines), and it leaves an
  already-installed helper unchanged — so today every enrolled host reports
  "not provisioned" and the hub files one alert per host. That is Sprint 2.2's
  job and the order is not cosmetic: 2.2 is what makes those alerts clearable.
- **No timeout on the podman calls.** The tick blocks until podman answers; a
  contended store lock (the cycle pulling while a tick fires — which 2.2 makes
  routine) delays it, and the unit's 90s start timeout would kill the POST.
  Queued: bounding the calls needs a PATH dependency handled explicitly, and
  the pre-existing `podman info` above has the same exposure.
- **The cycler retains the same byte comparison and the same `|| true`**
  (`runner-image-cycle.sh`): it fails closed rather than hiding a host, and its
  correction is owed with its own tests (see design.md D3.1).
- **A reported digest that is stale after a re-pin** reads as ready; documented
  as a residual in `image_missing`, owned by Sprint 4.
- **`/health` renders no image state at all**, so "fleet view" is realised only
  through the alert path; noted rather than papered over.

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
  each guard killable by a named test — now 17, see the CI-found defect below

  FOUND BY CI 2026-09-24 (run 36061428590, commit `43d5ead`), and it is the
  whole argument for the hosted lane: the suite was green locally and RED
  there. Three tests failed — `test_a_successful_re_pin_…`,
  `test_the_operation_takes_its_digest_from_the_registry`,
  `test_the_post_write_guard_catches_…` — every one of them with

      fatal: empty ident name (for <runner@…>) not allowed
      re-pin: the commit failed (a hook, a git identity, or an index lock)…

  The suite commits: the fixtures do, and the operation under test does. The
  identity reached fixture commits (`_git()` supplied it through the
  environment) but not the OPERATION's commits — `_env()`, which builds the
  environment the script runs in, supplied none, so the operation's `git
  commit` fell back to whatever config the machine had. A developer machine
  has a `~/.gitconfig`; the runner does not. The tests were therefore green
  for a reason they did not assert, which is the same defect class as the two
  vacuous assertions the first audit found, one layer further out: the suite
  was coupled to ambient state rather than to the code.

  Fixed in `bcb2d0c`. One shared identity, used by both, and deliberately the
  ENVIRONMENT's rather than config's — the fixtures read no config
  (`GIT_CONFIG_GLOBAL=/dev/null`), so a config-file `user.name` would not
  reach the operation either. The battery itself now runs with HOME and
  XDG_CONFIG_HOME pointed at empty dirs, so it cannot pass for a reason the
  runner will not reproduce. Verified hermetically: 843 passed / 3 skipped.

  The red run left one useful thing behind. It exercised the exit-6 rollback
  — audit fix 4, above — in a real environment, and NOTHING pinned it: no
  test in the suite named exit 6, so the rollback could have been deleted
  unnoticed. A failing `pre-commit` hook now induces that path
  deterministically and asserts both halves of the promise: exit 6, HEAD
  still at `ORIG`, a clean `git status`, the record still carrying its old
  digest, and the diagnostic that claims the rollback ("nothing was left
  applied"). Both halves are asserted because a rollback removed while the
  message survives is a message that lies — M17 mutates the message alone.
  Induced by hook rather than by a missing identity on purpose: now that an
  identity is supplied, a test depending on its ABSENCE would be the same
  ambient coupling in reverse.

  What this does NOT establish, and should not be read as: that the exit-6
  path is covered in every way it can be reached. The hook fails the FIRST
  commit; the second commit's failure branch is the same code with `$ORIG`
  reached the same way, but it is not separately executed.

  SECOND CI FINDING 2026-09-24 (run 36062353190, commit `098387b`), and this
  one was self-inflicted: the tests job went GREEN and the gates job went RED,
  because the re-pin suite had grown to 648 lines against a 600-line hard
  limit. Adding the exit-6 test is what pushed it over. The local mirror had
  been run for pytest, guardrails, exec bits, floors, openspec and
  `git diff --check` — the regression check was the one step skipped, and it
  was the step that would have caught this. Fixed in `08554a4` by moving the
  HARNESS — the throwaway git repository and the bin/ of stubs — out to
  `tests/fixtures/repin.py`, where ten other suites already keep theirs. The
  suite is 504 lines; no test logic changed. The file-size report is the thing
  to read here, not the exit code (a separate lesson this repository already
  paid for once).

  That move then reproduced the repository's own root-anchor defect class in
  miniature, which is worth recording because it is the second time this
  month a root resolved one directory off silently: `REPO =
  Path(__file__).resolve().parent.parent` was the checkout root from
  `tests/` and `tests/` itself from `tests/fixtures/`, so all 21 tests failed
  with `bash: …: No such file or directory`. The anchor now refuses to import
  when the path it resolved does not carry the script, and that refusal was
  verified by re-creating the move — the same rule `scripts/lib/project_root.py`
  states for the scanners (root-anchor-01).

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
