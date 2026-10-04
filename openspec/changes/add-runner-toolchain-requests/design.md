# runner-toolchain-requests — Design

## Context

A fleet runner that lacks a toolchain cannot ask for one. This design adds the
request channel, the decision surface, and the fulfillment path that keeps the
digest-pinned property the fleet already has.

The measured facts the design rests on are in `proposal.md` §Why. The three
that constrain it:

1. Stock runner image = `git`, `python3`, `jq`, `bash`. Nothing else.
2. Runners are uid 1001 with `NOPASSWD: ALL` and unrestricted egress.
3. Provisioning happens by rebuilding a lane image and repointing a quadlet.

## Decisions

### D1 — The hub owns request state; Mission Control owns the decision

The hub is the only component that authenticates every runner (per-runner
heartbeat tokens, salted hashes at rest per mon-sec-02). Adding `missing_tools`
to the existing heartbeat needs no new credential and no new network path.

The alternative — runners POST directly to MC — would create a second source of
truth for fleet state. This fleet already carries that class of drift: ten
registry rows that recorded `OWNER/<repo>` placeholders instead of resolved
repositories (repaired 2026-10-04), and helper scripts that had drifted from
their checkout. MC reads and decides; the hub remembers.

**Rejected:** MC as system of record. It has no hub client today, and putting
fleet state there would mean two components disagreeing about which runners
exist.

### D2 — A request states a gap, never a remedy

The runner reports what it lacks: `missing_tools: ["cargo"]`. It does not name
a package, version, URL, or command.

This is the security boundary of the whole feature. With free text, the
approval button becomes "run this string as root on a machine that executes
private-repo code" — a remote package installer with a UI. With a closed
vocabulary, approval is "add toolchain profile X to lane Y", a decision about a
reviewed artifact.

The vocabulary is declared in the spec and versioned with it. An unknown tool
name is rejected at the boundary, not stored and not displayed.

### D3 — Approval means a pinned image change, not a live install

An approved request is fulfilled by rebuilding the lane image with the toolchain
added and recording the resulting digest. It is not fulfilled by
`apt-get install` on the running runner.

If approval mutated a live runner, then what a lane contains would depend on
what got clicked, in what order, and on which of its jobs asked first. That
breaks the property `image_digest` records and `image_pin_divergence`
(img-cycle-05) detects — both would become noise — and it would leave no
artifact to audit.

**Rejected:** live install. It is the intuitive reading of "approve software
installation", and it is the one that costs the fleet its supply-chain
guarantee.

### D4 — Decision auth is separate from runner auth

The hub has no user authentication today: `/enroll`, `/heartbeat`, and
`/revoke` authenticate with one-time enrollment tokens and per-runner heartbeat
tokens. There is no operator identity anywhere in the system.

An approve action cannot ride on a heartbeat token — those are held by every
job on the lane, and the operator approving is not the lane asking. This change
introduces an operator credential distinct from `HEARTBEAT_TOKEN`, and the
request record stores who decided and when.

The exact mechanism (bearer token, mTLS, existing MC session forwarded) is
implementation detail; the requirement is that a runner cannot decide its own
request, and that a decision is attributable.

### D5 — Requested, not blocking

A runner reports a gap and continues. The heartbeat still exits 0. The job that
needed `cargo` still fails — correctly, and before this change it failed without
saying why.

The request exists to convert an unexplained failure into a visible, owned
decision. Making the job wait on a human would turn a missing toolchain into a
stuck queue on every lane at once.

**Rejected:** fail-closed heartbeat. A gap that blocks the heartbeat would
also block the report of that same gap.

## Data shape

New top-level collection in `runners.json`, alongside `runners`:

```
toolchain_requests: [
  {
    id:                  "tcr-0001",      # monotonic, per-registry
    runner_name:         "ucs03-zhm",     # the lane that reported the gap
    missing_tools:       ["cargo"],       # closed vocabulary only (D2)
    state:               "open",          # open|approved|denied|fulfilled
    reason:              "ci.yml needs cargo for the Bevy build",
    first_seen:          "<iso8601>",
    last_seen:           "<iso8601>",     # re-reported while still open
    decided_by:          "<operator id>", # null until decided
    decided_at:          "<iso8601>",     # null until decided
    decision_note:       "<free text>",   # null until decided
    fulfilled_digest:    "sha256:…",      # the pinned image, when fulfilled
    fulfilled_at:        "<iso8601>"      # null until fulfilled
  }
]
```

`fulfilled_digest` is the join to the lane's existing `image_digest`: when a
fulfilled request's digest matches what the runner reports, the gap is closed
by construction rather than by a second mechanism noticing.

## Data flow

1. Runner's job needs `cargo`; the image lacks it. The spoke compares the
   image's toolchain against the vocabulary and adds `missing_tools` to its next
   heartbeat.
2. Hub verifies the heartbeat token as usual, upserts an `open` request per
   `(runner_name, tool)`, and records `last_seen`.
3. MC's dashboard route lists open requests with the lane's repo, host alias,
   and current `image_digest`, so the operator decides with context.
4. Operator approves (with operator auth, D4). State → `approved`.
5. A build produces a lane image containing the toolchain. Its digest is
   recorded as `fulfilled_digest`; state → `fulfilled`.
6. Lane redeploys; the next heartbeat reports a new `image_digest`. The gap
   closes because the tool is present, and `image_pin_divergence` continues to
   do its job.
7. Deny, or approve-then-build-fails: state → `denied` or back to `open`, with
   `decision_note`. Never silently closed.

## Risks

- **Vocabulary drift.** A lane needing a tool the vocabulary lacks cannot
  express it. Mitigation: the vocabulary is spec-governed and extended by
  change, and an unknown name is rejected loudly rather than dropped.
- **Request spam.** A lane whose image never gains the tool re-reports every
  300s. Mitigation: `last_seen` updates in place; no new row per heartbeat.
- **Stale approvals.** Approved but never fulfilled. Mitigation: an approved
  request older than the rebuild window is surfaced as such in the dashboard —
  the same "absence is not health" rule the rest of the hub follows.

## Open questions for implementation

- Does approval trigger the build, or does a separate CI job build and report
  the digest back? The spec requires only that fulfillment is recorded with a
  digest; the trigger is a delivery decision.
- Should a fulfilled request for a tool the image later loses re-open
  automatically? Leaning yes — it is the same gap, and the vocabulary makes it
  expressible.