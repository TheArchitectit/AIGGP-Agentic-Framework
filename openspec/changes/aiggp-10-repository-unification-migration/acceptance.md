## Required acceptance fixtures

- Fixture A - ancestry: both selected cutover commits are ancestors of the unified migration commit.
- Fixture B - audit preservation: original audit tip resolves from the archival ref or verified mirror bundle.
- Fixture C - tag collision: same-name predecessor tags resolve distinctly and match the tag map.
- Fixture D - pure move: policy and DevGate move commits contain no normalized content changes.
- Fixture E - path matrix: policy-only, DevGate-only, schema-only, and cross-module changes run the intended nonempty job sets.
- Fixture F - negative control: every successor required check proves it can fail.
- Fixture G - golden corpus parity: standalone and unified paths agree on verdicts, findings, severity, and subject digest.
- Fixture H - generated-doc drift: edited guardrail output fails against the policy-bundle renderer.
- Fixture I - consumer matrix: each supported dependency route works through its declared compatibility path.
- Fixture J - release provenance: candidate manifest names both predecessor commits and all required digests.
- Fixture K - old URL: archived notice and exact canonical link are visible and working.
- Fixture L - rollback: repository settings, required checks, write routes, and post-cutover commits survive a rehearsed rollback.

## Release acceptance criteria

- AIGGP-01 completed on a named DevGate cutover commit with no unresolved P0 false-green finding.
- History manifest and mirror checksums reviewed; all declared refs reachable.
- New CI passed all positive fixtures and failed all negative controls from a fresh clone.
- Golden corpus equivalence holds; no skipped-all or zero-test green.
- All required consumers pass or have explicit owner-approved breaking migrations.
- First unified release candidate has complete provenance and no tag collision.
- Rollback rehearsals pass at the required states.
- No open P0/P1 migration defect at archive approval.
- Archive notices and canonical links verified visually and functionally.

## Open owner decisions before implementation

- Exact hosting repository names and whether the Agent Guardrails repository is renamed at cutover or after stabilization.
- Freeze and stabilization window lengths.
- Which consumer routes receive compatibility shims and their expiry dates.
- Unified release namespace and first version number.
- Whether predecessor issue trackers stay open for historical discussion or are locked after archive.

## Handoff

Start with inventory and mirror bundles, not file moves. Finish AIGGP-01 and name the DevGate cutover commit. Rehearse the exact migration in disposable mirrors until history, CI, tag, consumer, release, and rollback fixtures all pass. At cutover, replay the rehearsed process from frozen heads; do not improvise or combine behavior changes with moves. Do not archive either predecessor until the unified path has survived stabilization. No repository changes are authorized by this document.
