# Tasks

## 1. Historical inventory

- [ ] 1.1 Extract all 829 archived task rows and verify 43 archive IDs and the 719 checked / 110 unchecked aggregate against repository content.
- [ ] 1.2 Compare every archived delta capability against the 56 published specs, active deltas, retirement records, and archive-time Git history; save stable reconciliation IDs.

## 2. Evidence disposition

- [ ] 2.1 Review every unchecked task and every vanished delta against current implementation, tests, CI, documentation, and commit history; record rationale and source evidence or explicit absence.
- [ ] 2.2 Carry only confirmed live work into active changes with owners and new IDs; verify archive files remain byte-for-byte unchanged.
- [ ] 2.3 Independently review the reconciliation inventory and rerun pinned `openspec validate --archived --strict --json`; verify the ten baseline archive task-check failures are dispositioned and no task is classified implemented solely from its historical checkbox.
