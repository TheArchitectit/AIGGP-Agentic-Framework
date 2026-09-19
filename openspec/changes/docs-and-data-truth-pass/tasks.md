# Tasks: docs-and-data-truth-pass

- [x] 1 README: tree reflects the full repo; new "Spec Coherence Service"
      section (what/why, request→result flow, container execution, exit-code
      table pointer); hub monitor section (exists in CHANGELOG, not README).
- [x] 2 Rule-count truth: derive "N rules" from the file at write time or a
      CI check comparing prose numbers to `jq '.rules | length'`.
- [x] 3 README/AGENTS script inventories complete (all 21 scripts + helpers);
      each entry one line.
- [x] 4 AGENTS.md overlay-contract consistency: custom rules → project
      `.guardrails/` overlay; database config → config surface (schema-health
      config-file task from fix-vacuous-and-broken-gates or its own follow-up);
      remove the two "edit the submodule" instructions.
- [x] 5 SEMANTIC-005 decision: implement useEffect dependency checking or
      remove it from README + script header + semantic-rules (record which in
      the failure registry if it was incident-adjacent).
- [x] 6 CHANGELOG: [Unreleased] gains the coherence-service entry (S1-S4
      summary, schemas, container, exit matrix); merge duplicate `### Fixed`;
      cut 1.3.0 decision recorded (VERSION bump task).
- [x] 7 templates/README.md: full tree (runner-monitor, add-a-runner);
      frontmatter claim fixed; file-size-check SETUP header references real
      script (or none — the workflow is self-contained).
- [x] 8 Skills: replace `docs/AGENT_GUARDRAILS.md` refs with AGENTS.md;
      cross-ref paths match in-repo layout; commit-type lists reconciled with
      guardrails-compliance.yml (one list).
- [x] 9 Allowlist decontamination: `git mv` the 1,726 gamerepo01 entries out
      of the baseline (consuming repo overlay); fresh install scans clean.
- [x] 10 silent-success-rules.json: preamble true again (disable the two
       families or change the preamble + gate default behavior decision).
- [x] 11 Registry comments: decision recorded — keep the `#` header lines;
       all three readers (gate_overlay, regression_diff,
       failure_registry_check) skip `#` lines and the hygiene gate validates
       the file, so the sidecar would be ceremony without a consumer.
       fix_commits: FAIL-2026091901..12 backfilled with real SHAs; the legacy
       `pending`/resolved pair predates this audit (FAIL-07a50c72's rule) and
       is left for the data owner.
- [x] 12 Rules-file schema validation wired (CI self-gates step):
       pattern-rules + semantic-rules + silent-success validated against
       their schemas; pre-work-check rule table regenerated.
- [x] 13 .gitignore dedupe; drop the dead tilde pattern.
- [x] 14 docs/qa delta note listing closed QA items (M1-M3, M7, M10, H1, H3).
