# Tasks

## 1. Historical inventory

- [x] 1.1 Reproduce the proposal baseline (43 archives; 829 ordinary task rows: 719 checked / 110 unchecked; one separate `[~]`) and verify the ready-tree inventory (58 archives; 907 ordinary rows: 797 checked / 110 unchecked; one `[~]`) against repository content.
- [x] 1.2 Compare all 64 archived delta-capability directories (58 unique names) against the 65 ready-tree canonical specs, active deltas, available retirement records, and archive-path Git history; save stable `ARC-CAP-NNN` IDs and explicit unresolved dispositions in `delta-capability-reconciliation.md`.

## 2. Evidence disposition

- [ ] 2.1 Review every unchecked task and every vanished delta against current implementation, tests, CI, documentation, and commit history; record rationale and source evidence or explicit absence. The [first evidence batch](task-2.1-batch-001.md) covers the first two historical task rows.
- [ ] 2.2 Carry only confirmed live work into active changes with owners and new IDs; verify archive files remain byte-for-byte unchanged.
- [ ] 2.3 Independently review the reconciliation inventory and rerun pinned `openspec validate --archived --strict --json`; verify the ten baseline archive task-check failures are dispositioned and no task is classified implemented solely from its historical checkbox.
