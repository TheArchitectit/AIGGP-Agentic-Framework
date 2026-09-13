# Proposal: Decontaminate the shared baseline — allowlist, registry, bundled specs

**Change ID:** 2026-09-13-baseline-hygiene
**Source audit:** docs/qa/2026-09-13-full-qa.md (findings H3, H8, M8, L6)
**Status:** Proposed

## Problem

DevGate's bundled baseline — the files every consumer inherits — carries
another project's data and this repo's leftovers:

1. **1,726 allowlist entries for a different project's tree** (H3):
   silent-success-allowlist.json (12,093 lines) references `internal/`,
   `go/`, `cmd/`, `tests/` paths that do not exist here. It bloats every
   install and models exactly the wrong workflow. Flagged 2026-09-09; still
   present. [verified]
2. **The failure registry holds other repos' bugs** (H8 context): 12+
   entries reference files that only exist in consuming projects
   (`go/internal/engine/game.go`, a game project's
   `.github/workflows/ci.yml`, …), producing permanent stale-path warnings
   for every consumer. The structural cause is live: log_failure.py defaults
   to appending into the *submodule's* registry, so every consumer following
   the docs re-contaminates the baseline. [verified]
3. **Game-framework specs are bundled in the language-agnostic framework**
   (M8): openspec/specs/{game-regression, game-type-phase-matrix,
   per-screen-tracking} are Sword-of-Hope documents with no requirement IDs
   (spec_traceability reports 0/0 on the repo's own specs) referencing gates
   that do not exist here; scripts/game-framework-README.md tells readers to
   submodule a different repo. [verified]
4. **`.gitignore` misfits** (L6): `Cargo.lock` ignored (wrong default for the
   Rust binary projects this framework mostly serves) and an unenforceable
   agent-behavior rule (PREVENT-DIST-001) embedded in comments.

## Scope

Shrink every bundled data file to what belongs to this repository; move
project-specific data to the projects that own it (or document the move);
fix the default write path that causes re-contamination; gate against
regression.

## Non-goals

- The silent-success overlay merge mechanism (owned by
  2026-09-13-rule-enforcement-gaps) — this change owns the *data* and the
  log_failure default.
- Deleting game-framework capability work: specs move to the game-framework
  project where they are enforceable, they are not discarded.

## Success criteria

- silent-success-allowlist.json contains only entries whose `file` exists in
  this repository (today: zero) and is under 50 lines.
- failure_registry_check.py runs warning-free on a clean checkout.
- log_failure.py in a submodule layout appends to the project overlay by
  default; appending to the baseline requires an explicit flag.
- A new baseline-hygiene gate fails CI when a bundled entry references a
  path absent from this repo.
