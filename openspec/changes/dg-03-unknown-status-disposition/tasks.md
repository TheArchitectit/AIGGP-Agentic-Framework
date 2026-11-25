# Tasks

## 1. Status roster

- [ ] 1.1 Generate the 12 UNKNOWN-capability roster with every heading and parsed ID (or stable heading location); verify it against `openspec/INDEX.md`.
- [ ] 1.2 For each requirement, inspect code, behavioral tests, CI, owner decisions, and external evidence; write outcome, owner, evidence pointer or explicit absence, and review date.

## 2. Status-safe publication

- [ ] 2.1 Implement disposition rendering separately from lifecycle status; verify an `insufficient` disposition cannot alter CLOSED/UNPROVEN/UNKNOWN classification.
- [ ] 2.2 Preserve `game-type-phase-matrix` as DEFERRED and record its existing owner answer; verify no relabeling occurs.
- [ ] 2.3 Run strict validation and index/status checks; verify all twelve UNKNOWN specs are explicitly accounted for and none was closed by prose.
