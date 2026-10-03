# Proposal: Runner-owned evaluator-image cycling

## Problem

Two facts about the pinned evaluator image are unreconciled, and each one
hides the other.

**Nothing puts the image where the gate runs.** `templates/github-workflows/
spec-coherence.yml` states the requirement plainly — "The runner must have
podman and the pinned image already present" — and then relies on it: the
doctor reports `unavailable` and the container phase SKIPs when the
digest-qualified ref is absent, and the gate never pulls by design (coh-rt-01,
because a gate-time pull would make the executed bytes depend on the network
rather than on the registry pin). But no mechanism in this repository, the
runner templates, or the enrollment path ever puts those bytes on a host.
The coherence image is not mentioned in `templates/runner/*`, not in
`scripts/runner-enroll.sh`, and not in `hub/`. Measured 2026-09-24 from the
runner container definition: `self-hosted-runner.container` mounts exactly one
volume, `/_work` — no podman socket, no container-storage mount — so even a
host that *did* have the image would not necessarily expose it to the job,
whose podman is whatever runs inside the runner container. There is no
recorded host holding the image, and no provisioning step to record.
A missing image therefore presents as a SKIPPED phase on a host that believes
it is healthy.

**The published tag moves and nothing notices.** `container-publish` builds
and pushes a fresh manifest on every push to main, so the `:main` tag
advances past the recorded identity continuously. Measured on two consecutive
hosted runs: served `sha256:61170a5c2ee56ce23a485709f5110a044bdcf27b97113d3f3108e97bacbf7445`
against recorded `sha256:f470110ce0caa14bb78eabc633c1bbbf63aeb9f49b15e50cd5866788964f2c6c` —
stable across both, so not a race but a standing divergence. The job's own
comment claims it publishes "ONLY on main pushes and manual dispatch with
publish=true" while its `if:` is `github.event_name == 'push' && github.ref ==
'refs/heads/main'` — manual dispatch never publishes. The divergence is
reported as a `::notice::` in a job log nobody reads, and nothing fails.

## Solution

Move image freshness onto the runners, as a timer beside the heartbeat, and
split it so that only convergence is automatic.

1. **Converge (automatic).** A `devgate-image-cycle` unit, installed by
   `runner-enroll.sh` the same way `devgate-heartbeat.sh` is, ticks on the
   host's drift period and ensures `image@<recorded manifest digest>` is
   present in the container storage the *gated job's* podman reads. It pulls
   by digest only — never a tag — and is idempotent: an image already present
   at the pinned digest is not re-pulled. This is coh-rt-01-clean, because
   the pull happens on the timer and never at gate time.

2. **Report (automatic).** The heartbeat carries the host's evaluator-image
   state (present at the pinned digest, or explicitly absent with a reason),
   so a host that cannot serve the pinned image is visible on the fleet
   dashboard instead of presenting as a healthy runner whose gate quietly
   SKIPs. An omitted field is unknown, never present.

3. **Advance (deliberate).** The record is the desired state; the published
   tag is not. Moving the pin becomes one operation that updates the registry
   digest, the template's `COHERENCE_IMAGE` / `COHERENCE_IMAGE_MANIFEST_DIGEST`
   / `DEVGATE_PIN` literals together, and fails closed unless the new pin's
   tree carries the moved record — which is already the shape the chain guard
   enforces. It is never a side effect of a push, and fleet hosts hold no
   authority to perform it.

4. **Detect (automatic, advisory).** The tick compares the registry's
   currently served `:main` manifest digest with the recorded one and reports
   divergence to the hub as an advisory. CI's share shrinks to publishing on
   a deliberate trigger, with the job's stated trigger matching its condition.

## Why not "let the runners auto-advance the pin"

The runner owners' suggestion was to build the cycle into the runners. It is
the right home for *convergence* and the wrong home for *authority*. If a
runner could advance the pinned identity to whatever the last push published,
then the executed evaluator bytes would be chosen by an unreviewed build —
the implicit-trust-from-upstream failure this framework exists to refuse —
and every fleet host would need write credentials on the framework repository,
converting a compromise of any host into a compromise of the identity chain.
Runners cycle; the pin moves by decision.

## Affected specs

- New capability `runner-image-cycling`: `img-cycle-01` … `img-cycle-06`
- Cites `coh-rt-01` (digest-pinned invocation, no gate-time pull),
  `coh-id-04` (identity registry), `mon-registry-01` / `mon-online-01`
  (heartbeat-carried runner state), `mon-alert-01` (alerting),
  `mon-enroll-01` (the unit-installation path this rides on),
  `mon-drift-01` (the periodic tick this shares a cadence with)

## Out of scope

- AIGGP packages (not started; nothing here may wire to `aiggp-*` IDs).
- The arm64 profile — still blocked on an arm64 runner to verify the claim.
- Host-side housekeeping in the separate docs-only infra repository.
