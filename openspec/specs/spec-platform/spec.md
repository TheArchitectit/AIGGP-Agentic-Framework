# Spec platform

## Purpose

The OpenSpec tree is one source of truth read by two tools: the OpenSpec CLI
and the repository's marker-based traceability gate. Every capability spec is
CLI-valid AND id-marker-parseable, completed changes are archived so their
deltas publish, and the change-local authority policy (active-change deltas
are the draft; publication happens at archive with a traceability re-run) is
documented so main-spec/change-delta divergence is never read as drift.

## Requirements

### Requirement: Main specs are CLI-valid and marker-parseable
<!-- id: spec-fmt-01 -->
Every capability spec under `openspec/specs/` SHALL be simultaneously valid
for the OpenSpec CLI (Purpose and Requirements sections, `### Requirement:`
headings, `#### Scenario:` blocks) and parseable by the repository's marker
gate (`<!-- id: -->` markers). The two parsers SHALL agree on the requirement
count of every spec, and `openspec validate --all --strict` SHALL pass in CI.

#### Scenario: dual-parser agreement
- **WHEN** `openspec list --specs` and `python3 scripts/spec_traceability.py`
  both run over the tree
- **THEN** they report the same requirement ids per capability — no capability
  reads as empty to either tool

#### Scenario: format drift blocked
- **WHEN** a spec edit breaks CLI validity or drops an id marker
- **THEN** CI fails before merge

### Requirement: Completed changes are archived
<!-- id: spec-fmt-02 -->
A change whose tasks are complete SHALL be archived with the CLI so its deltas
land in the main specs, and the main specs SHALL then be re-validated.
Active changes SHALL each have a `proposal.md` and `tasks.md`, and SHALL NOT
reference nonexistent paths.

#### Scenario: complete change lingers
- **WHEN** a change is fully checked and not archived
- **THEN** it appears as process debt in the next audit (and CI's `openspec
  list` output makes the state visible)

### Requirement: Change-local authority policy is documented
<!-- id: spec-fmt-03 -->
While a change is active, its spec deltas are the authoritative draft for the
capabilities they touch; publication to `openspec/specs/` happens at archive
time together with a traceability re-run that prevents requirement-id
double-counting. This policy SHALL be documented in AGENTS.md and the change's
own design notes, so main-spec/change-delta divergence is never read as drift.

#### Scenario: stacked changes
- **WHEN** a successor change depends on an unarchived predecessor
- **THEN** the dependency and the publication order are recorded in both
  proposals (DEP-style entries)
