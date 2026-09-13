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

D4. **Game specs leave the framework.** The three openspec/specs/* game
    documents and scripts/game-framework-README.md move to the
    game-framework project (or a docs/attic note pointing there); the
    framework keeps a one-paragraph README note that game-specific gates
    (game_regression.py, scene_inventory.py) remain but their phase-matrix
    specs live with the game framework.

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

Q2. Keep the game *scripts* (game_regression.py, scene_inventory.py) in the
    framework or move them with the specs? Recommendation: keep — they are
    generic scanners for Godot projects; only the SoH-specific specs move.

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| A consumer relied on baseline allowlist coverage after a submodule bump | Medium | D1 export file + CHANGELOG migration note + overlay merge lands first (rule-enforcement-gaps) |
| Registry split breaks a consumer's fix_commit validation | Low | gate_overlay owner logic already attributes entries per source; exports are labeled non-enforced |
| Moving specs breaks inbound links | Low | Leave a README pointer at the old docs location |
