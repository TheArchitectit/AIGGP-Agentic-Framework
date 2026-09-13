# Design: rule-enforcement gap closure

## Locked decisions

D1. **Semantic rules: implement SEMANTIC-005 now; disable-and-ticket the
    rest.** SEMANTIC-005 (React useEffect missing deps) is documented in the
    README and the script header, so it is implemented in this change using
    the TypeScript AST already loaded. SEMANTIC-002/003/004/006/007/008/009/
    010 are flipped to `enabled:false` with a `status: "not-implemented"`
    annotation and one tracking issue per rule; the scanner is taught to
    *fail the hygiene gate* (below) if an enabled rule has no implementation,
    so the gap cannot silently reopen. Rules are re-enabled individually as
    checkers land in later changes.

D2. **extracted-rules.json: remove from the framework, point to skills.**
    The 10 behavior rules move to a docs section naming the skill template
    that covers each (four-laws, commit-validator, scope-validator); the JSON
    file is deleted and README's tree listing updated. File-scanning gates
    cannot enforce "no force push" and pretending otherwise is the same
    dead-config class as H1.

D3. **Spec markers are language-aware.** spec_traceability.py accepts
    `// spec: <id>`, `# spec: <id>`, and `-- spec: <id>` (SQL/Lua), matched
    per file extension; findings_to_spec.py emits the marker hint in the
    implementing file's own comment syntax. Blocking mode then works for
    Python, Rust, JS/TS, and Go alike.

D4. **silent-success-scan joins the overlay contract.** Rules and allowlist
    resolve through gate_overlay.py semantics: bundled baseline merged with
    `<project>/.guardrails/` overlay (overlay wins on family/file id), and
    the scan honors `.guardrailsignore`. The shipped baseline allowlist
    shrinks to DevGate's own tree only (coordinated with
    2026-09-13-baseline-hygiene, which owns the allowlist cleanup).

D5. **schema-health-check.mjs reads external configuration.** A
    `<project>/.guardrails/schema-contract.json` (adapter, expected columns,
    connection env var name) replaces edit-the-script configuration; the
    shipped default stays `"none"` and the file ships only as an example.
    AGENTS.md's database section is rewritten to point at the file
    (coordinated with 2026-09-13-ci-templates-docs, which owns AGENTS.md).

D6. **Shipped data matches the documented default.** The two enabled
    silent-success families flip to `enabled:false`; enabling stays a
    documented per-project overlay action.

D7. **A rules-hygiene check keeps this closed.** failure_registry_check.py
    (or a new rules_check.py) verifies: every enabled rule in
    semantic-rules.json has a registered checker; every rules file parses
    against pattern-rules.schema.json; no enabled rule lacks a message and
    severity. Wired into the repo's own pre-commit once M9 (CI for the
    framework repo) exists.

## Open questions

Q1. SEMANTIC-005 dependency-array analysis has known false-positive classes
    (stable refs, custom hooks). Ship it warning-severity (as the JSON has
    it) with `guardrails-allow` as the escape, or hold it to a later change?
    Recommendation: ship at warning, matching the file.

Q2. Should schema-contract.json live at `.guardrails/` (config) or
    `openspec/` (spec)? Recommendation: `.guardrails/` — it is gate
    configuration, not a capability spec.

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Disabling 8 semantic rules reads as lost coverage | Medium | The coverage never existed; CHANGELOG frames it as honesty + per-rule re-enable path |
| Consumers already hand-edited schema-health-check.mjs in their submodule | Medium | D5 detects a locally-modified script (non-"none" adapter with no config file) and fails with migration instructions instead of silently changing behavior |
| Marker regex widening matches strings in docs | Low | Markers are still only collected from source extensions in SCAN_EXTS |
