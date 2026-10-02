> **Re-anchored 2026-10-02:** `aiggp-00`/`aiggp-09` are retired (see `openspec/changes/AIGGP-RETIREMENT-2026-10-02.md`); references below read against DevGate's shipped evidence machinery (`hub/coherence/`) and runner enrollment (`scripts/runner-enroll.sh`).

## Required conformance fixtures

- Fixture A: credential in commit - redacted, hash recorded, block at boundary.
- Fixture B: personal data in outbound send - held for escalation per policy.
- Fixture C: benign code resembling secrets - allowed within false-positive budget.
- Fixture D: classifier timeout at boundary - escalate, not allow.
- Fixture E: version bump without re-run - stale status reported.

## Release acceptance criteria

- All fixtures pass; per-category budgets met on pinned corpora; envelope validation rejects identity-less decisions; drift monitor demonstrates one detected behavior change in test.

## Open questions requiring owner decisions

### Q7 — Classifier provider(s) + local-vs-hosted posture

**ANSWERED 2026-10-01 (owner).**

**Posture: B — local-first classifiers are the default; hosted classifier
is a per-deployment opt-in for specific categories.**

Default plane (v1 core categories, starting with secrets/credentials per
handoff.md):
- Regex / entropy / keyword grammar ships as the classifier-of-record.
- Zero third-party calls by default. Zero egress to a provider on the
  classification path. Zero per-message cost beyond envelope emission
  (aiggp-00's evidence envelope already carries classifier identity and
  version — local grammars are accountable to that).
- Secrets/credentials is the cleanest category and the handoff's first
  target: a well-designed regex/entropy combo is authoritative enough to
  ship the "do not commit secrets" bar the proposal names without
  host-mediated classification.

Opt-in plane (per-category, not whole-system):
- A category MAY be flagged "hosted" in its `policy-bundles` entry when
  local grammars genuinely underperform (PII / financial / IP-licensing
  content are the candidates that ship later).
- The flag is gated behind the aiggp-00 Q1 org-wide-blast-radius
  invariant: sending content to a third party is an org-scale data
  exposure decision — "if you do it and don't understand what you're
  doing you break your entire org" — so a per-deployment opt-in (never
  default), a schema-version bump on the classification envelope's
  provider field, and a signed vault-log of that decision are all
  expected, not optional.
- Hosted calls run on the *abstain* path only when the local classifier
  is ambiguous for that category (same abstain-only shape as aiggp-03
  Q6's model second-opinion). Never default-on.

Option A (local-only, no opt-in plane at all) was rejected because the
proposal and handoff anticipate categories where local grammars can't
outperform hosted classification — leaving the plane entirely off
forever means PII / financial core categories never ship trustworthy
detectors. Option C (hosted default) was rejected on the Q1 invariant:
defaulting to third-party-mediated classification is exactly the crash-
radius move the invariant names. Option D (ship-only-what-local-detects)
was rejected because it treats a tuned classifier that fails
confidently ("published failure-mode table is a reputation asset")
as operationally equivalent to a category that simply doesn't exist,
and the proposal's separation of concerns (filter/business/data
failure modes) explicitly branches on both directions.

**Cost/latency budget (stated assumption SA-6):** local classification
runs in the same "identity-and-noise" tier as aiggp-03 Q6's env emission —
microseconds per message logged locally. Hosted fast-path, when
opted-in, is scoped per-deployment through the same budget rig
(aiggp-03's SA-5, `policy-bundles/[bundle].toml`) — never a default.

### Q8 — Escalation routing (who decides held sends) for solo vs team deployments

**ANSWERED 2026-10-01 (owner).**

**Answer: A as the default, with B and C as optionals layered on top.**
Escalation *authority* is always bundle-declared identity; alerting and
workspace surfaces are optional *channels*, never the decision identity
themselves.

**Default (A) — bundle-declared routed identity.**
`policy-bundles/[bundle].toml` declares who is authorized to close an
escalation (by identity hash — CA-optional per SA-9: a key-hash allowlist
entry when no CA runs, a CA-signed identity when one does; the retired
aiggp-00 kernel is not the source, see AIGGP-RETIREMENT-2026-10-02.md).
Solo default = the deployer. Team re-points the routed
identity to a role, on-call rotation, or designee. No hardcoded routing
lives in the code — the bundle owns it. Resolution is a signed envelope
referencing the held-matter envelope; the resolver's identity hash
matches the bundle-declared routed identity at resolution time.

**Optional (B) — alert-channel notification on the same hold.** When
opted-in per deployment, an escalation *also* emits an alert envelope
alongside the hold (hooking the existing `hub_alert` / runner-monitor
alert pipeline). This is a notification surface only — the PAGER is
not the authorized resolver. The alert envelope is evidence of
"someone was told"; closing the escalation still requires an envelope
signed by a bundle-declared identity. Blast-radius: tightening alert
routing (e.g. paging a channel) is the deployer's daily ops call; it
can never silently widen who can *close* an escalation.

**Optional (C) — workspace surfacing for team deployments.** When
opted-in per deployment, a held send *also* opens a ticket/PR on a
team-visible surface, and the resolution travel is a signed envelope
from that workspace. Again: the workspace is the notification surface;
identity authority is unchanged. Does not introduce a mandatory
workflow step to unblock (solo deployer closes directly per A).

**Invariants:**
1. **Authority is never the channel.** The bundle decides who can
   resolve; B/C merely notify. Widening the channel (adding a webhook,
   a pager, a ticket) must not silently widen the resolution set.
2. **B and C are opt-in per deployment** under aiggp-00 Q1's
   org-wide-blast-radius invariant: turning on an escalation web hook
   fans a hold's payload out to a wider surface, which is exactly the
   "understand before you flip" class. Schema-version bump on the
   escalation envelope's channel field when shipping the alert shape.
3. **Solo-first usability is not optional.** A solo deployer who opts
   into no B/C surfacing still can hold, resolve, and audit every
   send — mirrors the proposal's "before day-one blocking."

Rejected: B-only (left alert-only-routed authority worse than A alone —
whoever configures the pager silently owns escalation resolution);
C-only couples the default path to a team tool solo deploys don't run.
A guarantees the deployment is playable without any of the opt-ins.

(SA-7): the resolved envelope's `routed_identity_hash` check happens at
resolution time against the bundle's *current* routed identity — if the
bundle rotated the routed identity between hold and resolve, the hold's
routed identity stays the resolver identity recorded at hold time. The
bundle's own upgrade path must therefore explicitly decide a cutover
attitude for open holds (default: any hold routed at old identity
expires after a grace window and re-escalates to the new).

## Handoff

Start with secrets/credentials: the clearest category, the easiest corpus, the fastest trust win. Keep every category honest about both failure directions - the published failure-mode table is a reputation asset, not an admission of weakness.
