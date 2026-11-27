# Sprint plan — DG-02 package, release, and rule gaps

Use the [sprint dispatch guide](../../SPRINTS.md) with this package’s [tasks](tasks.md), [proposal](proposal.md), and [batch 008 review](../dg-02-evidence-ledger-reconciliation/batches/batch-008/README.md).

Exercise the native entry point for this change. A change to session startup or manifest handling also needs a carrier-specific receipt. [Session adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Roles

- Lead: prioritize requirements and review acceptance boundaries; sign off on evidence/state proposals.
- Luna: implement isolated fixtures and collect package, registry, deploy, and rule receipts.
- Independent auditor: separate session reviews source, tests, no-publish controls, digests, and bundle validation.
- Accountable owners: package service maintainer, release/registry owner, deploy-gate maintainer, rule owners, and DG-02 evidence owner.

## S1 — intake and baseline

- Use batch 008 findings as leads: unresolved package closure/classification, upload retry ambiguity, short overlay commit checks, targeting, and rule coverage.
- Map tasks 1.1–1.5 to `coh-pkg-01..05`; tasks 2.1–2.5 to `rel-upload-01`, `rel-artifact-01`, `rel-fixcommit-01`, `rel-target-01`, `rel-audit-01`; tasks 3.1–3.3 to rule/evidence proof.
- Pin expected package/digest inputs, fake registry boundary, owner repository availability, and deploy entry point; do not use real registries or publish artifacts.
- Exit when fixtures are isolated and every test maps to an existing requirement and observable result.

## S2 — implementation and evidence

- Tasks 1.1–1.5: test service-entry missing/moving/digest cases, duplicate IDs/references/cycles, normative vs archive digests, full frozen import closure, and inventory approval invalidation.
- Tasks 2.1–2.5: fake-registry upload/build/partial-result cases; empty/missing artifact refusals; owner-history resolution for bundled/overlay commits; deploy targeting without publishing; HIGH vs advisory pre-commit exits.
- Tasks 3.1–3.2: fail on enabled semantic rules with no checker and verify complete shipped-rule coverage; map prior behavior rules to skill templates.
- Task 3.3: bind only supported historical claims to accepted row-specific bundles and expected digests.
- Exit with deterministic outcomes, explicit limits for ambiguous remote state, and no external publication.

## S3 — independent qualification

- Auditor reruns named defensive tests, verifies fixture isolation and expected/actual digest reporting, and inspects rule-to-checker/template completeness.
- Auditor checks commit identities against the owning repository where available and marks unavailable history NOT_RUN/rejected rather than assuming validity.
- Auditor validates each bundle and its row binding; lead reconciles any change to an existing contract before state-gate submission.

## S4 — integration and closeout

- Run relevant package, release, registry, and rule suites plus strict OpenSpec, traceability, evidence validation, and state gate at final head.
- Handoff: fixture inventory, test receipt, repository-history findings, fake-registry outputs, rule mapping, per-row digests, auditor verdict, and external limitations.
- No real publish, registry mutation, or requirement closure without the separate owner authorization and accepted evidence.
