# Tasks: docs-and-data-truth-pass

- [ ] 1 README: tree reflects the full repo; new "Spec Coherence Service"
      section (what/why, request→result flow, container execution, exit-code
      table pointer); hub monitor section (exists in CHANGELOG, not README).
- [ ] 2 Rule-count truth: derive "N rules" from the file at write time or a
      CI check comparing prose numbers to `jq '.rules | length'`.
- [ ] 3 README/AGENTS script inventories complete (all 21 scripts + helpers);
      each entry one line.
- [ ] 4 AGENTS.md overlay-contract consistency: custom rules → project
      `.guardrails/` overlay; database config → config surface (schema-health
      config-file task from fix-vacuous-and-broken-gates or its own follow-up);
      remove the two "edit the submodule" instructions.
- [ ] 5 SEMANTIC-005 decision: implement useEffect dependency checking or
      remove it from README + script header + semantic-rules (record which in
      the failure registry if it was incident-adjacent).
- [ ] 6 CHANGELOG: [Unreleased] gains the coherence-service entry (S1-S4
      summary, schemas, container, exit matrix); merge duplicate `### Fixed`;
      cut 1.3.0 decision recorded (VERSION bump task).
- [ ] 7 templates/README.md: full tree (runner-monitor, add-a-runner);
      frontmatter claim fixed; file-size-check SETUP header references real
      script (or none — the workflow is self-contained).
- [ ] 8 Skills: replace `docs/AGENT_GUARDRAILS.md` refs with AGENTS.md;
      cross-ref paths match in-repo layout; commit-type lists reconciled with
      guardrails-compliance.yml (one list).
- [ ] 9 Allowlist decontamination: `git mv` the 1,726 gamerepo01 entries out
      of the baseline (consuming repo overlay); fresh install scans clean.
- [ ] 10 silent-success-rules.json: preamble true again (disable the two
       families or change the preamble + gate default behavior decision).
- [ ] 11 failure-registry: comment lines moved to a `.comments` sidecar (or
       every reader taught to skip + documented); `pending` fix_commits
       resolved with real SHAs or entries annotated per the registry's rule.
- [ ] 12 Rules-file schema validation wired (CI self-gates step):
       pattern-rules + semantic-rules + silent-success validated against
       their schemas; pre-work-check rule table regenerated.
- [ ] 13 .gitignore dedupe; drop the dead tilde pattern.
- [ ] 14 docs/qa delta note listing closed QA items (M1-M3, M7, M10, H1, H3).
