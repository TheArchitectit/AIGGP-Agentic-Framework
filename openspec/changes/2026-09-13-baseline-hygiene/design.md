# Design: baseline decontamination

## Locked decisions

D1. **Allowlist: reset to empty scaffold.** silent-success-allowlist.json
    becomes `{"entries": []}` with a header comment pointing at the overlay
    contract. The 1,726 entries belong to a consuming project (paths match
    its layout); the migration note in the CHANGELOG tells that project to
    re-home them into its own `.guardrails/silent-success-allowlist.json`,
    which the overlay merge (rule-enforcement-gaps D4) then honors.

D2. **Registry: split by ownership.** Entries whose affected_files are not
    in this repo move to a new `docs/registry-exports/<project>.jsonl`
    archive (kept for provenance, clearly labeled non-enforced), and the
    bundled registry keeps only entries against this tree. The merge
    semantics in gate_overlay.py are unchanged — this is data placement.

D3. **log_failure.py defaults to the owner's side.** In a submodule layout
    (`<project>/.devgate/`), the default append target is
    `<project>/.guardrails/failure-registry.jsonl`; `--upstream` is required
    to write the baseline, and the command prints which file it wrote.
    Standalone behavior is unchanged.

D4. **Game specs and gates stay in the framework — one DevGate, not
    two.** Owner decision (Roger, 2026-09-13): game development is NOT
    moving out of this repository. The three openspec/specs/* game
    documents, the game gates (game_regression.py, scene_inventory.py),
    and scripts/game-framework-README.md all remain here and are brought
    up to framework standard in place: add `<!-- id: … -->` requirement
    IDs so spec_traceability.py covers the game specs (no more 0/0
    capabilities), reconcile the gates the specs reference (implement or
    mark planned), and rewrite game-framework-README.md so it documents
    the game tooling as part of THIS framework — it must no longer tell
    readers to submodule a separate devgate-game-framework repo.

D5. **A baseline-hygiene gate prevents re-contamination.** A small script
    (folded into failure_registry_check.py or new baseline_check.py) fails
    when: any bundled registry/allowlist entry references a path absent from
    this repo; any bundled spec lacks requirement IDs traceable by
    spec_traceability.py; log_failure's default target is the baseline in a
    submodule layout. Wired into the repo's own CI once M9 lands; runnable
    standalone immediately.

D6. **.gitignore corrected.** `Cargo.lock` un-ignored (binaries are the
    common consumer); the PREVENT-DIST-001 comment moves to the
    commit-validator skill where behavior rules belong (coordinated with
    rule-enforcement-gaps D2).

## Open questions

Q1. Which consuming project owns the 1,726 allowlist entries, and does it
    still need them? The audit can name candidate repos from the paths
    (Go service layout) but cannot verify current need; the export file (D2
    pattern) preserves them regardless. Owner confirms before their next
    submodule bump.

Q2. RESOLVED (owner, 2026-09-13): keep BOTH the game *scripts*
    (game_regression.py, scene_inventory.py) and the game *specs* in this
    repo. Game dev is not moving out — one DevGate, not two. D4 amended
    from extraction to in-place remediation accordingly.

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| A consumer relied on baseline allowlist coverage after a submodule bump | Medium | D1 export file + CHANGELOG migration note + overlay merge lands first (rule-enforcement-gaps) |
| Registry split breaks a consumer's fix_commit validation | Low | gate_overlay owner logic already attributes entries per source; exports are labeled non-enforced |
| Bundled game specs drift from what consuming game projects rely on while remediated in place | Low | Specs stay in exactly one place (this repo); consumers track the submodule, no second copy is created |
