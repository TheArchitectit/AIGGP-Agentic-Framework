# AIGGP-02 ↔ shipped coherence-service: requirement reconciliation

**Status: reconciliation record — not an acceptance decision.**

The 2026-09-20 spec-coherence drift audit found AIGGP-02's overlap with the
shipped `devgate-spec-coherence-service` package unreconciled (import commit
`ec0c9e1` flags it). This file disposes every AIGGP-02 requirement against its
shipped counterpart.

**Scope limit — read this first.** The AIGGP program has not started. AIGGP-02
is an imported draft, not a commitment; nothing in this repository is built to
its requirement IDs, and no `coh-*` ID is claimed by an AIGGP-02 delta. Every
row below therefore disposes as either *duplicate of shipped* or *not built
(program not started)*. There is no "identical, adopt as-is" disposition
available, because adopting a draft requirement is an AIGGP lifecycle event that
has not occurred.

**Precedence rule for any future conflict:** the shipped ladder wins. Where the
draft and the shipped spec state the same obligation, the shipped text is the
one under test today, and it is generally the stronger of the two (see the
strictly-stronger rows below). A future AIGGP-02 acceptance must reconcile
*against* the shipped spec, not the reverse.

Recorded per the audit's disposition vocabulary: **duplicate (shipped stronger)**
/ **duplicate (shipped equal-or-stronger)** / **not covered by AIGGP-02** /
**novel in draft**.

Disposition "reconcile at coherence-service archive" applies to every row that
names a `coh-*` ID: those IDs live only as deltas in
`openspec/changes/devgate-spec-coherence-service/`, so a `## MODIFIED` delta in
AIGGP-02 could not name-match them until that package archives into
`openspec/specs/`. AIGGP-02's deltas stay `ADDED`.

## 1. Adoption ladder ↔ `adoption-and-policy`

| AIGGP-02 requirement (draft) | Shipped counterpart | Disposition |
|---|---|---|
| centrally enforced minimums | `coh-pol-01` centrally enforced minimums | duplicate — shipped **strictly stronger** |
| bounded advisory stage | `coh-pol-03` bounded advisory stage | duplicate — shipped **strictly stronger** |
| no-regression ratchet | `coh-pol-04` no-regression ratchet | duplicate — shipped **strictly stronger** |

**Strictly stronger, with evidence.** The draft's `coh-pol-01` counterpart reads
"Policy minimums SHALL be set outside repositories. A repository MAY tighten
minimums and SHALL NOT loosen them." The shipped requirement carries that
obligation *plus* an anti-rollback scenario with no draft equivalent: a genuinely
signed but **obsolete** central bundle with weaker requirements must be rejected
unless the control plane has explicitly grandfathered it for a recorded window,
and the attempt must be visible in fleet reporting. Signing proves identity, not
currency, and only the shipped spec tests for that.

The same pattern holds for `coh-pol-04`: the shipped text states the baseline is
a ceiling and that entries are finding **fingerprints, not counts**, with a
secondary scenario ("one fixed, one new, count unchanged") proving the
fingerprint semantics — a scenario the draft lacks entirely. A count-based
baseline silently absorbs a new violation when an old one is fixed; the shipped
spec is the only one that catches it.

## 2. Coherence evaluation ↔ `coherence-evaluation`

| AIGGP-02 requirement (draft) | Shipped counterpart | Disposition |
|---|---|---|
| deterministic evaluation | `coh-eval-01` deterministic evaluation | duplicate — shipped equal-or-stronger |
| complete required assertion execution | `coh-eval-02` complete required assertion execution | duplicate — shipped equal-or-stronger |
| semantic assertion traceability | `coh-eval-04` semantic assertion traceability | duplicate — shipped equal-or-stronger |

The draft's determinism requirement binds the verdict to "repo revision, spec
package, policy package, evaluator image"; the shipped `coh-eval-01` additionally
binds evaluation context and declared capabilities, and adds the "evaluator reads
time" negative scenario (a plugin whose result depends on wall-clock time must be
rejected at conformance). Shipped is the superset.

## 3. Promote/halt ↔ `integrations`

| AIGGP-02 requirement (draft) | Shipped counterpart | Disposition |
|---|---|---|
| uniform promote/halt verdict | `coh-int-03` promote-or-halt contract | duplicate — shipped equal-or-stronger |
| no implicit trust from upstream | `coh-int-04` no implicit trust from upstream | duplicate — shipped **strictly stronger** |

These two are the sharpest overlap: same requirement names, 1:1. The shipped
`coh-int-04` is stronger because it is *fallible in the right way* — "An upstream
build success, test pass, or signed artifact MUST NOT substitute for
spec-coherence evaluation" — and carries the scenario "upstream artifact is
signed but unevaluated". The draft stated the prohibition but shipped with no
scenario at all until this remediation authored one (the audit's demotion exposed
the gap). Note that the scenario authored here under the draft expresses the same
digest-binding rule the shipped scenario already tests, so the overlap is now
explicit rather than latent.

