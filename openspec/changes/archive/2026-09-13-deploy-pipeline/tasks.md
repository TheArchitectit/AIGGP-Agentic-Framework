# Tasks: deploy pipeline repairs (dependency-ordered)

## Sprint 1 — audit gate targets the project (C7)
- [ ] 1.1 Add DEVGATE_PROJECT_ROOT support to regression_check.py (D1)
- [ ] 1.2 deploy.sh: export it and run gates from "$PROJECT_ROOT" (D1)
- [ ] 1.3 Fixture: consumer with a planted critical violation → deploy gate
      reports the consumer's file, exits 1 before any publish step

## Sprint 2 — npm audit classification (C6)
- [ ] 2.1 Rewrite is_runtime per D2 (isDirect + dependencies + effects)
- [ ] 2.2 Fixture: direct-dep HIGH blocks; dev-only HIGH warns (D2)
- [ ] 2.3 Re-run the audit's live lodash case; record output in CHANGELOG

## Sprint 3 — publish leg safety (H7)
- [ ] 3.1 Replace PyPI line with build-once/upload-once per D3
- [ ] 3.2 Shell dry-run harness: success path uploads once; failure aborts
      pre-publish (D3)
- [ ] 3.3 Audit npm/cargo legs for the same precedence class; fix if present

## Sprint 4 — honest stage severities (M5, M6)
- [ ] 4.1 Schema health: strict-when-configured + documented escape (D4, Q2)
- [ ] 4.2 Lint/clippy relabeled or blocking per D4; RELEASE_GATE.md updated
- [ ] 4.3 Artifact verify: empty must_contain = config error (D5)

## Sprint 5 — registry validation (L8)
- [ ] 5.1 failure_registry_check.py: verify abbreviated SHAs (D6)
- [ ] 5.2 Test: short-SHA entry resolves; bogus short SHA errors

## Sprint 6 — closeout
- [ ] 6.1 Full suite green; CHANGELOG; version bump per release gate
