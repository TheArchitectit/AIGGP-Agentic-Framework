# Design: Fleet Manager adapter contract

## The contract is a shape, and the shape is checkable without running anything

Sec. 5.2 names eleven calls. Three of them carry a policy decision inside their
signature, and three carry an identity:

| call | the parameter that carries the rule |
| --- | --- |
| `ensure_image(digest, ...)` | a digest, never a tag — the immutable artifact |
| `create_runner(registration_ref, ...)` | a reference, never the registration material |
| `cancel_or_timeout(policy, ...)` | cancellation happens only under an explicit policy |
| `prove_cleanup(instance_id, ...)` | cleanup is proved about one instance, not about a host |
| every mutating call | `operation_key` — idempotent or durably keyed (Sec. 5.2) |

`check_contract()` inspects the candidate with `inspect.signature` and refuses
before anything is called. Two consequences worth naming:

1. **A fake that raises on every call still conforms**, and the suite proves it.
   Conformance is about the shape an implementation promises, which is exactly
   the part that cannot be discovered by calling it in a test with a happy path.
2. **`**kwargs` does not satisfy a named parameter.** An adapter that swallows
   everything accepts a call it does not implement; the checker requires the
   name.

The check reports *every* missing member in one refusal rather than the first,
because a fresh adapter is usually missing several and a one-at-a-time loop
turns one review into six.

## Runtime is declared, not inferred

An adapter serves exactly one `Runtime` (docker or podman). The checker takes
the runtime from the pool and refuses a mismatch by name. This is the "runtime
differences SHALL be isolated inside adapters" rule given a place to fail: a
podman adapter handed a docker pool is a wiring error, not a runtime surprise.

## Errors are typed and closed

Sec. 5.2 fixes eight kinds. `ErrorKind` holds exactly those, `AdapterError`
carries one, and a string that happens to equal a value is refused — the enum is
the type, and "runtime_failure" is a string that found its way into a place
where a decision was expected. `classify()` wraps an unexpected exception as
`RUNTIME_FAILURE` naming **the exception's type only**: an arbitrary exception's
message is exactly where a credential ends up (a failed `podman login` echoes
what it was given), so it is dropped rather than recorded. A `detail` that
matches the credential shape inherited from `audit` is refused **without being
echoed**, the same rule as receipts and audit reasons.

## The image pin has one source, and a test holds it to the standard

`templates/runner/README.md` sets the fleet's image decision: the official
`ghcr.io/actions/actions-runner`, pinned by digest once validated, and
`self-hosted-runner.container` records the validated digest. The module carries
that digest as `STANDARD_RUNNER_IMAGE_DIGEST` and a test parses the quadlet's
`Image=` line and fails if the two differ, so the package cannot pin an image
the fleet standard does not use. The test is skip-guarded because the extraction
rehearsal copies only `fleet-manager/` — a missing template is a skip, a changed
one is a failure (the same guard as 3.2's runner-enroll check).

A reference with a tag is refused. `ghcr.io/actions/actions-runner:2.337.0` is a
mutable name for an immutable artifact, and the whole point of the pin is that
what ran today is what runs again.

## Warm is a state of the instance, not a count on the host

Sec. 5.3 permits a warm pool to keep "pre-pulled images or stopped clean
containers" and forbids keeping "a previously used job filesystem". So warmth is
a property the pool can check: an instance is warm iff its state is
`PREPULLED` or `STOPPED_CLEAN`. `USED` is a state, not an absence, because a
used instance still exists and still occupies a name — treating it as "not warm"
by omission is how it ends up reused.

`WarmPool` binds every instance to the pool's own `image_digest` and
`pool_id`, so a warm container from a previous image generation cannot be
counted against the new one; the digest is what makes "the same image" mean
something. Warm stock above `warm_max` is refused as well as below — a pool that
is over its own ceiling is as much a defect as one under its floor, and it is
the more expensive one.

## The ephemeral instance is defined by what it does not have

The standard's persistent runner uses a durable `/_work` volume so a restart
reuses the registration. An ephemeral job instance must have the opposite
property: an anonymous work directory, removed with the container. The spec
value therefore carries `work_dir=None` meaning anonymous, `remove_on_exit=True`,
and **no volume mount at all**; a test asserts the rendered command has no
`/_work` and no `-v`.

The registration reference goes in an environment *file* named by `--env-file`,
never as `-e RUNNER_TOKEN=<value>` in the argument list: the runner standard's
own walkthrough is careful to keep the token out of argv and shell history, and
a value that a process can see in `ps` is not protected. A test asserts no
`RUNNER_TOKEN=` appears in the rendered command and that the env-file path is
the only place the reference is named.

## What is left to 4.2, on purpose

No conformance fixture for a real adapter, no lifecycle, no cleanup proof, no
quarantine, no resource limits, and no `destroy_runner` implementation. This
change supplies the surface they implement and the values they build on.
