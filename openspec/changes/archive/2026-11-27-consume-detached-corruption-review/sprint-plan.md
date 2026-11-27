# Sprint plan — consume detached corruption range reviews

Use the [sprint dispatch guide](../../../SPRINTS.md) with this archived package's [tasks](tasks.md), [proposal](proposal.md), and recorded deltas for [data-corruption](specs/data-corruption/spec.md), [framework-ci](specs/framework-ci/spec.md), and [release-checksum-manifest](specs/release-checksum-manifest/spec.md). Current requirement routing lives in the published [data-corruption](../../../specs/data-corruption/spec.md), [framework-ci](../../../specs/framework-ci/spec.md), and [release-checksum-manifest](../../../specs/release-checksum-manifest/spec.md) specifications.

## Roles

- Lead: scope the exact candidate range, reconcile evidence and own integration.
- Luna writer: maintain the detached-review consumer and focused fixtures within the selected implementation tasks.
- Evidence collector: pin the checkout, base, tree and authority-supplied digest; retain positive and negative-control receipts.
- Independent auditor: in a separate session, recompute the finding inventory and replay match, stale-clean, self-approval and mismatch cases.
- Accountable owners: framework maintainer owns scanner behavior; the external review authority owns review issuance and digest; release and CI owners accept their respective manifest and suite-floor evidence.

## Operating boundary

This package's explicit detached range mode and the [active protected-transition mode](../../provision-exact-corruption-reviews/sprint-plan.md) are independent, mutually exclusive trusted alternatives. Do not chain them or fall back from one to the other. Existing callers remain strict. A configured detached review that is stale or otherwise mismatched cannot acknowledge findings; ordinary findings and other gates apply. A clean range with a stale review may pass with the specified diagnostic. Consumer-controlled files and options do not supply authority. Neither mode grants production authority or constitutes a live CI rollout.

## S1 — baseline and acceptance boundary

- Pin the candidate source and current base; record the exact committed `BASE..HEAD`, repository identity, target tree and complete substitution/mass-rewrite inventory expected by the delta.
- Map tasks 1–12 to the detached consumer, backward-compatible caller behavior, negative controls, checksum inventory, test-suite-floor inventory and regenerated OpenSpec index. Task 11 records native Specs index drift at `d58fe65618ba4a610bd0d8bfc888371c68c3fb57` ([hosted run](https://github.com/TheArchitectit/AIGGP-Agentic-Framework/actions/runs/46072712751/job/140753197852)) and the subsequent `python3 scripts/spec_index.py --write` followed by `--check`, which passed. Task 12 records reconciliation at current main `e302beed6c23bcc1580e285a980a32d36d543489`: 162 tracked script checksum entries and 148 collected suites / 2,167 tests, including `test_corruption_review` floor 11 and `test_spec_catalog` floor 5, with checksum, index and suite-floor verification. Retain both exact receipts and verify applicability to the final candidate. Confirm current task checkboxes against the delivered candidate; do not use this plan to change them.
- Identify the independent review authority and the owner of each required CI/release receipt. Keep any missing hosted or production-control evidence explicit.
- Exit when the range identity, accepted digest source, inventory definition and blocking independent gates are fixed.

## S2 — implementation and candidate evidence

- Exercise the explicit detached-review path with externally supplied digest and the exact repository, base, target tree and full finding inventory. Retain the emitted reviewed disposition and command result.
- Reproduce the task-listed stale-clean, self-approval, changed-tree/base, malformed digest/schema, symlink and arbitrary-range controls. Confirm a stale or nonmatching receipt does not suppress ordinary findings and that unrelated/content/staged/control-test checks remain active.
- Reconcile `CHECKSUMS.sha256` against the final tracked script tree and `tests/expected-counts.json` against collected suites. Preserve the exact candidate SHA and gate output; a local result does not establish hosted acceptance.
- Exit with candidate artifacts and unresolved evidence clearly listed; no production-use claim.

## S3 — independent qualification

- Auditor independently verifies the pinned source, repository/range/tree identity, authority digest and complete finding inventory from original inputs.
- Replay one positive exact match and the failure controls from S2. Verify no consumer-controlled review can authorize findings and no fallback between trusted modes occurs.
- Re-run applicable manifest, suite-floor, focused scanner, strict OpenSpec, traceability and regression checks at the audited tree. Record any skipped check as `NOT_RUN` with the blocker.
- Return a verdict per requirement and applicable gate; stale, incomplete or absent authority remains unaccepted.

## S4 — integration and handoff

- Lead reconciles the independent report and confirms exact checks at the final tree. Update package tasks only for evidence actually accepted and treat tasks 11 and 12 as receipts for their named revisions. Regenerate and verify the index, checksums and suite floors at the integration commit.
- Handoff the candidate SHA, range and tree identities, digest source, complete finding inventory, positive and rejection receipts, manifest and suite-floor receipts, App check links, native jobs and runner identities, auditor verdict and remaining owner decisions.
- Keep external authority issuance, protected CI adoption and production use pending until their owners accept them. The archived package is historical input for the published capability plan; any reopened implementation work needs a new package and fresh receipts.
