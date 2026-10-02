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

### Q14.1 — Exact hosting repository names + rename timing

**ANSWERED 2026-10-01 (owner).**

**Keep `AIGGP-Agentic-Framework` as the unified name (option C) — no
rename at cutover, no rename after stabilization.** DevGate merges into
the existing AIGGP repo; Agent Guardrails' standalone repo is archived
as a read-only stub. Simplest, no name-churn, and matches the
proposal's "it does not redesign module internals merely because files
move" — a rename is a move with no behavior change.

Rejected: rename-at-cutover (A) — an extra surface of path-reference
rewrites in an already-heavy migration. Rename-after-stabilization (B)
— same churn deferred, and the handoff's "do not improvise or combine
behavior changes with moves" argues against adding another move
post-cutover.

### Q14.2 — Freeze and stabilization window lengths

**ANSWERED 2026-10-01 (owner).**

**Client-chosen, STS or LTS.** The freeze and stabilization windows are
not a single product decision — different clients (personal, business,
enterprise, same tier-scaled shape as aiggp-05 Q9.2 and aiggp-07 Q11.1)
have different tolerances for rollback exposure. The bundle declares
which profile a given deployment runs:

- **STS** (short-term): short freeze (e.g. 24-48h), short stabilization
  (e.g. 14 days). Faster closure, less rollback exposure for solo /
  low-consumer deployments.
- **LTS** (long-term): longer freeze (e.g. 7 days), longer stabilization
  (e.g. 90 days). Safer for slow-moving consumers, enterprise
  rollouts.

The migration machinery itself must honor either profile — the
proposal's rollback fixture ("A rehearsed rollback can restore the
pre-cutover repositories and required checks before the point of no
return") is scoped per-profile: STS has a shorter rollback window, LTS
a longer one, and the point of no return is defined by the chosen
profile's stabilization window, not a hardcoded number.

### Q14.3 — Which consumer routes receive compatibility shims + expiry

**ANSWERED 2026-10-01 (owner).**

**All four routes, expiry 90 days post-cutover (option A).** Submodules,
reusable workflows, package paths, and pinned action references each
get a compatibility shim. The proposal explicitly says "It does not
remove compatibility shims before their declared window ends" — shims
are expected, and the 90-day window matches a typical LTS stabilization
window plus grace. Which routes a given consumer actually uses is
their call (same opt-in shape as elsewhere) — the shim exists for all
four whether or not a consumer needs all four.

### Q14.4 — Unified release namespace + first version number

**ANSWERED 2026-10-01 (owner).**

**Fresh namespace, first version `1.0.0` (option A).** The first
unified release declares both predecessor baselines in its release
manifest (proposal: "the first unified release declares both
predecessor baselines"). Clean break from both predecessors' version
schemes — no ambiguity about which history a version number names.

### Q14.5 — Predecessor issue trackers: stay open or lock after archive

**ANSWERED 2026-10-01 (owner).**

**There are none to manage.** Neither predecessor repository has an
active issue tracker to migrate or lock — the ";p" answer is
operative: no predecessor issue-tracker work is in scope. If either
predecessor's tracker is discovered non-empty at cutover, the proposal's
"divergent writes" P0 risk applies and the tracker is archived read-only
per the standard archive posture (old repo URLs remain readable,
clearly archived).

## Handoff

Start with inventory and mirror bundles, not file moves. Finish AIGGP-01 and name the DevGate cutover commit. Rehearse the exact migration in disposable mirrors until history, CI, tag, consumer, release, and rollback fixtures all pass. At cutover, replay the rehearsed process from frozen heads; do not improvise or combine behavior changes with moves. Do not archive either predecessor until the unified path has survived stabilization. No repository changes are authorized by this document.
