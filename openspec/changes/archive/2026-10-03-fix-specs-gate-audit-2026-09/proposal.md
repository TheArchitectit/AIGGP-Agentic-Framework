# Proposal: fix-specs-gate-audit-2026-09

## Why

An external spec-coherence drift audit (2026-09-20, against HEAD `5af12bb`)
returned **RED — not a safe repository-unification baseline**. Two of its four
binding findings were about gates that did not actually gate:

1. **The declared hard spec gate was red.** `openspec validate --all --strict`
   failed 26 of 31 items: 11 AIGGP change packages whose specs used
   `## Requirement:` / `### Scenario:` where the delta grammar requires
   `## ADDED Requirements` / `### Requirement:` / `#### Scenario:`, and 15 base
   specs missing the mandatory `## Purpose`. The specs CI job was failing.
2. **The self-test lane was a false green.** `run-tests.mjs` and
   `semantic-scan.mjs` resolved the project root by walking UP from the parent of
   DevGate's own directory looking for a marker file. Run inside the checkout on
   a machine whose parent carries a `package.json` (`/mnt/data/git`), the walk-up
   settled on that shared directory: semantic-scan counted thousands of files it does
   not own, and `run-tests.mjs` discovered **zero** of DevGate's own tests yet
   printed `TOTAL: 0 passed` and **exited 0**. The audit's mutation battery
   survived every root-resolution mutation it tried (0/10 killed). Separately,
   `ci.yml` invoked `tests/test_scanner_root_anchor.mjs`, a file that had never
   existed in any commit.

Both are the same class of defect the whole gate exists to prevent: a gate that
reports success while evaluating nothing, or while evaluating the wrong tree.
This package records the audit and the contracts that prevent recurrence. The
two *other* audit findings — the containerized coherence path not yet
rebuilt/re-pinned, and AIGGP-02's overlap with the shipped ladder — are handled
outside this package's deltas: the first stays open on the coherence-service
merge gate, the second is dispositioned in that package's `reconciliation.md`.

## What Changes

- Adds **`openspec-format-conformance`**: the published-spec shape contract that
  the 15 failing base specs lacked, plus the rule that imported draft packages
  carry no requirement IDs (an ID on an unimplemented draft manufactures false
  traceability coverage). Defines `spec-fmt-01`, which `ci.yml` has referenced
  in a comment since the migrate-specs change but which was never actually
  written down anywhere.
- Adds **`scanner-root-anchoring`**: the layout contract for project-root
  resolution, and the non-vacuity contract — a test gate SHALL NOT report
  success after discovering zero tests. Defines `root-anchor-01..03`, marked in
  `scripts/lib/project-root.mjs` and the anchoring fixture.
- Adds a **strict-validation negative control** to the specs CI job: a
  synthetic malformed spec must be *rejected* under `--strict`, proving the gate
  can fail rather than only observing that the tree currently passes. Also pins
  the `openspec` CLI version (today it is resolved through an unpinned `npx`).
- Adds a **CI-checked status row** to the README, so readiness claims are
  generated from what CI actually verified rather than asserted in prose.

## Impact

- Existing specs: format-only changes, already applied on this branch.
- Scanners: one shared contract module replaces two divergent copies; behavior
  for a correctly-laid-out tree is unchanged, and the escape is gone.
- CI: one new negative-control step and a pinned CLI version.
- No runtime behavior change to any gate's *findings*.
