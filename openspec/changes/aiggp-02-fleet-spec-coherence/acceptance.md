> **Re-anchored 2026-10-02:** `aiggp-00`/`aiggp-09` are retired (see `openspec/changes/AIGGP-RETIREMENT-2026-10-02.md`); references below read against DevGate's shipped evidence machinery (`hub/coherence/`) and runner enrollment (`scripts/runner-enroll.sh`).

## Required conformance fixtures

- Fixture A: coherent minimal repository - full green.
- Fixture B: identity drift repo (gamerepo01 case) - FAIL naming drifted requirements.
- Fixture C: advisory-debt repo (LobsterWars case) - advisory stage with recorded debt, no block.
- Fixture D: repository bypass attempt (skipping assertions) - ERROR, not green.
- Fixture E: nondeterministic evaluator - conformance rejection.
- Fixture F: evidence tamper - verifier rejection with named check.
- Fixture G: 3D repair loop - verdict on new digest only.

## Release acceptance criteria

- All fixtures pass; determinism proven in CI; envelopes validate against AIGGP-00; one real fleet repo reaches Stage 2 with ledger history; one 3D promote/halt cycle completes end to end.

## Open questions requiring owner decisions

### Q4 — Stage-0 fleet set + per-stage time bounds

**ANSWERED 2026-10-01 (owner).**

**Fleet set: all repos enter Stage 0 simultaneously.** Stage 0 is
*inventory* by the ladder's own definition (proposal.md:
"inventory, advisory baseline, ratchet, enforced core, enforced full —
never day-one blocking"), so it is non-blocking by construction. The
first full-fleet inventory sweep is the baseline measurement every later
stage decision reads against. Pilot-subset and one-repo-first were
rejected on "no blast radius to protect against at a stage that cannot
block" — a pilot buys caution that Stage 0's semantics don't cost
anything.

Standing under aiggp-00 Q1's org-wide-blast-radius invariant: if a
future change ever makes Stage 0 emit anything a consumer could gate on
(a score, a status color, a "stage: inventory" envelope field read as a
verdict), that change is opt-in with a schema-version bump, never
default-on. Inventory stays inventory.

**Per-stage bounds: mixed by stage type.**

| Stage | Bound | Why |
|---|---|---|
| Stage 0 (inventory) | Short, e.g. 1 week to populate. | A measurement window, not a climb. |
| Stage 1 (advisory baseline) | Open-ended; drift monitored via the ledger. | Findings ride the ledger; nothing forces a transition while advisory mode is by definition non-blocking. |
| Stage 2 (ratchet) | **30 days per release cycle** — the only strictly-bounded stage. | The ratchet is where drift can calcify; a clock makes it climb or escalate. |
| Stage 3 (enforced core) | Permanent posture; no bound. | Post-arrival state, not a transit. |
| Stage 4 (enforced full) | Permanent posture; no bound. | Same. |

Fixed-calendar-for-all was rejected: a clock on Stage 3/4 reads as
"you may fall back out of enforcement," which is the wrong incentive.
No-bounds-at-all was rejected: Stage 2 without a clock has no ratchet
pressure — drift waits it out. Mixed bounds match the ladder's own
per-stage semantics: measurement / observation / pressure / posture.

### Q5 — Where the central policy minimums live before the policy-bundles repo exists

**ANSWERED 2026-10-01 (owner).**

**Action: C — stand up the `policy-bundles` repo now, and put the initial
minimums bundle in it day one.** Severity: wrong-shaped authority source
is what the shipped `coh-pol-01` forbids ("Policy minimums SHALL be set
outside repositories"). DevGate is already outside every other repo, but
option A (feat in DevGate's tree → migrate later) would leave a wrong
authority baked into every adopter's config until the migration step —
exactly the org-wide blast-radius class from the Q1 invariant.

Concrete shape:
- Create `TheArchitectit/policy-bundles` (private is fine).
- Seed with one signed initial minimums bundle (TOML or JSON — a
  git-observable file matching the shipped `coh-pol-02` "authenticated
  policy authority" requirement: repository-supplied digests establish
  identity, never authority).
- DevGate ships the bundle as a **pinned-digest reference**, never as inline
  copies. Consumers pin to a digest that names a specific bundle revision;
  repo-level cooldown happens by re-pointing the pinned digest (a commit,
  not a silent config change).
- **Which bundle, and where the pin lives (terminology note).** The word
  "bundle" is overloaded across these packages; both senses are real
  artifacts and must not be conflated:
  - The **spec/eval bundle** (aiggp-00 `design.md: "bundle identity"`) is
    the artifact whose digest covers the manifest, **policy references**,
    parameters, waiver rules, evidence categories, and rendering metadata.
  - The **policy bundle** (this Q5) is the signed minimums artifact in
    `TheArchitectit/policy-bundles`, named by pinned digest inside the
    spec/eval bundle's **policy-reference field**.
  The pin is therefore carried *by the spec/eval bundle*, not by a loose
  config file: the spec/eval bundle's digest transitively commits to the
  exact policy revision. "DevGate ships a pinned-digest reference" means
  the spec/eval bundle (or a DevGate-side consumer config) names that
  digest — never a copy of the policy text.
- When AIGGP-02's central policy authority requirement is later
  formalized, this repo is it. No migration, no freeze step.

Option D (Hub runner host config as source of truth) was rejected on the
"can the verifier name the violation" test: filesystem config is not a
git-observable artifact, and the audit's own config-inspection findings
('dead configuration → silent green') say config that cannot be read is
config that will drift.

Trust root for the policy bundle follows aiggp-00 Q1's CA-optional model:
the bundle's own signature is Ed25519. In a **CA-less deployment
(home-lab default)** the pinned digest is the verifier's fetch-root and
nothing else signs the bundle. In a **CA opted-in deployment** the bundle
is additionally CA-signed at enrollment and the CA's key inventory is the
trust list. Either way the pinned digest is what the verifier fetches
against; the CA is an optional root of *cross-install* trust on top, not
a requirement for standing up `policy-bundles`.

**Where the pin lives (clarification 2026-10-01, alignment review).**
CA-less does **not** mean repo-controlled. The published `coh-pol-02`
contract still binds every deployment: policy resolves from control-plane
trust roots outside repository-controlled input, and repository-supplied
digests establish identity but never authority. So the pinned digest is
carried in **control-plane configuration outside the evaluated repo** —
the DevGate-side consumer config or the fleet's pinned bundle reference,
which a repository's pull request cannot rewrite. A pin placed inside the
repository under test would make the repo its own policy authority, which
is exactly what `coh-pol-02` forbids and what Q5's option D was rejected
for. The CA is optional; the *authority boundary* is not.

## Handoff

Reuse the September 17 package's component design verbatim where possible; the delta is envelope plumbing, the ladder's ledger record, and fixtures. Do not let any consumer special-case the verdicts - the contract is the product.
