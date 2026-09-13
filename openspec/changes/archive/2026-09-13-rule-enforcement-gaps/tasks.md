# Tasks: rule-enforcement gaps (dependency-ordered)

## Sprint 1 — semantic ruleset honesty (H1)
- [ ] 1.1 Implement SEMANTIC-005 useEffect dependency check (D1, Q1)
- [ ] 1.2 Flip unimplemented rules to enabled:false + not-implemented
      annotation; file one tracking issue per rule (D1)
- [ ] 1.3 Rules-hygiene check: enabled-without-checker fails (D7)

## Sprint 2 — extracted-rules removal (M1)
- [ ] 2.1 Delete extracted-rules.json; add docs mapping each rule to its
      skill template (D2)
- [ ] 2.2 Update README tree listing and any rule-count references (D2)

## Sprint 3 — language-aware spec markers (H6)
- [ ] 3.1 spec_traceability.py: per-extension comment syntax (D3)
- [ ] 3.2 findings_to_spec.py: emit marker hint in the file's own syntax (D3)
- [ ] 3.3 Fixture: `# spec:` in .py satisfies blocking mode

## Sprint 4 — silent-success overlay (M2, M3)
- [ ] 4.1 Overlay merge for rules + allowlist via gate_overlay semantics (D4)
- [ ] 4.2 Honor .guardrailsignore in the scan (D4)
- [ ] 4.3 Flip shipped families to enabled:false (D6)
- [ ] 4.4 Fixture: project overlay allowlist entry covers project hit

## Sprint 5 — schema config file (M2)
- [ ] 5.1 schema-contract.json reader + example file (D5)
- [ ] 5.2 Locally-modified-script detection with migration message (D5 risk)
- [ ] 5.3 AGENTS.md database section rewrite (handoff to ci-templates-docs)

## Sprint 6 — closeout
- [ ] 6.1 Suite green; CHANGELOG; version bump per release gate
