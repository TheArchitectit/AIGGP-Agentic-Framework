# Tasks: migrate-specs-to-openspec-conventions

## 1. Format migration (mechanical)

- [ ] 1.1 Write the conversion table (house `## Requirement:` + id marker +
       `#### Scenario:` → CLI `## Purpose` + `## Requirements` +
       `### Requirement:` + same id marker + same scenarios) and apply it to
       the 12 retained structured specs.
- [ ] 1.2 Verify after each file: `openspec validate <capability> --type spec
       --strict` passes AND `python3 scripts/spec_traceability.py` still finds
       the same ids (no marker loss).
- [ ] 1.3 The 3 game specs: record the disposition decision (move to the
       consuming game repo / delete), execute it, and update
       `baseline-ownership` scenarios that referenced them.
- [ ] 1.4 `openspec list --specs` shows non-zero requirements for every
       retained capability.

## 2. Archive and pointer hygiene

- [ ] 2.1 `openspec archive add-runner-to-fleet` (fleet-add-01 lands in main
       specs); re-run traceability; fix any double-count.
- [ ] 2.2 `openspec archive fix-size-gate-test-scope`.
- [ ] 2.3 Add `ai01-runner-monitor-impl/proposal.md` (derive from plan.md);
       fix the two broken archive pointers (plan.md:3, tasks.md:3).
- [ ] 2.4 Restore `mon-local-01` (local-only posture) into
       `openspec/specs/hub-architecture/spec.md` with its original scenario
       text, or record its deliberate merge into mon-hub-01 as a MODIFIED
       delta with rationale.
- [ ] 2.5 Reconcile `game-regression` spec's `game_regression_check.py`
       reference with the actual `game_regression.py` (or remove with the
       spec).

## 3. Contradiction closure (spec ↔ tree)

- [ ] 3.1 Delete `.guardrails/prevention-rules/extracted-rules.json`
       (required by `rule-coverage-truth` base coverage scenario; it also
       violates its declared schema and is loaded by nothing) — README tree
       reference updated.
- [ ] 3.2 Rewrite `scripts/game-framework-README.md` per `base-specs-01`'s
       scenario (no submodule instruction; describes the absorbed scripts) or
       delete it with the game-tooling disposition.
- [ ] 3.3 Fix or remove the six skills' `docs/AGENT_GUARDRAILS.md` references
       (point at AGENTS.md, which exists).
- [ ] 3.4 Add the missing `semantic-rules.schema.json` or drop the
       `$schema` pointer in `semantic-rules.json`.

## 4. Platform policy

- [ ] 4.1 AGENTS.md: OpenSpec section — marker grammar (both comment forms
       after fix-vacuous-and-broken-gates), id namespaces, active-change
       authority (GD-3), archive ceremony steps (validate, traceability
       re-run, changelog).
- [ ] 4.2 CI: `openspec validate --all --strict` step (post-migration gate).
- [ ] 4.3 Coherence-change S8 spec-publication task references this change's
       ceremony (no double-count at publish).

## 5. Acceptance

- [ ] 5.1 `openspec validate --all --strict` → 100% pass.
- [ ] 5.2 `openspec list` shows only genuinely-active changes; no ✓ Complete
       stragglers.
- [ ] 5.3 Spec traceability gate green in blocking mode for framework
       capabilities; the failure-registry gains an entry for the
       "two parsers, two truths" incident class.
