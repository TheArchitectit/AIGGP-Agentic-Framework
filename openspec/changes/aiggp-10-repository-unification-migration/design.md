## Design principles

- Preserve ancestry, not merely files.
- Reconcile before combining: the unified repository imports a known-good DevGate cutover head, not an unresolved branch.
- Parallel prove, then switch: replacement CI must be green and negative controls must fire before old checks are retired.
- One canonical writer after cutover; old repositories are references, not forks.
- Every destructive or hard-to-reverse step has a checkpoint, an owner, and a rollback command sheet.
- Generated guardrail documentation comes from the shipped policy bundle; the unified repository does not become a Markdown copy farm.

## Locked decisions

### Canonical repository

The existing Agent Guardrails repository becomes the physical host for the unified AIGGP repository. This preserves its established policy/runtime lineage and avoids creating a third source-of-truth repository. The repository is renamed to the settled AIGGP name only as a separately approved hosting operation; provider redirects SHALL be verified if a rename occurs.

### History strategy

DevGate SHALL enter through a non-squashed subtree merge into modules/devgate. The merge commit SHALL retain the selected DevGate cutover head as a parent, using an explicit unrelated-histories merge where required. A fresh file copy and a squashed subtree import are forbidden because they do not preserve the full reachable ancestry as migration truth.

Filter-repo rewriting is reserved for a rehearsed fallback only if provider or tooling constraints make a parent-preserving merge impossible. Any filtered import SHALL keep an untouched mirror bundle and SHALL publish old-to-new commit mapping. It is not the default because rewriting hashes expands audit and rollback cost.

### DevGate cutover head and audit branch

AIGGP-01 SHALL finish first. Its cherry-pick-by-finding reconciliation produces a named DevGate main cutover commit. The unified import uses that commit, not specification-time head edca86bc8edb82e8da19022aebba79fc72fd9aca unless AIGGP-01 proves it remains the correct cutover. The original unmerged audit tip SHALL be preserved under an archival namespace such as refs/tags/archive/devgate/audit-original-2026-09-13 and recorded in the history manifest. It SHALL NOT be bulk-merged during AIGGP-10.

### Target directory layout

- modules/policy/ - Agent Guardrails policy/runtime module and policy-bundle renderer.
- modules/devgate/ - DevGate repository, CI, and release enforcement module.
- kernel/ - AIGGP-00 verdict, evidence, waiver, ledger, and subject contracts.
- schemas/ - versioned public schemas shared across modules.
- bundles/ - canonical policy-bundle sources; generated guardrail documents are build outputs, not copied source.
- conformance/ - positive fixtures, negative controls, golden corpus, cross-module proofs.
- integrations/ - forge, runner, coding-agent, and external-tool adapters.
- docs/generated/ - generated documentation output for release artifacts; checked-in status follows the bundle renderer's reproducibility rule.
- tools/migration/ - one-time manifests, verification scripts, consumer inventory, rollback runbook, and tag map; removed or frozen after stabilization by an explicit follow-up.

The first migration commit MAY stage existing Agent Guardrails files in place if moving them and importing DevGate in one commit would make review unsafe. The terminal AIGGP-10 state SHALL match the layout above. Pure moves SHALL be isolated from behavior changes so Git rename detection and human review remain useful.

### Tags and releases

Predecessor tags SHALL remain immutable and namespaced when imported into the unified repository: devgate/<original-tag> and guardrails/<original-tag>. If the provider forbids slash forms, the migration uses devgate-<tag> and guardrails-<tag> and records the exact mapping. Existing unqualified tags in the host repository remain intact; no tag is force-moved or reused. Unified releases begin in an AIGGP namespace and include a release manifest naming both predecessor cutover commits, the policy-bundle digest, schema version, CI run, and conformance evidence.

### Old repository disposition

Old standalone repositories remain writable during rehearsal, enter a short freeze at cutover, and become archived/read-only only after the stabilization gate passes. Each archived repository SHALL have a top-level notice and provider description pointing to the exact unified repository and migration guide. Releases, issues, pull requests, tags, and security history remain readable. No old repository is deleted.

### Generated guardrail documents

The migration SHALL not copy generated guardrail Markdown into consuming repositories. Guardrail documents SHALL be generated at deploy or release from the shipped, content-addressed policy bundle. Compatibility wrappers may invoke the renderer but may not create a second manually edited source.

## Major migration artifacts

1. Source inventory: repositories, default branches, branch protections, tags, releases, packages, container images, workflows, secrets by name/class, webhooks, environments, submodules, reusable workflow callers, action consumers, and open work.
2. History manifest: source URLs, cutover heads, archival tips, imported refs, tag map, merge commit, object reachability proof, and mirror-bundle checksums.
3. Consumer map: every known URL/path/ref dependency, owner, migration mechanism, compatibility window, and status.
4. CI check map: old required-check name to new check name/job, negative control, branch-protection update, and rollback mapping.
5. Release continuity manifest: predecessor tags/releases, unified version namespace, artifact and image mapping, provenance record, and deprecation dates.
6. Rollback runbook: checkpoints, commands, ownership, provider settings, write-unfreeze steps, and data-loss checks.

## Cutover state machine

- INVENTORIED: sources, refs, consumers, CI, releases, and provider settings captured.
- REHEARSED: migration completed in a disposable mirror; history, CI, tags, and consumers verified.
- FROZEN: writes paused on both repositories; heads and provider configuration recaptured.
- IMPORTED: parent-preserving subtree merge and module move exist on a protected migration branch.
- DUAL-PROVEN: old and new paths run the same corpus and negative controls; results match the allowed equivalence contract.
- CANONICAL: unified repository is the sole writable source; redirects and consumer mappings are active.
- STABILIZED: defined observation window passes with no unresolved P0/P1 migration defect.
- ARCHIVED: predecessor repositories are read-only signposts.

A state transition SHALL be recorded in the migration ledger with actor, time, source and destination commits, evidence links, and rollback checkpoint. Skipping a state is forbidden.

## Point of no return

Moved out of `specs/archive-and-rollback/spec.md` (2026-09-20 audit remediation): this is design prose, not a testable requirement, and level-2 sections inside a delta spec file are reserved for delta verbs.

The practical point of no return is not the subtree merge; it is publication of the first unified release plus downstream adoption that cannot be safely reversed. Before that point, rollback is the default P0 response. After it, rollback requires an owner decision and may use a forward repair while keeping the release ledger append-only.
