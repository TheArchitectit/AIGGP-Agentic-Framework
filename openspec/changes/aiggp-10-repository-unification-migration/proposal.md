## Summary

Create one canonical AIGGP repository from the existing Agent Guardrails repository and the DevGate repository. Import DevGate by a non-squashed subtree merge, normalize both products behind explicit module boundaries, migrate CI and release automation in parallel, prove history and behavior continuity, then archive the standalone repositories with durable pointers to the unified source.

## Problem

The product decision is settled, but the physical source-of-truth move is unspecified. AIGGP-01 repairs DevGate, AIGGP-00 defines shared truth, and AIGGP-02 through AIGGP-09 define capabilities. None says how two live Git histories become one repository without losing blame, tags, audit work, release provenance, or CI truth. An improvised move could flatten DevGate into one commit, leave the audit branch behind, run duplicate or contradictory release jobs, break consumers pinned to the old repository, or archive the old repository before the unified one has proved itself.

## Desired outcomes

- One canonical AIGGP repository contains the policy, repo/CI/release, kernel, bundle, schema, conformance, and generated-document surfaces.
- Every commit reachable from the selected DevGate main and Agent Guardrails main cutover heads remains reachable from a documented ref in the unified repository.
- DevGate's audit branch is reconciled per AIGGP-01 before import; its original tip also remains recoverable as an archival ref.
- CI runs old-path compatibility checks and new-path checks through a controlled overlap, with no branch-protection window in which required checks disappear.
- Existing release tags remain unambiguous and resolvable; the first unified release declares both predecessor baselines.
- Old repository URLs remain readable, clearly archived, and point humans and automation to the replacement.
- A rehearsed rollback can restore the pre-cutover repositories and required checks before the point of no return.

## Non-goals

- This package does not implement AIGGP-00 through AIGGP-09.
- It does not bulk-merge the DevGate audit branch or decide unresolved AIGGP-01 findings.
- It does not redesign module internals merely because files move.
- It does not remove compatibility shims before their declared window ends.
- It does not create paid tiers, private editions, or a commercial source split.
- It does not authorize the migration. It is the delivery contract for a later owner-approved implementation.

## Users and calling systems

- Maintainers working in the unified repository.
- CI runners and release automation consuming DevGate and Agent Guardrails paths.
- Repositories that pin DevGate by repository URL, submodule path, action reference, package, container, or release tag.
- Auditors tracing a finding or release back to predecessor commits.
- AIGGP conformance fixtures validating module boundaries and evidence continuity.

## Success measures

- History manifest proves 100 percent reachability of both cutover heads, the original audit tip, and every preserved release tag.
- Fresh-clone CI exercises policy, DevGate, kernel contracts, integration boundaries, and negative controls on the merged tree.
- A migration fixture containing consumers for each supported integration route passes before archive.
- Old and new execution paths produce equivalent verdicts and evidence for the agreed golden corpus during overlap.
- No required branch-protection check is absent, renamed without mapping, or made optional during cutover.
- First unified release can be traced to both predecessor baselines from its release manifest alone.

## Severity-ranked migration risks

- P0 - false-green cutover: required checks disappear, silently skip modules, or change names under branch protection.
- P0 - history loss: squash/fresh copy drops commit ancestry or archival branch tips.
- P0 - divergent writes: work lands in an old repository after the canonical cutover and is not represented in AIGGP.
- P1 - release ambiguity: colliding tag names, reused versions, or artifacts that cannot name their source tree.
- P1 - consumer breakage: submodules, reusable workflows, package paths, and pinned action references stop resolving.
- P1 - premature archive: old repositories become read-only before rollback and consumer migration are proven.
- P2 - blame discontinuity: mechanical path moves obscure authorship despite preserved ancestry.
- P2 - documentation drift: hand-written guardrail documents return in repositories instead of being generated from the shipped policy bundle.
