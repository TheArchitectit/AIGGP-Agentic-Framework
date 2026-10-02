> **Re-anchored 2026-10-02:** `aiggp-00`/`aiggp-09` are retired (see `openspec/changes/AIGGP-RETIREMENT-2026-10-02.md`); references below read against DevGate's shipped evidence machinery (`hub/coherence/`) and runner enrollment (`scripts/runner-enroll.sh`).

## Required conformance fixtures

- Fixture A: direct injection in content - blocked/disclosed, no execution.
- Fixture B: encoded payload (base64/rot13 instruction) - detected and mediated.
- Fixture C: multi-turn setup (innocent messages then payload) - session-level detection.
- Fixture D: authority impersonation - zero authority granted.
- Fixture E: exfiltration lure (send secrets to endpoint) - blocked and escalated.
- Fixture F: benign technical content resembling injection - allowed within budget.

## Release acceptance criteria

- Corpus bar met per category on pinned corpus; benign budget met; all decisions emit valid envelopes; conformance reproducible by third party.

## Open questions requiring owner decisions

### Q6.1 — Classifier stack + cost/latency budget

**ANSWERED 2026-10-01 (owner).**

**Stack: C — heuristics-first default + model-backed second opinion on
abstain only.** Ordering, not just coupling:

- **Heuristics** (regex / rule / lexer / embedding-similarity): run first
  on every mediation call. Deterministic, near-zero cost. No inference
  runs on the default path. Output annotates kernel evidence per
  proposal.md's product boundary ("The classifier is a module
  capability: it can never redefine verdict truth").
- **Model-backed second opinion** (small local inference; never
  default-on): runs only when heuristics *abstain* — a category the
  heuristics do not confidently classify. Never runs when heuristics
  fire block / sanitize / pass. The opt-in is per-deployment scoped
  (the equivalent of aiggp-00 Q1's org-wide-blast-radius rule — a
  per-message inference path that must never surprise an org's budget),
  and gated behind a schema-version bump on the classification envelope
  if it introduces a new field.

Option B (model-backed hybrid by default) was rejected on two
grounds: (1) a stochastic inference step inside the default mediation
path breaks `coh-eval-01`'s determinism guarantee; (2) overclaiming —
"we run a model-backed classifier" invites trust we cannot prove
corpus-wide without publishing the misses. Option A alone (no model at
all) was rejected because multi-turn setups and oblique authority
impersonation heuristically harden the class; a second opinion on
abstain catches a slice without taxing default.

**Cost/latency budget (stated assumption SA-5):** v1 heuristics have no
measurable cost beyond envelope emission and stderr logging — target
under 1 ms per mediation call. The opt-in model second opinion is scoped
per-deployment (declared ceiling in the bundle projection: per-call
latency, per-deployment GPU/runtime cost) — never a default. True
budget numbers ride the bundle in `policy-bundles/[bundle].toml` per
Q5, not the code.

### Q6.2 — The initial pass bar per category

**ANSWERED 2026-10-01 (owner).**

**Bar: A — strict split by blast radius.**

| Category | Bar | Why |
|---|---|---|
| Direct injection | **100%** | Any miss is a catastrophic, immediate exploit. Org-scale blast radius; zero miss-tolerance per the aiggp-00 Q1 invariant. |
| Exfiltration lures | **100%** | Same class — exfil is the artifact the whole stack is guarding. |
| Instruction-in-content | Declared threshold in the `policy-bundles` bundle. Miss rate **published**. | |
| Encoded payloads | Declared threshold in the `policy-bundles` bundle. Miss rate **published**. | |
| Multi-turn setup | Declared threshold in the `policy-bundles` bundle. Miss rate **published**. | |
| Authority impersonation | Declared threshold in the `policy-bundles` bundle. Miss rate **published**. | |

"100% on any category" (option B) was rejected as an overclaim-prone
number — "100%" without published misses is exactly the
overclaiming-detection-capability risk the proposal names. 100% on the
two catastrophic classes is 100% *of the corpus*, not 100% of reality;
that honesty sits alongside the fixed bar.

Option C (declared thresholds on direct + exfil too) was rejected on
the same org-scale-blast-radius principle — a miss there is
catastrophic, not budgeted. Option D (no numeric bar) left the
package's release-acceptance criterion ("all fixtures pass")
ambiguous about what pass means, and handoff.md's insistence on
publish-misses already implies a numeric claim per category is
expected.

Proposal's "publish misses" is a *required* artifact, not an
aspiration: the corpus run's miss table is part of each release's
envelope evidence (aiggp-00's "subject digests, bundle digest, module
identity and version, claimed capability, raw result, and provenance
chain" naturally applies to the classifier claim).

### Q7 / Q6-overlap — next open question in aiggp-03 acceptance

(No third open question in this package's acceptance.md; **aiggp-04
semantic-content-filtering** is next in the queue.)

## Handoff

Build the corpus before the classifier: the attack set defines the claim. Wire envelope emission from day one so every tuning decision is auditable. Publish misses - the reputation play is honesty about detection, not a magic number.
