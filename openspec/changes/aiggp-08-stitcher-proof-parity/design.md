## Design principles

- Proof over coverage: a feature exists when its evidence exists.
- Bidirectional drift: spec-without-code and code-without-spec are both findings.
- Meet reviewers where they are: SARIF and forge comments, not a new dashboard to check.
- External results keep their names: ingestion preserves tool identity.

## Locked decisions

- Promotion order: (1) task traceability, (2) OpenSpec-to-diff review, (3) reverse drift, (4) pre-commit, (5) SARIF, (6) forge comments, (7) whole-repo mode, (8) external-tool adapters, (9) coding-agent-loop hooks. Each stage gates the next.
- Per-feature negative control: no feature merges without a seeded-failure fixture it must catch.
- LLM advice: advisory annotation only, marked non-blocking in every surface; excluded from the promoted set.
- Adapter evidence: external tool results carry tool identity, version, and raw output reference; AIGGP never re-issues them as its own findings.
- Pre-commit parity: local mode runs the same digest-pinned images as CI.

## Major components

1. Traceability engine (spec tasks to commits, both directions).
2. Diff-review evaluator (per-requirement verdicts over the change).
3. Reverse-drift scanner (uncovered changes as findings).
4. Local runner (pre-commit) with CI-parity harness.
5. SARIF emitter.
6. Forge comment adapter (GitHub first; GitLab via AIGGP-07 adapter).
7. Whole-repo evaluation mode.
8. External-tool ingestion adapter interface.
9. Agent-loop verdict endpoint (promote/halt contract).

## Trust boundaries

- External tool results are third-party evidence: identity-stamped, never elevated to first-class without re-execution.
- Forge comment posting is the only write to forge surfaces; it carries evidence links and never edits code.
- Agent loops are consumers of verdicts, not authors: loop output re-enters as new unverified changes.