## 4. Shipped-only — not covered by AIGGP-02

| Shipped requirement | Disposition |
|---|---|
| `coh-pol-02` authenticated policy authority | not covered by AIGGP-02 — shipped superset |
| `coh-pol-05` finding fingerprint definition | not covered by AIGGP-02 — shipped superset |
| `coh-pol-06` scoped exceptions | not covered by AIGGP-02 — shipped superset |
| `coh-pol-07` enforcement boundary is external | not covered by AIGGP-02 — shipped superset |

The shipped set is the superset. `coh-pol-02` covers control-plane trust roots
("repository-supplied digests establish identity but never authority") — a real
gap in the draft's ladder, which never says where policy authority comes from.
`coh-pol-07` fixes the enforcement boundary outside the service. An AIGGP-02
acceptance that omitted these would be weaker than what already ships.

## 5. Novel in the draft — not built (program not started)

| AIGGP-02 delta | Disposition |
|---|---|
| envelope-bound evidence (AIGGP-00 dependency) | not built (program not started) |
| 3D-pipeline consumer contract | not built (program not started) — partially overlaps shipped `coh-3d-01..04` |
| per-project coherence history | not built (program not started) |

These three are genuinely new relative to the shipped package, and none is
implemented. Each is a real dependency on work that does not exist:

- **Envelope-bound evidence** requires the AIGGP-00 kernel truth model (signed
  evidence envelopes, verdict algebra), which is a draft. The shipped service
  emits its own envelope shape; adopting AIGGP-00's would be a migration, not a
  format tweak.
- **3D-pipeline consumer contract** overlaps the shipped `subjects-3d`
  capability (`coh-3d-01` 3D subject manifest, `coh-3d-02` repair invalidates
  prior results, `coh-3d-03` pipeline consumes the common contract, `coh-3d-04`
  captures are declared inputs). The overlap should be resolved in favor of the
  shipped `coh-3d-*` set at acceptance time; the draft adds a *pipeline-side*
  obligation the shipped spec does not state from the consumer's direction.
- **Per-project coherence history** has no shipped counterpart. The shipped
  service is stateless per evaluation (`coh-eval-01` determinism is a pure
  function of inputs); history is an aggregation layer that does not exist.

## 6. Cross-package findings (audit S6)

- **AIGGP-01 (gate correctness)** overlaps this audit's own findings: its
  "no vacuous gates", "correct audit subject" (a gate SHALL NOT audit the
  DevGate submodule instead of the project), and "no dead configuration"
  requirements target DevGate's *shipped* scanners and gate configuration —
  the same surface findings 2-4 of the drift audit cover. It is **not** a
  target mismatch (an earlier working note claiming it targeted Jinja/3D-adapter
  codebases was wrong; `grep -in 'jinja\|adapter'` over its specs returns
  nothing). Disposition: **not built (program not started)** — this branch
  closes the audit's findings directly, and AIGGP-01's requirements remain
  accepted-or-not on the future AIGGP lifecycle, not here.
- **AIGGP-00, -09, -10** cannot be closed by this branch either; they depend on
  the AIGGP program. This branch's `tasks.md` tracks the *drift audit's*
  findings, not AIGGP package acceptance. Reaching 31/31 strict green is what
  unblocks that acceptance discussion; it does not constitute it.

## 7. No false closure

Two rules this reconciliation deliberately does not break:

1. **No `## MODIFIED` deltas in AIGGP-02.** A MODIFIED delta name-matches a
   requirement in a *published* spec. The `coh-*` requirements exist only as
   deltas inside `devgate-spec-coherence-service`, which has not archived into
   `openspec/specs/`. A MODIFIED targeting them would be unresolvable today.
2. **No duplicated IDs.** Inventing AIGGP-02 IDs that mirror `coh-*` would put
   two requirement IDs with the same capability key into
   `scripts/spec_traceability.py`'s accounting, manufacturing coverage for
   requirements that are not implemented. The AIGGP-02 deltas carry no ID
   markers at all (see the conformance commit).

## Reconcile-at-archive checklist

When `devgate-spec-coherence-service` archives into `openspec/specs/`:

- [ ] Re-run this comparison against the *published* `coh-*` requirements, not
      the deltas, and confirm the strictly-stronger verdicts still hold.
- [ ] Decide whether the draft's three novel items are accepted, deferred, or
      dropped — this is an AIGGP lifecycle decision, not a repository fix.
- [ ] If any novel item is accepted, its delta may then be retargeted to
      `MODIFIED` against the published `coh-*` requirement it strengthens.
- [ ] Resolve the 3D-pipeline overlap toward the shipped `coh-3d-*` set unless a
      documented consumer-side gap justifies the draft's additional obligation.
