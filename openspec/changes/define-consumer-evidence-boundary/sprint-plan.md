# Sprint plan — consumer evidence boundary

**Scope:** additive consumer contract; no new wire format, universal interception claim, or evaluator-issued authority.
All source tasks 1.1–3.2 remain unchecked. The design already separates evaluator evidence from consumer authorization.

## Sequence

### S1 — intake/baseline

- For tasks 1.1–1.3, review the published evidence, decision, context, policy, and integration contracts; map trusted context, immutable subject/provenance, bounded coverage, advisory/mandatory modes, and one hermetic fixture.
- Preserve the existing formats and keep private deployments and optional platforms out of the generic contract.

### S2 — implementation or evidence collection

- For tasks 2.1–2.4, build the consumer fixture and fake effect sink: allow only a matching supported result for the exact subject/context; deny failed, missing, skipped, unavailable, unsupported-version, stale, and mismatched evidence before recording an effect.
- Also prove advisory mode retains uncertainty without authorization; agent-supplied tenant/tool context cannot override trusted context; evidence omits prompts, credentials, and unrelated content.
- For task 2.5, model an unintegrated entry point as unsupported. For 2.6, exercise allow/deny/unavailable/mismatch solely against the fake sink; make no external writes.

### S3 — independent qualification

- For 3.1, run strict OpenSpec validation and traceability on the proposed capability IDs.
- For 3.2, a separate audit session reviews contract scope and assertions, including the deny-before-effect ordering and unsupported-entry-point boundary.
- Stop if a test substitutes evaluator output for trusted consumer authority or implies coverage beyond the fixture.

### S4 — integration/closeout

- Lead reconciles findings and signs off the contract/test boundary; implementation, consumer rollout, and effect policy stay with their respective maintainers.
- Close only on validated fixture evidence and independent review. Broader adoption waits for each consumer owner’s own integration decision and proof.

## Bounded roles

- Lead: design/review/sign-off. Luna: author the contract notes and hermetic fixtures, collect test receipts. A distinct audit session validates the receipts independently.
- This contract is carrier-independent and changes no session-start/manifest interface; qualify its native consumer fixture, not the five-adapter matrix.
- No live service, private tenant, or effect target is used without the relevant consumer owner’s explicit scope decision.

## Sources

- [Proposal](proposal.md) · [Tasks](tasks.md) · [Design and ownership boundary](design.md)
- [Global sprint plan](../../SPRINTS.md)

Use the package’s native acceptance path. If the session interface changes, assign its carrier-specific work through the [five-adapter matrix](../../SPRINTS.md#session-adapter-matrix).
