# data-corruption sprint plan

Route acceptance to the **framework gate maintainer**. Bring a pinned repository and committed range, disposable corruption fixtures, and the authority-supplied detached review digest to intake. Use the [sprint dispatch guide](../../SPRINTS.md#dispatch-by-agent-type) and current [published specification](../../specs/data-corruption/spec.md).

## Roles

- Lead: establish the repository/range identity and acceptance boundary, reconcile the independent report, and own integration.
- Luna writer: maintain the detached exact-range consumer and focused fixtures in the selected implementation scope.
- Evidence collector: capture original bytes, authority digest, base/head/tree identity, full finding inventory, candidate SHA and exact test/job receipts.
- Independent auditor: in a separate session, recompute inventory and replay positive, stale, mismatch and self-approval rejection cases.
- Accountable owners: framework maintainer owns scanner behavior; external review authority owns review issuance; CI and release owners accept their own hosted and manifest receipts.

## S1 — baseline and scope

- Pin the published `fw-corruption-02` contract and the candidate source revision.
- Identify the exact committed range, canonical repository identity, target Git tree, complete substitution/mass-rewrite findings, detached review location and authority-provided digest.
- Keep the detached whole-range mode separate from the protected per-transition mode in the [active provisioning plan](../../changes/provision-exact-corruption-reviews/sprint-plan.md). The modes are mutually exclusive and never fall back to one another; ordinary callers remain strict.
- Exit when acceptance inputs, owners, evidence destination and independent gates are named.

## S2 — implementation and receipts

- Exercise an exact matching detached review and retain reviewed dispositions with the command result.
- Replay stale-clean, self-approval, changed tree/base, malformed digest/schema, symlink, arbitrary-range, wrong repository/run and unrelated-finding controls.
- Confirm stale or absent review input does not acknowledge findings: ordinary findings and unrelated content, staged, control-test and other gates keep their normal behavior. A clean range with a stale review follows the specified diagnostic behavior.
- Reconcile the changed-script checksum manifest and collected-suite floor against the final tracked tree; record the exact source, test and hosted job identities.

## S3 — independent qualification

- Auditor independently recomputes repository/range/tree identity and the complete finding inventory from pinned source inputs.
- Replay one positive match and the relevant refusal cases; inspect that consumer-controlled review data cannot authorize findings.
- Re-run applicable focused scanner, manifest, suite-floor, OpenSpec, traceability and regression checks at the audited tree. State every skipped gate as `NOT_RUN` with its blocker.
- Return a requirement-level verdict and list any missing authority, hosted or owner receipt.

## S4 — integration and handoff

- Lead reconciles the audit and verifies checks against the final tree. A matching digest and fixture result are evidence for the selected range only; they do not grant production authority or prove protected-CI rollout.
- Handoff candidate SHA, exact range/tree identity, authority digest provenance, full finding inventory, positive and negative receipts, manifest/suite-floor results, hosted job identity and owner decisions.
- Preserve the ordinary strict default and independent gates. Archive or reopen work only through the repository's OpenSpec lifecycle and evidence process.

## Acceptance

| ID | Contract | Key scenarios |
|---|---|---|
| [`fw-corruption-02`](../../specs/data-corruption/spec.md#requirement-range-findings-require-detached-exact-review) | Detached exact review can acknowledge only the complete matching committed range | exact match; consumer self-approval; range change; invalid authority; run/checkout or repository mismatch; unrelated blocking findings; clean range with stale review |

The [archived implementation package](../../changes/archive/2026-11-27-consume-detached-corruption-review/sprint-plan.md) records its task receipts. Its completion does not establish external authority issuance or production adoption.
