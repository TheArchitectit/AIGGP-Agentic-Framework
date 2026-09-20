## Phase 0 - inventory and freeze design

- Capture repository URLs, default branches, current heads, protections, rulesets, tags, releases, artifacts, packages, images, webhooks, environments, secret names/classes, deploy keys, submodules, open branches, and automation callers.
- Build the consumer map and required-check map.
- Define cutover freeze length, stabilization length, owners, incident channel, and point-of-no-return approval.
- Produce signed mirror bundles of both repositories and checksum them.

## Phase 1 - finish predecessor truth

- Complete AIGGP-01 on DevGate; name the verified cutover commit and finding ledger.
- Preserve the original audit tip in the history manifest and archival ref plan.
- Freeze the AIGGP-00 contracts needed by both modules: verdicts, envelope, bundle digest, waiver, ledger, subject identity.
- Re-run predecessor suites and negative controls at both selected cutover heads.

## Phase 2 - rehearse in disposable mirrors

- Create a migration branch from the Agent Guardrails cutover head.
- Isolate the policy pure-move commit into modules/policy.
- Add DevGate with a non-squashed subtree merge into modules/devgate.
- Add kernel, schemas, bundles, conformance, integrations, docs/generated, and tools/migration boundaries without implementing unrelated features.
- Import and verify namespaced tags and archival refs.
- Run object reachability, pure-move, tag-map, and fresh-clone tests.

## Phase 3 - rewire and dual-prove CI

- Port required checks with stable mappings and explicit path filters.
- Re-bind environments and least-privilege secret classes.
- Run positive fixtures and negative controls for every successor check.
- Run standalone and unified paths over the same corpus; compare verdict and evidence outputs.
- Test fork/PR trust boundaries, protected environments, release dry runs, and failure reporting.

## Phase 4 - consumer and release continuity

- Exercise fixtures for submodule, reusable workflow/action, package, container, CLI, and generated bundle consumers that remain supported.
- Publish the migration guide and compatibility schedule.
- Build the first unified release candidate with predecessor manifest and provenance, but do not publish.
- Test old URL behavior, provider redirects if renamed, package/image mappings, and archived-repository notices.

## Phase 5 - cutover

- Enter FROZEN; record heads and provider configuration again and compare with inventory.
- Repeat the rehearsed import from the frozen heads; do not hand-edit the result.
- Verify history manifest, tag map, CI negative controls, corpus equivalence, and release candidate.
- Switch branch protection and canonical automation only after all successor checks are present and required.
- Mark the unified repository CANONICAL and old repositories as migration-frozen, not archived.

## Phase 6 - stabilize, release, archive

- Monitor divergence, consumer failures, required-check execution, evidence parity, and release provenance through the stabilization window.
- Rehearse rollback one final time before publishing the first unified release.
- Publish only with owner approval and complete provenance.
- When acceptance holds, archive standalone repositories with notices and retain mirror bundles.
- Freeze tools/migration artifacts as the permanent migration record; remove one-time credentials and revoke obsolete tokens.
