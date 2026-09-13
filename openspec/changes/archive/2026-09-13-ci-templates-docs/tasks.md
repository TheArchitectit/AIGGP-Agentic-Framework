# Tasks: CI templates, repo CI, docs (dependency-ordered)

## Sprint 1 — self-clean (unblocks D3)
- [ ] 1.1 Resolve the PREVENT-024 self-hit (scoped allow or retune) (D6)
- [ ] 1.2 Align file-size and .env-suffix semantics (D6)

## Sprint 2 — framework CI (M9)
- [ ] 2.1 .github/workflows/ci.yml per D3 with fetch-depth: 0
- [ ] 2.2 Mark required on main; verify a test PR runs it

## Sprint 3 — drift template (H2)
- [ ] 3.1 fetch-depth: 0 on both checkouts (D1)
- [ ] 3.2 Conditional typescript@5 install + SKIPPED state in the table (D1)
- [ ] 3.3 Fixture consumer run: four gates report green (D1)

## Sprint 4 — compliance template (M4)
- [ ] 4.1 Exact-basename forbidden matching with explicit .env.* allows (D2)
- [ ] 4.2 Per-commit body iteration without tr-shredding (D2)

## Sprint 5 — version + docs (M7, M10)
- [ ] 5.1 VERSION → 1.2.0; reconstructed CHANGELOG sections (D4)
- [ ] 5.2 AGENTS.md overlay rewrite + rule-count fix (D5)
- [ ] 5.3 README rule counts and tree listing sync (D5)

## Sprint 6 — closeout
- [ ] 6.1 Suite + new CI green; CHANGELOG; version bump per release gate
