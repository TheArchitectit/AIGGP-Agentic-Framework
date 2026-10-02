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
  sweep (131-entry declaration; T-08/T-14/T-15 mutation proofs). Fleet
  scope shape, not per-repo.

Two shapes, one adapter contract: the stitcher's proof-parity claim
("external-tool outputs reconstruct into the evidence chain with the
same rigor as internal ones") is only credible if it survives both a
per-repo scanner and a fleet-wide declaration sweep. A single-shape
first-target (A alone) proves less.

`spec_traceability.py` (option C) is a natural third target once the
combo is proven — it is conceptually closest to the aiggp-00 evidence
chain (spec IDs ↔ implementation ↔ coverage) — but not the initial
combo because it is already part of the DevGate's own evidence surface,
so it does not stress the "external-tool" boundary the way the two
scanners do.

## Handoff

Reconcile the existing parity branch against current main first (same cherry-pick discipline as AIGGP-01), then run the stages in order. Every stage demo shows the negative control failing first - that is the proof the feature is real.
