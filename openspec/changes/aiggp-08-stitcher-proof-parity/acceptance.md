> **Re-anchored 2026-10-02:** `aiggp-00`/`aiggp-09` are retired (see `openspec/changes/AIGGP-RETIREMENT-2026-10-02.md`); references below read against DevGate's shipped evidence machinery (`hub/coherence/`) and runner enrollment (`scripts/runner-enroll.sh`).

## Required conformance fixtures (per stage, minimum set)

- Fixture A: orphan commit and orphan task - both reported.
- Fixture B: undeclared change - flagged, no clean verdict.
- Fixture C: silent behavior change - reverse-drift finding.
- Fixture D: SARIF round-trip - schema valid, renders in viewer.
- Fixture E: local/CI divergence seed - parity harness catches.
- Fixture F: comment without evidence link - refused.
- Fixture G: ingested external result - identity preserved.
- Fixture H: loop self-certification - treated as unverified.

## Release acceptance criteria

- Each stage's fixtures pass before the next begins; every promoted feature emits valid envelopes on its real path; the promoted set is reported with per-feature maturity.

## Open questions requiring owner decisions

### Q12.1 — How to handle the unmerged parity branch `07aadb05` (Drive bundle)

**ANSWERED 2026-10-01 (owner).**

**Hybrid (option C): reconcile first for the delta that applies cleanly
against current main, re-implement the stale gaps from scratch.** The
handoff's "reconcile the existing parity branch against current main
first (same cherry-pick discipline as AIGGP-01), then run the stages in
order" is honored as the *entry* move — do the reconcile first — but the
hybrid allows that some of the bundle is written against stale main
assumptions and does not want to be dragged through a reconciler that
will produce garbage diffs. Pragmatic order:

1. **Reconcile** (cherry-pick-by-finding) the parity branch against
   current main for whatever applies cleanly — same discipline as
   aiggp-01's finding-by-finding reconciliation of the Kit + Ryan audit
   branch.
2. **Re-implement** anything that lands stale, from current main. Do
   not bulk-merge the Drive bundle (which would re-import the stale
   main assumptions aiggp-01's design.md explicitly warned about for
   the audit branch).
3. **Stage gates after the hybrid is on main** — the stages run against
   the reconciled+re-implemented state, not the bundle's old main.

Option A (reconcile-first-and-everything-goes-through-it) was rejected
because forcing stale material through a reconciler when the rebase
conflict is 100% garbage wastes time without preserving archaeology
value. Option B (re-implement everything from scratch) was rejected
because the existing proof material is real work that deserves a
careful apply where possible.

### Q12.2 — First external-tool adapter target

**ANSWERED 2026-10-01 (owner).**

**Combo: `guardrails-scan.mjs` + `secret-scan-declared.sh` as the
initial adapter targets**, wired in as the first two proven-out
external-tool surfaces of the stitcher. The combo is deliberate:
two very different scanner shapes exercise the stitcher's parity
claim from both directions.

- **`guardrails-scan.mjs`** — the flagship DevGate scanner, the audit's
  named core-gate surface, the one with an existing conformance-adjacent
  suite (`tests/test_guardrails_scan.mjs` 23/23 + `tests/test_guardrails_scan_node.py` 3/3).
  Per-repo scanner shape.
- **`secret-scan-declared.sh`** — the fleet-wide secret declaration
  sweep (declaration generator over `gh repo list`; the 2026-09-30
  census: declared=135, scanned=131, findings=59; T-08/T-14/T-15
  mutation proofs). Fleet scope shape, not per-repo.

Two shapes, one adapter contract: the stitcher's proof-parity claim
("external-tool outputs reconstruct into the evidence chain with the
same rigor as internal ones") is only credible if it survives both a
per-repo scanner and a fleet-wide declaration sweep. A single-shape
first-target (A alone) proves less.

**Anti-laundering invariant (recorded 2026-10-01, cross-package review).**
The proposal explicitly warns against "external tool results re-labeled
as first-class checks." The combo above is DevGate's *own* tooling, which
makes laundering a live risk in the other direction: a stitched
`guardrails-scan.mjs` or `secret-scan-declared.sh` finding must not be
re-presented as a first-class AIGGP check. Binding rule:

- Every adapter-ingested finding records the **source tool identity and
  version** (path + version/commit of the scanner, and its input digest)
  as a first-class field on the evidence envelope.
- Verdicts, severities, and check names stay attributed to the source
  tool. The stitcher's contribution is the *provenance reconstruction*,
  not the authority of the check.
- "AIGGP check" means a check defined by an AIGGP requirement and run by
  an AIGGP module. An adapted tool's output MAY feed an AIGGP verdict
  (as evidence), but the finding itself is never renamed, re-keyed, or
  counted as an AIGGP-native check. Fixture G ("ingested external result
  - identity preserved") is the conformance expression of this rule.

`spec_traceability.py` (option C) is a natural third target once the
combo is proven — it is conceptually closest to the aiggp-00 evidence
chain (spec IDs ↔ implementation ↔ coverage) — but not the initial
combo because it is already part of the DevGate's own evidence surface,
so it does not stress the "external-tool" boundary the way the two
scanners do.

## Handoff

Reconcile the existing parity branch against current main first (same cherry-pick discipline as AIGGP-01), then run the stages in order. Every stage demo shows the negative control failing first - that is the proof the feature is real.
