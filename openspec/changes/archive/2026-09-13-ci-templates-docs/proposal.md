# Proposal: Fix CI templates, give the framework its own CI, and reconcile the docs

**Change ID:** 2026-09-13-ci-templates-docs
**Source audit:** docs/qa/2026-09-13-full-qa.md (findings H2, M4, M7, M9, M10, L3, L4, L5)
**Status:** Proposed

## Problem

The copy-in CI templates — the thing most consumers actually touch — ship
defects that make gates red-by-default or arbitrarily wrong, while the
framework repo itself has no CI at all:

1. **drift-scan.yml guarantees a red regression arm** (H2): both checkouts
   use default `fetch-depth: 1`; `--all` needs tags/history and now fails
   loud without them, so every scheduled run fails. The same job never
   installs `typescript@5`, so the semantic arm fails on every TS consumer.
   Flagged 2026-09-09; still present.
2. **guardrails-compliance.yml treats globs as regex** (M4): `.env` as ERE
   matches `environment.yml` and `.env.example` (which the workflow's own
   message recommends); the AI-attribution check shreds commit bodies with
   `tr '---COMMIT_SEP---' '\n'` (character map, not string split).
3. **The framework repo has no CI** (M9): `.github/` holds only FUNDING.yml;
   PRs merge with zero checks. v1.1.0/v1.2.0 shipped without CHANGELOG
   entries and VERSION still reads 1.0.0 (M7).
4. **AGENTS.md teaches overlay violations** (M10): "Adding Custom Rules"
   edits the submodule's baseline; the database section edits a submodule
   script; the same file says "Don't modify DevGate scripts". Rule counts
   are stale (29 documented vs 32 shipped).
5. **Template drift** (L4/L5): file-size-check.yml disagrees with
   regression_check.py by one line and references a script that doesn't
   exist; secret-validation.yml and guardrails-scan.mjs exempt different
   `.env.*` suffixes; DevGate's own tree isn't warning-clean on its own
   scanner (L3).

## Scope

Fix the five workflow templates, add a minimal CI workflow to this repo
running its own gates and test suite, bring VERSION/CHANGELOG to truth,
rewrite the AGENTS.md sections that contradict the overlay contract, and
align the small gate-vs-template disagreements.

## Non-goals

- Gate-logic changes (owned by gate-correctness and deploy-pipeline
  changes); this change consumes their contracts in the templates.
- Publishing releases or tags.

## Success criteria

- drift-scan.yml runs green on a fixture consumer: full history fetched,
  semantic arm's parser installed when TS/JS exists, all four gates report.
- guardrails-compliance.yml forbidden-file check matches exact basenames
  (`.env` blocked, `.env.example` allowed, `environment.yml` untouched).
- This repo's PRs run: pytest, node fixture tests, guardrails scan,
  semantic scan, failure-registry hygiene — and the workflow is required.
- VERSION, CHANGELOG, and tags agree; AGENTS.md contains no instruction to
  edit the submodule.
