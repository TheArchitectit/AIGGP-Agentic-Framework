# Design: runner-owned evaluator-image cycling

## D1 — The desired state is the record, not the tag

The registry (`container/execution-profiles.json`) names the bytes a consumer
fetches: `image` plus `image_manifest_digest`. The gate resolves the profile,
validates the launch config's digest against it (`hub/coherence/profiles.py`,
`check_launch_digest`), and then launches the digest-qualified ref — the tag
is not in the executed path at all. So any cycle that follows `:main` is
chasing something the gate never reads. Converging on the record is both
simpler and the only direction that keeps the doctor's meaning: "the bytes
this host will execute are the bytes the registry pins."

Corollary: a host that is *ahead* of the record (has a newer `:main` build) is
not converged either. Presence is checked on the digest-qualified ref,
never by name.

## D2 — Two digests, and why the cycle must speak manifest

Measured 2026-09-23: `podman image inspect --format '{{.Digest}}'` of a
locally BUILT image yields a value no registry serves; pushing re-encodes the
manifest. The pullable identity is the registry's manifest digest, and only a
pull can establish it. Recording the build-time config digest is precisely how
the S4 pin once shipped unpullable while CI was green. The cycle therefore
operates exclusively on `image@image_manifest_digest` and never on a local
build's `.Digest` — the same rule the CI identity gate now follows.

## D3 — The storage the cycle fills must be the storage the job reads

`templates/runner/self-hosted-runner.container` runs the official
`actions-runner` image and mounts one volume: `/_work`. There is no podman
socket bind and no container-storage mount, so the job's podman is not
automatically the host's podman, and an image pulled on the host is not
automatically visible to the job.

This is the failure mode this design must make impossible: a cycle that
succeeds into one store while the gate SKIPs against another reports health
for a host that cannot run the evaluator. Two shapes are admissible, and the
choice is per-fleet, not per-repo:

- **(a) podman inside the runner container.** The runner image gets podman,
  and a named volume backs `~/.local/share/containers`. The job, the cycle,
  and the image all live in that store.
- **(b) socket-shared host storage.** The host's rootless podman socket (and
  its storage) is bound into the runner container, and the cycle runs against
  the host store the job then reaches through the same socket.

Whichever shape a fleet picks, the cycle's own verification MUST resolve the
ref the way the job resolves it — inside the same namespace, digest-qualified
— and MUST fail (non-zero, with the mismatch named) when it cannot. "The
cycler is green and the doctor is SKIPPED" is a defect, not a state.

### D3.1 — The store is a required input, verified by asking podman

An implementation cannot discover which store the job will read: from inside a
tick, shape (a) and shape (b) are indistinguishable, and a script that assumes
the ambient store is right produces exactly the green-and-SKIPPED state above.
So `scripts/runner-image-cycle.sh` requires `COHERENCE_PODMAN_STORE`, addresses
every podman call with `podman --root "$COHERENCE_PODMAN_STORE"`, and then
verifies the assumption instead of trusting it: `podman --root <path> info
--format '{{.Store.GraphRoot}}'` is asked to confirm the graph root it actually
resolved. A mismatch exits 5 and names both paths; nothing is pulled until that
check passes.

**Corrected 2026-09-24 (audit, measured on podman 6.1.1).** This section first
claimed podman "answers with the path given, so a different answer means the
configuration does not address the store it names". The measurement was right
and the inference was wrong: podman answers with the path NORMALISED, not
verbatim — `--root /tmp/ps1/` answers `/tmp/ps1`, and `--root /tmp//ps1`
answers `/tmp/ps1` too. A byte comparison of the two strings therefore does not
compare two stores: a trailing slash, an ordinary EnvironmentFile typo, makes a
correctly configured host report a mismatch. The check is on the DIRECTORY each
name denotes (`cd` + `pwd -P`, builtins) rather than on the spelling. The
heartbeat probe carries that correction here — where the defect was worse than
a refusal, because its mismatch branch skips the presence check and so hid a
converged host from the fleet view entirely.

The cycler carried the same byte comparison and the same `|| true`. Its
correction was owed with its own tests rather than smuggled into this change,
and that is now paid (2026-09-25). Three things moved, and each is a separate
promise rather than a tidier spelling of one:

- The same canonical comparison, and a podman that cannot answer gets its own
  exit code and its own words instead of arriving as a "mismatch" no
  EnvironmentFile edit can fix.
- The store is checked for EXISTENCE before podman is asked anything, and the
  cycle REFUSES to create it. `podman --root X info` materialises X (measured),
  so on a host whose mount has not come up the old order created an empty store
  on the underlying filesystem and pulled the pinned image into it — filling
  storage the gate never reads, while the mounted filesystem stayed empty.
- The pinned image is re-verified AFTER the reap. `podman rmi <id>` takes every
  row that ID carries, and the reap set is computed from a listing whose
  `.Digest` is not a reliable identifier of the bytes: measured 2026-09-24, the
  listing's digest and `inspect`'s digest are different values for one image
  (`sha256:294b683c…` vs `sha256:d56c381f…`). So a listing can report a digest
  other than the recorded one for the image that IS the recorded bytes, putting
  the pinned ID in the reap set. The check turns that invariant from reasoning
  into an observation — and the mutation battery can now produce the loss, so
  "the pinned image survived" is not a claim about a store where nothing is
  ever removed.

