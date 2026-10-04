# runner-toolchain-requests — Design

> Revised after external architecture review (v2) and Mission Control fit
> review, 2026-10-03 CDT. Findings F1–F11 and M1–M6 are addressed below; the
> six questions the review left open are answered in §Decisions taken.

## Context

A fleet runner that lacks a toolchain cannot ask for one. This design adds the
request channel, the decision surface, and the fulfillment path.

Measured 2026-10-04 02:40–02:55 UTC (read-only, via `podman run` against the
images the fleet's own quadlets reference). Evidence is held in private
operational documentation; lane names, host aliases, image sizes and host
posture are deliberately not reproduced in this public repository — see F7.

- The stock runner image carries `git`, `python3`, `jq`, `bash` and no
  toolchain beyond those. Five lanes run on it.
- Lanes with a toolchain carry it baked into the image.
- The consequence is a per-job tax: stock lanes fetch a toolchain in every job,
  so the knowledge lives in workflow YAML and drifts from the image.

## Findings this revision corrects

**F1 — evaluator image fields are not lane images.** The previous draft claimed
fulfillment's digest "SHALL be the value the lane reports in its existing
`image_digest` field". Verified against `hub/schema/runners.schema.json:50`,
that field is the **coherence evaluator** ref, assembled from
`COHERENCE_IMAGE` plus `COHERENCE_IMAGE_MANIFEST_DIGEST`. It does not describe
a runner lane image, and img-cycle-05 compares the *evaluator* tag's served
digest. Overloading it would have been a silent join to nothing, and
`hub/registry.py` clears the field when a heartbeat sends an explicit null, so
evidence held there can vanish. Lane image identity now lives in separate
fields and the spec states the two are unrelated.

> Correction to the review: F1 states the hub "clears a stored `image_digest`
> when a heartbeat omits it". It does not. `heartbeat()` defaults the field to
> `UNREPORTED` and assigns only when it is not `UNREPORTED`
> (`hub/registry.py:309`), so omitting leaves the stored value alone and an
> explicit `null` clears it. The conclusion is unchanged; the regression test
> must assert the real behaviour.

**F3 / M2 — there are two runner registries.** Mission Control maintains its own
Postgres runner registry (enroll, heartbeat, fleet reads) alongside the hub's
`runners.json`. The previous draft asserted Mission Control "holds no fleet
state", which was true of the hub client and false of the registry.

**M3 — the previous draft read the wrong Mission Control.** Its file paths came
from the standalone `TheArchitectit/mission-control-rs` repository, last pushed
2026-09-15. The live tree is the `mission-control-rs/` directory inside
`TheArchitectit/missioncontrol`, last pushed 2026-10-03. Verified in that tree:
`askama` + `askama_axum` + `axum` (not Inertia), `src/api/runners/` and
`src/api/fleet/` present, no `src/api/dashboard.rs`.

**F4 — the detector compared against the vocabulary.** That is a permanent gap
on every stock lane, because the vocabulary is the union of what *some* lane
needs. The gap is now *required profile minus observed*, which is empty on a
provisioned lane.

## Decisions taken

Answers to the six questions the review left open.

### Q1 — Registry ownership and lane mapping

The hub owns toolchain **requests**. Mission Control owns its runner registry
and keeps it; the two are not merged.

`runner_name` in the hub is the canonical lane identifier. Each Mission
Control runner record carries an explicit `hub_runner_name` link. The queue
joins on that link only, and a request whose lane has no link renders as
`unmapped` rather than being dropped or joined to a same-named record.

Rejected: making Mission Control the system of record (a second writer for
state the hub already owns), and a merged registry (two deployments, one
migration, no incremental value).

### Q2 — Operator identity depth

For v1: one operator, an actor claim, and honesty about it.

Mission Control authenticates the human through its existing session and CSRF
guard plus an administrative-tier check, then calls the hub with a dedicated
service credential carrying scope `toolchain:decide` and a signed actor claim
(principal, timestamp, nonce). The hub stores the claim and the credential
identifier, refuses replay, and refuses every other credential class it knows.

The hub records the actor claim as presented. It does not assert the claim
identifies a distinct human, and `mon-tc-03` requires that a single-principal
configuration be visible as such in the audit record. Per-operator accounts are
a prerequisite for multi-operator operation, not for v1 — there is one human
today — but the spec must not imply attribution it cannot deliver.

Rejected: letting the decide action ride on an ordinary Mission Control API
key (write scope, shared secret, no actor), and inventing an operator identity
in the hub before Mission Control has one to forward.

### Q3 — Who builds, and what triggers it

A build job, not Mission Control.

Mission Control records the approval. A CI job — triggered by the approval and
holding a **builder credential**, distinct from both the operator credential
and runner credentials — builds the lane image with the toolchain profile
added, then reports back with profile id, build id and digest. The hub moves
the request `approved → built`, and a later heartbeat carrying that digest with
a passing probe moves it `built → fulfilled`.

Rejected: Mission Control triggering builds (puts an operator-facing service in
the build path for no gain), and the hub executing a build (the hub must never
run a package manager — `mon-tc-05`).

### Q4 — Row identity

Per `(lane, tool)`.

Approving one tool of three has to be expressible, and a bundle row cannot
represent a partial approval. A **toolchain profile** groups tools for
provisioning; the **request** stays per tool so partial progress is visible.

Rejected: one row per bundle (partial approval becomes a lie) and one row per
lane (the common case of two tools from two different profiles collides).

### Q5 — Queue UI surface

An Askama + HTMX page in the page-gated tier.

It matches what the live tree actually ships, escapes by default, and needs no
cookie-session bridge. Mission Control's own `frontend-architecture` spec still
says the React SPA "SHALL be removed" while a later decision admits React
islands on six routes; reconciling that stale spec text is part of the Mission
Control companion change, not something this change should silently pick a side
on.

Rejected: a React island tab (requires the bridge the decision describes, for a
queue that is a list and two buttons).

### Q6 — Ownership of observed lane-image evidence

The hub.

Mission Control's `fleet-runner-dashboard` spec forbids full image digests in
the podman snapshot payload. Since the fulfillment chain is digest-based, the
evidence comes from the hub's `lane_image_digest`, reported by the spoke from
the running container. No Mission Control spec change is required.

Rejected: widening the snapshot allow-list (changes a security decision in
another spec to serve this one).

## Architecture

### Detection

    gap = required_profile(lane)  MINUS  observed(runner image)

`required_profile` is a reviewed per-lane assignment, trusted, not
runner-supplied. `observed` is probed inside the runner image — never the host
`PATH`. Each probe returns `present`, `absent`, or `unknown`; a probe that
exceeds its bound is `unknown`, and `unknown` is never collapsed into `absent`
or into `present`.

Probes are fixed: `python` is `python3` present; `pip` is `python3 -m pip`
succeeding; `maven` and `java` require a working JDK; `g++` is probed
separately from `gcc`.

### State machine

Row identity `(lane, tool)`, states `open` → `approved` → `built` →
`fulfilled`, with `denied` terminal-until-suppressed. The normative transition
table is in `mon-tc-04`; `design.md` does not restate it, so there is one
source of truth.

Concurrency: every row carries a version counter. Transitions are
compare-and-swap under the registry lock, so of two simultaneous decisions
exactly one wins and the loser receives `409 Conflict`. Re-submitting an
identical decision at the version it already produced returns that outcome
rather than applying twice — idempotency without opening a replay hole, which
is why nonce freshness is enforced separately on the credential.

History is append-only; the current state is a projection of it.

### Coverage state

The previous draft collided: one requirement said a no-gap heartbeat must be
indistinguishable from a pre-capability heartbeat, another said a provisioned
lane must be distinguishable from one that never reported.

Resolved by a separate per-lane **report-coverage state** — `reported`,
`never-reported`, `stale`, `probe-failed` — with numeric staleness and
fulfillment windows defined by the spec. Coverage is orthogonal to request
state, so both requirements can hold at once.

### Credentials

| Credential | Holder | May |
|---|---|---|
| enrollment / heartbeat | runner spoke | enroll, heartbeat |
| runner key | runner spoke | request a gap |
| `toolchain:decide` + actor claim | Mission Control service | decide |
| builder credential | build job | report build evidence |

The hub refuses every class outside the row's authorization. No credential is
stored in plaintext in the repository, and rotation is a hub restart — which is
also when enrollment tokens arm.

## Honest limits

This boundary protects the **decision channel and the audit trail**, not the
runner. A job executing on a lane can already install software for itself; this
change makes the operator-visible decisions attributable and the resulting
images digest-pinned, and it does not make a lane hermetic. Read
`mon-tc-05` as a statement about provenance, not as a claim about confinement.

## Data shape

New top-level collection in `runners.json`, alongside `runners`:

```
toolchain_requests: [
  {
    id:                  "tcr-0001",
    lane:                "lane-A",        # hub runner_name
    tool:                "cargo",         # one row per (lane, tool)
    required_profile:    "rust-bevy",    # reviewed, trusted
    state:               "open",         # open|approved|built|fulfilled|denied
    version:             3,              # CAS counter
    observed_at:         "<iso8601>",
    last_seen:           "<iso8601>",
    coverage:            "reported",     # reported|never-reported|stale|probe-failed
    actor:               "<claim>",      # decision identity as presented
    credential_id:       "<id>",
    decided_at:          "<iso8601>",
    decision_note:       "<capped text>",
    nonces:              ["<consumed>"], # replay defence
    build_id:            "<id>",
    builder_identity:    "<id>",
    lane_image_digest:   "sha256:...",   # when built
    fulfilled_at:        "<iso8601>",
    suppression_until:   "<iso8601>"     # when denied
  }
]
```

Per-runner, separate from the above and **not** touching the evaluator fields:
`lane_image_ref`, `lane_image_digest`, `toolchain_profile_id`, `coverage`.

## Risks

- **Profile drift.** A lane's required profile is trusted and reviewed; a stale
  profile reports gaps nobody needs. Mitigation: profiles are versioned with the
  capability, and a fulfilled request records the profile it was fulfilled
  against.
- **Single-principal attribution.** v1 decisions share one principal by
  construction. Mitigation: stated in `mon-tc-03`, visible in the audit record.
- **Request spam.** A lane whose image never gains the tool re-reports every
  300s. Mitigation: upsert on `(lane, tool)`, `last_seen` advances, no new row.
- **Approved but never built.** Mitigation: numeric fulfillment window,
  outstanding reporting.