# Sprint plan — GitLab forge support

**Scope:** preserve the supported GitLab option alongside GitHub; live adoption is optional.
Hermetic Sprints 1–3 and 5, plus the rebuilt fixture parity drill, are recorded complete.
No GitLab server was contacted; do not reopen those receipts as live proof.

## Sequence

### S1 — intake/baseline

- Confirm the 2026-11-15 and 2026-11-25 owner decisions, zero instance declarations, and current pinned-corpus result.
- Treat task “Sprint 0 (instance discovery)” as dormant. No operator has selected an instance.

### S2 — implementation or evidence collection (adoption-triggered)

- Only after an operator elects adoption, collect Sprint 0 inputs: base URL/alias, exact version, API and runner-registration auth shape, runner reachability/TLS, backup location and restore receipt, instance owner/patch cadence, and explicit hosted GitLab scope.
- On the same trigger, activate Sprint 4’s two-live-forge parity, “Two-live-forge parity (GLF-01 live half),” and “Backup restore drill … (GLF-10).” Keep secrets and private endpoint data outside git.
- Before adoption, no implementation work is needed; the existing local gate-backed parity test remains the acceptance evidence for the option.

### S3 — independent qualification

- After private operator evidence exists, a separate audit session checks version pin, declaration, restore validator result, two-forge finding parity, redaction, and that GitHub behavior is unchanged.
- Stop if access, trust, or restore evidence is missing; record NOT_RUN rather than infer a live pass from fixtures.

### S4 — integration/closeout

- Lead reconciles the private acceptance reference with `docs/GITLAB-FORGE.md`, deployment declaration, and the current task record; sign off only the scope actually exercised.
- If adoption is not selected, retain the dormant conditions and make no live-support claim.

## Bounded roles and acceptance

- Lead: own scope, design choices, independent-review reconciliation, and sign-off; operator: decide adoption and supply the private instance/restore inputs.
- Luna: maintain the hermetic receipt and, only after adoption, collect redacted operator evidence; a distinct auditor session verifies it without using Luna’s conclusions as proof.
- Acceptance: existing pinned five-case parity drill remains green; adoption additionally requires accepted restore evidence and two-live-forge parity. No calendar date is implied.

## Sources

- [Proposal](proposal.md) · [Tasks and owner decisions](tasks.md) · [Design](design.md)
- [Forge support tests](../../../tests/test_gitlab_forge_support.py) · [Deployment/parity fixtures](../../../tests/test_gitlab_forge_deployment.py)
- [GitLab forge guide](../../../docs/GITLAB-FORGE.md) · [Global sprint plan](../../SPRINTS.md)

Use the package’s native acceptance path. If the session interface changes, assign its carrier-specific work through the [five-adapter matrix](../../SPRINTS.md#session-adapter-matrix).