Also corrected there from measurement, because it was offered as a reason: the
comment claimed a locally built image "lists with a tag and no digest". It
lists WITH a digest (`sha256:df67b148…` for a `FROM scratch` build). The Tag is
the whole of the discrimination, and the digest comparison is doing none of
that work — a reader who believed otherwise would think a tagged build was
excluded twice over.

What the tick can then claim is narrow and true: *the recorded bytes are in the
store named by this unit's EnvironmentFile*. Which store the runner container
actually mounts stays a property of the unit file and its documentation — the
honest division, because that is the only place the mount is declared and the
only place a mismatch is fixable.

**Paid 2026-09-25 (Sprint 2.2).** Enrollment now installs the cycle
(`scripts/runner-enroll.sh`), and `templates/runner/README.md` documents the
namespace question in the one place it can be answered: both admissible shapes
in full, and the invariant that the cycle's store must be the job's store. Two
things about how it installs are design decisions rather than packaging, and
each is mutation-pinned (E1–E2, E7 in `tests/mutation_battery_image_state.py`):

- **It is installed by enrollment and ENABLED by provisioning.** The three
  `COHERENCE_*` variables are a per-fleet choice the script does not own, so an
  unprovisioned host gets the units on disk and no running timer. Starting one
  anyway would exit 1 here and 5/6/7 on a shape-(a) fleet that never sets them
  on the host at all; a unit failing every cycle is noise, and noise is how the
  alert that matters gets ignored.
- **The documented store value is obtained, not guessed.** The doc gives
  `podman info --format '{{.Store.GraphRoot}}'` — the same question the cycler
  asks the same binary — and records the measurement that makes the distinction
  matter: on rootless podman 6.1.1 the graph root is
  `~/.local/share/containers/storage`, and `/run/user/<uid>/containers` is the
  RUN root. Handing the run root to `--root` would make podman create a second,
  empty store — the exact failure this section exists to prevent, arrived at by
  following a plausible-looking path.

Residual limitation, stated rather than hidden: if an operator configures
`COHERENCE_PODMAN_STORE` to a store the job cannot read, both the tick and the
gate are internally consistent and still disagree with each other. The store
value is therefore a documented, single-source setting in the unit's
EnvironmentFile, and the heartbeat's image fields (Sprint 3) are what make the
disagreement visible from the fleet view rather than from a hunch.

## D4 — Why authority stays out of the runner

Auto-advancing the pin from a host requires: repo write credentials on every
fleet host; trust that whatever the last push published is the evaluator we
intend to execute; and a pin commit whose tree carries the moved record (the
template reads the registry out of the pinned tree, so the digest literals and
`DEVGATE_PIN` must move in the same commit). Consequences: a compromised host
becomes a compromised identity chain, and CI run output becomes executable
bytes by default.

The alternative chosen here keeps the useful half: hosts converge automatically
on a decision made elsewhere, and the decision itself is one explicit
operation with a fail-closed check. This mirrors the framework's existing
posture — the record is the identity (coh-id-04), a launch whose ref disagrees
with the record is refused, and a gate that cannot evaluate reports
non-green.

## D5 — Reporting rides the heartbeat, not a new channel

`runner-heartbeat.sh` already samples host facts (`disk_ok`, `podman_ok`) and
POSTs them; `hub/registry.py` already stores them per runner. Image state is
the same kind of fact, so it joins the same payload rather than inventing a
second reporting path: `image_digest` (the digest-qualified ref present, or
null) and `image_reason` (why not, when absent). The hub schema's nullable
fields already model "not reported"; the dashboard must render null as
unknown, never as healthy — the same rule that makes `podman_ok: none`
distinguishable from `podman_ok: true`.

## D6 — Divergence is advisory, and CI's publish trigger becomes honest

Served-tag-vs-record divergence is a fact about the repository, not a fault on
any host, so the cycle reports it as an advisory (`mon-alert-01`) rather than
failing a host's tick. Failing a host for the repo's publish policy would
train operators to ignore the alert.

Independently, `container-publish`'s condition and its comment must agree. As
written, the comment promises manual dispatch and the `if:` fires only on
push: the gate's stated trigger is false documentation, which is its own
defect regardless of which policy is chosen.

## D7 — The re-pin operation is mechanical or it is not done

Four literals move together: the registry's `image_manifest_digest`, the
template's `COHERENCE_IMAGE_MANIFEST_DIGEST`, and the `DEVGATE_PIN` whose tree
carries the registry, with `COHERENCE_IMAGE` agreeing on the name. Round-18
proved the failure mode of moving them by hand: a pin that predates the record
fails closed at the digest step, and a digest without the pin ships a record
the pinned tree does not carry. The operation is therefore a single command
that performs all four edits and then re-runs the chain guard
(`test_the_pinned_commit_carries_the_pinned_identity`) rather than a documented
ritual.
