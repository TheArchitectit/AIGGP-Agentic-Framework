# Proposal: Fix the release pipeline — audit gate, npm-audit classification, publish safety

**Change ID:** 2026-09-13-deploy-pipeline
**Source audit:** docs/qa/2026-09-13-full-qa.md (findings C6, C7, H7, M5, M6, L8)
**Status:** Proposed

## Problem

The publish path — the one place a mistake is irreversible — has three defects
that each independently defeat it, plus three that hollow out its gates:

1. **deploy.sh gates the wrong repository** (C7): the regression gate runs
   from the DevGate directory, whose `.git` stops root resolution there, so
   the project's code is never regression-gated before publish. Present since
   the 2026-09-09 QA. [verified]
2. **npm audit downgrades direct runtime vulns** (C6): `is_runtime` is
   derived from `effects` (dependents), which is empty for direct
   dependencies — a HIGH vuln in a direct runtime dep (lodash@4.17.15,
   verified live) reports as dev-only and never blocks. [verified]
3. **PyPI publish double-uploads and aborts after success** (H7):
   `A || B && C` precedence runs `twine upload` a second time after a
   successful first upload; twine's duplicate rejection aborts the pipeline
   *after* the immutable publish — the exact torn state the stage ordering
   exists to prevent. [code-read]
4. **Schema health is a warning in a stage table that calls it a gate** (M5);
   lint/clippy are likewise demoted inside a step named "full gate".
5. **Artifact verify passes vacuously on an empty contract** (M6): a present
   but `must_contain`-less contract asserts nothing and prints OK.
6. **fix_commit validation accepts non-40-hex values unchecked** (L8), so the
   short SHAs log_failure.py's own examples produce are never verified.

## Scope

Correct the audit/publish logic in deploy.sh, regression_audit.py, and
failure_registry_check.py; make gate stage severities honest (a stage is a
gate or it is labeled advisory); keep every abort-before-publish guarantee.
No changes to publish targets, tag semantics, or the artifact contract
format.

## Non-goals

- Adding new package managers or registries.
- The drift-scan CI template (separate change: 2026-09-13-ci-templates-docs).
- `--all` scan semantics (separate change: 2026-09-13-gate-correctness) —
  though C7's fix depends on that change's root contract landing first or
  being passed explicitly.

## Success criteria

- A fixture consumer project deploy run shows the regression gate evaluating
  the consumer's tree, not `.devgate/`'s.
- lodash@4.17.15 as a direct dependency blocks the gate; the same vuln
  reachable only through a dev dependency warns.
- A shell-level dry run of the PyPI leg proves exactly one upload attempt on
  success and a clear abort (pre-publish) on failure.
