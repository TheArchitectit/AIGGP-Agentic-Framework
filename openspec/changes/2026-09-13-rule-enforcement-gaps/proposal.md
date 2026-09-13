# Proposal: Close the rule-enforcement gaps — dead rulesets, unwritable spec markers, broken config paths

**Change ID:** 2026-09-13-rule-enforcement-gaps
**Source audit:** docs/qa/2026-09-13-full-qa.md (findings H1, H6, M1, M2, M3)
**Status:** Proposed

## Problem

The framework advertises rule coverage it does not enforce, and two of its
contracts can't be satisfied from outside the submodule:

1. **9 of 10 enabled semantic rules have no implementation** (H1):
   semantic-rules.json ships SEMANTIC-001…010, all enabled; semantic-scan.mjs
   implements only SEMANTIC-001. Four of the dead rules are error-severity
   (SEMANTIC-003, -004, -007, -008, -010). Consumers reading the rules file
   believe they have AST coverage they do not have; the README and the
   script's own header advertise SEMANTIC-005 (React useEffect).
2. **extracted-rules.json is entirely unenforced** (M1): 10 rules
   (PREVENT-GIT-*, PREVENT-SYS-001, PREVENT-SEC-001/002, PREVENT-SCOPE-001)
   loaded by nothing. They are also agent-*behavior* rules file scanning
   cannot enforce — they duplicate what the skill templates already say.
3. **spec_traceability.py can never pass for Python** (H6): the marker regex
   accepts only `// spec: <id>`; `# spec: <id>` never matches, and
   findings_to_spec.py tells implementers to use `//` syntax in any language.
4. **Two gates can only be configured by editing the submodule** (M2):
   silent-success-scan.sh reads rules/allowlist only from the DevGate tree
   (no overlay merge, no .guardrailsignore); schema-health-check.mjs's only
   configuration path is editing the script — while AGENTS.md says "Don't
   modify DevGate scripts".
5. **silent-success-rules.json contradicts its documented opt-in** (M3): two
   families ship `enabled:true` although the gate's header and the drift
   template promise every family ships disabled so fresh installs are green.

## Scope

Decide per dead rule — implement or remove — and make the surviving contract
honest: rules files contain only enforced rules, docs list only shipped
coverage. Fix the spec-marker contract for all scanned languages. Bring
silent-success and schema-health configuration onto the overlay contract.

## Non-goals

- Writing the nine AST checkers in this change (that is the bulk of the work;
  see Design D1 for the staged decision).
- Changing pattern-rules.json contents (the enforced 32).

## Success criteria

- `jq '.rules[] | select(.enabled==true)' semantic-rules.json` lists only
  rules the scanner implements, and the scanner implements every listed rule.
- `# spec: <id>` in a .py file satisfies spec_traceability.py in blocking mode.
- A consumer configures silent-success and schema-health entirely from the
  project-root overlay; the submodule is never edited.
- A fresh install runs silent-success-scan green with zero configuration.
