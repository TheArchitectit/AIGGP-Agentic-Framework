> **Status: imported draft — not a commitment.** The AIGGP program has not started; this package is imported reference material held for future acceptance. It does not modify, supersede, or bind the shipped DevGate specification ladder, and no code, traceability ID, or gate configuration is wired to its requirements. (Added 2026-09-20 per the spec-coherence drift audit; see the AIGGP-02 reconciliation.)

## Summary

Promote the proof-strengthening subset of Stitcher parity into the AIGGP DevGate module: OpenSpec-to-diff review, reverse drift, task traceability, SARIF output, pre-commit hooks, whole-repo mode, external-tool adapters, forge review comments, and coding-agent-loop hooks - each delivered incrementally behind the AIGGP-00 evidence contract with negative controls.

## Problem

The honest verdict from the Stitcher review was that Stitcher is the tighter product on the narrow overlap: it ties review to the spec a change claims to implement, in both directions, and meets reviewers in their existing tooling. DevGate's equivalent surfaces are weaker, which means its green carries less proof. The full parity package exists but predates AIGGP; promoting it wholesale would import twelve features with no shared evidence contract. The platform needs the proof features, in dependency order, each verifiable.

## Desired outcomes

- OpenSpec-to-diff review: a change is evaluated against the specific spec requirements it claims to implement, with per-requirement verdicts.
- Reverse drift: code changes with no covering spec requirement are findings, not silence.
- Task traceability: spec tasks map to commits; orphan tasks and orphan commits are both reported.
- SARIF output: findings flow into standard review tooling without bespoke parsing.
- Pre-commit mode: the same gates run locally before push, identical verdicts to CI.
- Whole-repo mode: full-tree evaluation beyond diff scope, on demand and scheduled.
- External-tool adapters: results from other scanners ingest as evidence with their own identity, never silently re-labeled as AIGGP checks.
- Forge review comments: findings posted as review comments keyed to evidence links.
- Coding-agent-loop hooks: agent loops consume promote/halt verdicts through the same contract as AIGGP-02.

## Product boundary

Promoted set is the nine features above. Explicitly not promoted: LLM advice beyond advisory annotation (stays proposed per the plan - it cannot determine blocking truth without a deterministic contract), and any Stitcher feature outside the absorbed package. Each promoted feature ships only behind the evidence contract; feature completeness without evidence is not delivery.

## Users and calling systems

- Reviewers consuming findings in SARIF-compatible tooling and forge comments.
- Developers running pre-commit gates locally.
- Coding-agent loops (Claude Code and peers) consuming promote/halt verdicts.
- The AIGGP ledger receiving per-feature evidence.

## Success measures

- Each promoted feature emits valid AIGGP-00 envelopes on its real execution path.
- Each has a negative control proving it can fail (a seeded case it must catch).
- Pre-commit and CI produce identical verdicts on the same change.
- SARIF output validates against the SARIF schema and round-trips into a standard viewer.

## Risks

- Feature-list chasing: shipping twelve shallow features instead of nine proven ones. Control: incremental promotion with per-feature acceptance; the absorbed package stays the backlog.
- Adapter laundering: external tool results re-labeled as first-class checks. Control: adapters record tool identity and version; aggregation weights are bundle policy.
- Local/CI divergence in pre-commit mode. Control: same images, same scripts, identical-verdict fixture in CI.
