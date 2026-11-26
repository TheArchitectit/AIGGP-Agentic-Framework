# Tasks

## 1. Specify the boundary

- [ ] 1.1 Review the published evidence, decision, context, policy, and integration contracts; keep the proposal additive and avoid new wire formats.
- [ ] 1.2 Define consumer responsibilities for trusted context, immutable subject/provenance binding, advisory versus mandatory handling, bounded coverage claims, and effect authorization.
- [ ] 1.3 Map the generic contract to a hermetic consumer fixture without naming a private deployment or requiring an optional platform.

## 2. Verify acceptance behavior

- [ ] 2.1 Prove a consumer can authorize a fixture effect only after validating a matching supported result for the exact subject and trusted context.
- [ ] 2.2 Prove mandatory mode denies failed, missing, skipped, unavailable, unsupported-version, stale, or mismatched evidence before an effect is recorded.
- [ ] 2.3 Prove advisory mode preserves uncertainty/findings and never yields an evaluator-issued authorization.
- [ ] 2.4 Prove agent-supplied tenant/tool context cannot replace trusted consumer context, and evidence contains no raw prompt, credential, or unrelated content.
- [ ] 2.5 Exercise an unintegrated entry point as unsupported and verify no universal interception claim is emitted.
- [ ] 2.6 Run allow, deny, unavailable, and mismatch controls against a fake effect sink; verify no external system is written.

## 3. Review and disposition

- [ ] 3.1 Run strict OpenSpec validation and traceability for the proposal and its new capability IDs.
- [ ] 3.2 Obtain independent review of the contract boundary and evidence tests; keep implementation, consumer rollout, and authorization policy owned by their respective maintainers.