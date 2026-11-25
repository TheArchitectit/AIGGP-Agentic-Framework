# Proposal

## Why

The 43 archived change directories contain 110 unchecked historical task boxes, alongside checked packages whose delta names are no longer published. A raw archive checkbox total is not current backlog evidence, yet there is no complete disposition mapping that explains which tasks were delivered, superseded, deferred, or remain live.

## What Changes

- Preserve archived `tasks.md` files and their original checkbox/evidence text unchanged.
- Create a separate, stable-ID reconciliation for each unchecked or unmapped archived task with current canonical spec, code/test/CI evidence, and final disposition.
- Carry genuinely outstanding work into a new active change with new task IDs and explicit owner; do not silently mark archive tasks complete.
- Reconcile absent archived delta capability names against publication, consolidation, or retirement evidence.

## Capabilities

### New Capabilities

- `archive-task-disposition`: auditable mapping from historical archived tasks to current evidence and successor work.

### Modified Capabilities

None.

## Impact

`openspec/changes/archive/`, the 110 unchecked task records, vanished delta names, and current OpenSpec backlog visibility.
