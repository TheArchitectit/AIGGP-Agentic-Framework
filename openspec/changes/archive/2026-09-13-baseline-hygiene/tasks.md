# Tasks: baseline decontamination (dependency-ordered)

## Sprint 1 — stop the bleeding (H8)
- [ ] 1.1 log_failure.py: project-overlay default in submodule layout +
      --upstream flag + written-path output (D3)
- [ ] 1.2 Fixture: submodule layout appends to project overlay; --upstream
      writes baseline (D3)

## Sprint 2 — allowlist reset (H3)
- [ ] 2.1 Export current entries to docs/registry-exports/ (D2 pattern)
- [ ] 2.2 Reset bundled allowlist to empty scaffold (D1)
- [ ] 2.3 CHANGELOG migration note for the owning project (D1, Q1)

## Sprint 3 — registry split (H8)
- [ ] 3.1 Partition entries by affected_files ownership; move foreign
      entries to docs/registry-exports/ (D2)
- [ ] 3.2 failure_registry_check.py runs warning-free on clean checkout (D2)

## Sprint 4 — specs and leftovers (M8, L6)
- [ ] 4.1 Game specs + game-framework-README.md: remediate in place —
      add requirement IDs, reconcile referenced gates, rewrite the README
      to one-repo wording (no devgate-game-framework submodule pointer) (D4)
- [ ] 4.2 .gitignore: un-ignore Cargo.lock; move PREVENT-DIST-001 note (D6)

## Sprint 5 — regression gate (D5)
- [ ] 5.1 baseline_check.py: foreign-path entries fail (D5)
- [ ] 5.2 Wire into pre-commit docs + the repo's future CI (M9 handoff)

## Sprint 6 — closeout
- [ ] 6.1 Suite green; CHANGELOG; version bump per release gate
