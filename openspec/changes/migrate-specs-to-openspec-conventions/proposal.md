# Proposal: migrate-specs-to-openspec-conventions

## Problem

The repository's OpenSpec setup fails its own tooling. Verified 2026-09-19
with openspec CLI 1.12.0:

1. **`openspec validate --all --strict` → 15 failed, 5 passed.** All 15 main
   specs under `openspec/specs/` fail with the same error: `Spec must have a
   Purpose section. Missing required sections. Expected headers: "## Purpose"
   and "## Requirements"`. The house format uses `## Requirement:` (h2) and
   `<!-- id: -->` markers, which the CLI does not parse:
   `openspec list --specs` reports **`requirements 0` for every capability**
   — the platform's source of truth reads as empty while the repo's own
   marker-based gate (`scripts/spec_traceability.py`) reports 100 tracked ids.
   Two tools, two incompatible views of the same specs.
2. **No `openspec/project.md`** — added separately with this roadmap; the CLI
   had no project context.
3. **Game specs are foreign documents.** `game-regression`,
   `game-type-phase-matrix`, `per-screen-tracking` are Sword-of-Hope /
   devgate-game-framework specs: no ids, no scenario structure, and they name
   gates that do not exist here (`game_regression_check.py` — actual file is
   `game_regression.py`; phase-matrix machinery exists nowhere in this tree).
   This violates the repo's own `base-own-01` ("bundled entry references a
   path absent from this tree") and produces the "0/0 capabilities" case
   `base-specs-01` explicitly forbids.
4. **Archive hygiene debt.** Two ✓ Complete changes (`add-runner-to-fleet`,
   `fix-size-gate-test-scope`) sit unarchived — the delivered `fleet-add-01`
   requirement exists only inside the change package, invisible to
   `openspec list --specs`. `ai01-runner-monitor-impl` has no `proposal.md`
   (a `plan.md` instead) and cites a nonexistent archive path
   (`archive/2026-09-13-ai01-runner-monitor/`, actual: `2026-09-13-runner-
   monitor/`) in two files. `mon-local-01` (local-only network posture) was
   lost in the archive→main migration of `2026-09-13-runner-monitor`.
   All six archived changes have 0 checked task boxes (evidence lives in
   handoff.md) — `openspec list` showed them as incomplete forever while they
   were active.
5. **Stacked change-local truth.** `devgate-spec-coherence-service` (48/88)
   and `devgate-product-tiers-fleet-manager` (0/37, hard-blocked) hold their
   normative content entirely change-local by design (GD-3: publishing while
   active double-counts ids in `spec_traceability.py`). That decision is sound
   but undocumented at the platform level — nothing tells a contributor why
   main specs and change deltas disagree, or what the publish ceremony at
   archive time must do (re-run traceability, dedupe, update markers).
6. **Spec/code contradictions:** `rule-coverage-truth` requires
   `extracted-rules.json` absent (it ships, schema-violating);
   `baseline-ownership` requires `game-framework-README.md` rewritten (it
   still instructs readers to submodule a repo that does not exist);
   the skills templates all reference a nonexistent `docs/AGENT_GUARDRAILS.md`.

## Solution

A mechanical, verifiable migration with no semantic changes to requirements:

1. Restructure all retained main specs to CLI-valid format: add `## Purpose`,
   convert `## Requirement:` → `### Requirement:` under a `## Requirements`
   section, keep `#### Scenario:` blocks and `<!-- id: -->` markers (the
   traceability gate's keys) — both parsers then agree on the same files.
2. Dispose of the three game specs per a recorded decision: move them to the
   consuming game repo (they describe that repo's gates), leaving redirects/
   history; delete the game-framework README or rewrite it as the framework's
   game-tooling doc.
3. Archive `add-runner-to-fleet` and `fix-size-gate-test-scope` with the CLI
   (their deltas land in main specs); fix `ai01-runner-monitor-impl`'s missing
   proposal + broken archive pointer; restore the lost `mon-local-01` into
   `hub-architecture`.
4. Document the change-local-truth policy (GD-3) in `openspec/project.md` +
   AGENTS.md: while a change is active its deltas are authoritative;
   publication happens at archive with the traceability re-run steps.
5. Wire `openspec validate --all --strict` into CI (depends on
   add-framework-ci-pipeline) so format drift can never accumulate again.
6. Success criterion, repeated until true: `openspec validate --all --strict`
   passes 100%; `openspec list --specs` shows every capability with a
   non-zero requirement count; `python3 scripts/spec_traceability.py`
   (blocking) still passes for framework capabilities — the two parsers agree.

## Impact

- Every file under `openspec/specs/` (format-only edits + game-spec disposal),
  `openspec/changes/ai01-runner-monitor-impl/` (proposal.md added, pointers
  fixed), archive moves for two complete changes.
- `AGENTS.md` (OpenSpec conventions section), CI job (validate step).
- No runtime code changes; `spec_traceability.py` marker compatibility is the
  invariant (its regexes are heading-agnostic — verify with its own test
  suite before/after).
