# Proposal: docs-and-data-truth-pass

## Problem

The repo's own `doc-truth` spec demands that documentation equal the tree; the
2026-09-19 review found it does not, in both directions. Highlights (all
verified against HEAD):

**README/AGENTS drift**
1. README's "What you get" tree (lines 28-66) omits `hub/`, `container/`,
   `openspec/`, `tests/`, `docs/`, `.github/` — over half the repository,
   including the two largest recent features (runner-monitor hub, spec-
   coherence service). A reader cannot discover the coherence service from the
   README at all; it has no README section despite being ~4k lines + a
   Containerfile + 13 schemas.
2. README:33 says "29 rules"; `pattern-rules.json` ships 32. README/AGENTS
   script trees omit `game_regression.py`, `scene_inventory.py`,
   `gate_overlay.py`, `failure_registry_check.py`, `hub-watchdog.sh`,
   `runner-enroll.sh`, and the three `regression_*` helpers.
3. AGENTS.md "Adding Custom Rules" tells consumers to edit
   `.devgate/.guardrails/prevention-rules/pattern-rules.json` and its database
   section says to edit `scripts/schema-health-check.mjs` — both violate the
   README's overlay contract and AGENTS.md's own "Don't modify DevGate
   scripts" (QA M10, still open).
4. `templates/README.md` tree omits `templates/runner/add-a-runner.md` and the
   entire `templates/runner-monitor/` directory; `templates/README.md:62`
   claims all skill frontmatter carries tools/globs (2 of 6 do);
   `file-size-check.yml:9` SETUP references `scripts/check_file_sizes.sh`,
   which does not exist.
5. `semantic-scan.mjs:7-8` header + README advertise SEMANTIC-005; only
   SEMANTIC-001 exists (9 of 10 enabled semantic rules are dead config — QA
   H1). Either implement or de-advertise.
6. CHANGELOG: the entire spec-coherence service (hub/coherence/, container/,
   ~40 commits, S1-S4) is absent from `[Unreleased]`; two `### Fixed`
   headings under `[Unreleased]` violate Keep-a-Changelog shape; VERSION/CHANGELOG
   coherence needs a release decision.

**Data-file hygiene**
7. `.guardrails/silent-success-allowlist.json`: 1,726 entries / 12,093 lines
   referencing 389 `go/` files **none of which exist in this repo** — another
   project's overlay shipped in the shared baseline (QA H3).
8. `silent-success-rules.json` preamble says every family ships disabled; two
   ship `enabled: true` (QA M3).
9. `failure-registry.jsonl` opens with `#` comment lines (not valid JSONL for
   any standard consumer); two `resolved` entries carry `fix_commit:
   "pending"` against the registry's own recorded rule (FAIL-07a50c72).
10. `pattern-rules.json` conforms to its schema but nothing validates it
    against `pattern-rules.schema.json` (schema is documentation-only);
    `pre-work-check.md` lists 14 of 32 rules under "in effect".
11. `.gitignore`: dead `~/.devgate-heartbeat.env` pattern (tilde doesn't
    expand); duplicate entries.

## Solution

A single docs-and-data truth pass, mechanically checkable: rewrite the README
tree + component sections to describe everything that ships (coherence
service gets its own section with a usage sketch); make AGENTS.md cite the
overlay contract consistently (rule edits → project overlay; schema config →
documented config surface after the schema-health config-file fix); fix every
count, filename, and script reference; de-advertise SEMANTIC-005 or implement
it (decision recorded); write the coherence-service CHANGELOG entry; purge the
contaminated allowlist to the consuming repo's overlay; align
silent-success-rules with its own preamble; move registry comments to a sidecar
or strip on read everywhere; add a schema-validation step for rules files
(reuse `schemacheck`-style checking or `ajv`-free node validator); regenerate
pre-work-check's rule table; dedupe .gitignore. Every fix lands with the doc
checker able to catch its recurrence (counts derived from files at render time
or checked in CI).

## Impact

- README.md, AGENTS.md, CHANGELOG.md, templates/README.md, all six SKILL.md,
  .guardrails/* data files, .gitignore, docs/NEW_REPO_ONBOARDING.md cross-refs.
- No code behavior changes; one new CI check (docs consistency: rule counts,
  referenced-files-exist) can live in the CI change's self-gates job.
- No spec deltas (doc-truth and rule-coverage-truth already mandate this).
