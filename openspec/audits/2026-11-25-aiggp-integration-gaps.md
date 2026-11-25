# AIGGP integration and rollout evidence review

Review baseline: AIGGP `main` `fd2c11f08aa74f8b1f4917a7a5c2785860ef4cf1`. This review branch is based at the same commit. Scope covers implementation and cross-repository deployment evidence, excluding the exhaustive OpenSpec inventory. No production code, live GitLab instance, remote, or credentials were changed or contacted.

## Confirmed implementation and packaging gaps

### DG-08 — reusable GitHub workflow bootstrap

`docs/SUBMODULE_WIRING.md:10-16` prohibits committed `.gitmodules` registration; `:122-124` says CI must clone `.devgate/` before gates, pinned to a SHA for reproducibility. The reusable `templates/github-workflows/drift-scan.yml:21-23,49-53` instead says the checkout may be a submodule and uses `submodules: true`; it has no explicit clone/bootstrap. It invokes `.devgate/scripts/...` at lines 59 and 136-139. The AIGGP-owned `.github/workflows/drift-scan.yml:51-56` demonstrates clone to in-tree `.devgate/` plus checkout of a full SHA (`8c2d0a9c680309bd90e6be7d5d43dd21e948fc20`). The clean copy-in consumer without `.gitmodules` will not provision the required scripts. `PREVENT-SUB-001` in `.guardrails/prevention-rules/pattern-rules.json` prohibits `.gitmodules` entries naming AIGGP or the template repo. DG-08 covers the reusable GitHub drift workflow, preflight, and wiring docs; the consumer owns the reviewed immutable SHA.

### DG-11 — GitLab mirror checkout bootstrap

The GitLab drift mirror has a separate setup mismatch. `templates/gitlab-ci/drift-scan.gitlab-ci.yml:15-22` enables `GIT_SUBMODULE_STRATEGY: recursive`, defaults commands to `${DEVGATE_DIR:-.devgate}`, and contains no bootstrap step. Recursive submodule checkout only initializes registered submodules, while the consumer contract disallows registering `.devgate`. A fresh consumer following the contract reaches gate commands without required scripts. DG-11 separately covers GitLab include/mirror execution and variables: consumer-owned full SHA, ignored in-tree checkout, script/root preflight, and hermetic clean-project validation. No live GitLab instance is required for this validation.

### DG-09 — GitLab runner live monitoring, conditional on adoption

`hub/monitor.py:1-6,80-86` declares and constructs a GitHub API polling client. `scripts/runner-enroll.sh:207,230` accepts a forge selection and validates a GitLab runner image, so metadata can identify a GitLab runner; there is no GitLab API polling path in the hub monitor. `hub/forge/monitor.py:4-12` explicitly limits itself to declaration/recorded evidence and says live TLS/version/backup probing is not implemented. `docs/GITLAB-FORGE.md:3-7,31-40` states no live instance has been contacted and live monitoring is not implemented. The owner decision in `openspec/changes/add-gitlab-forge-support/tasks.md:17-30` makes live proof dormant until adoption. Preserve that decision: no live server or acceptance proof is required absent an operator adoption declaration. After adoption, GitLab runner status must use the declared GitLab API or be marked unverified, never inferred from GitHub responses.

### DG-10 — GitLab runner image source provenance

All ten `templates/gitlab-ci/*.yml` use `ghcr.io/aiggp/devgate-runner@sha256:4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b`. `tests/test_gitlab_forge_support.py:39-42` verifies mirror count and digest-pin syntax; `hub/forge/instance.py:173-198` checks GitHub template names have GitLab mirrors with digest-pinned images. It does not map a digest to reviewed source/build provenance. A repository-wide search found no matching image build definition or release workflow outside the mirror references. This offline review did not query the registry; it does not claim the image is absent or unsafe. The actionable gap is repository reviewability: consumers cannot trace the pinned bytes to source, build workflow, or build permissions here. DG-10 calls for reviewed provenance and an offline consistency check; artifact authenticity still requires signature/attestation verification against an approved trust root.

## Existing coverage and maturity boundaries

- `openspec/changes/add-gitlab-forge-support/tasks.md` records fixture support and the 2026-11-15 decision that GitLab is optional; live instance discovery, two-live-forge parity, backup restore, and live monitoring are dormant until an operator adopts GitLab. The package should retain these boundaries, not duplicate its work.
- `python3 scripts/forge_parity_drill.py` was executed from AIGGP HEAD: five cases produced the expected fail/fail/fail/fail/pass results, both adapter paths had identical findings, and the command exited 0. It proves fixture/adapter-level parity, not two live CI platforms.
- GitLab configuration is fail-closed: `hub/forge/instances.toml` declares zero instances; `docs/GITLAB-FORGE.md` requires an operator declaration and keeps GitLab.com opt-in.
- `docs/SUBMODULE_WIRING.md:3-8,46-80` fixes the `.devgate/` path and requires consumer overlays to name vendored trees. Root and overlay behavior has dedicated tests (`tests/test_python_root_anchor.py`, `tests/test_scanner_root_anchor.mjs`, `tests/test_gate_overlay.py`).
- `openspec/changes/harden-template-runner-portability/tasks.md:18-36` records fixes for a rootless gitleaks install and GitHub YAML flow-list runner labels. Tests exist for the step bodies and fixtures; its `tasks.md:38-41` leaves post-fix consumer runner execution unchecked. This is rollout evidence to gather on the selected runner, not a newly reproduced defect. Do not duplicate that package.

## Cross-repository deployment boundary

Template repository `.devgate` pin/CI behavior is separate from AIGGP reusable workflow behavior; assess it under the template's own contract. Do not apply AIGGP's `PREVENT-SUB-001` to another repository without reviewing that product's explicit integration model. For bank rollout, keep consumer identities, topology, endpoints, credentials, approvals, and live run artifacts in approved operator systems; publish only revision, outcome, and a stable redacted reference.

## Routed implementation packages

All task checkboxes remain unchecked pending implementation and independent review:

- [DG-08: GitHub consumer bootstrap](../changes/dg08-consumer-workflow-bootstrap/proposal.md)
- [DG-09: conditional GitLab runner monitoring](../changes/dg09-gitlab-runner-live-monitoring/proposal.md)
- [DG-10: GitLab runner image provenance](../changes/dg10-gitlab-runner-image-provenance/proposal.md)
- [DG-11: GitLab mirror bootstrap](../changes/dg11-gitlab-mirror-bootstrap/proposal.md)
