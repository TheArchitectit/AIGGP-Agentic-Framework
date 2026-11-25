# Clarify the drift workflow setup comment

## Why

The hosted Data Corruption step for AIGGP draft #41 rejected an intentional
rewrite of a drift workflow setup comment. The pushed-range check matched the
same-length replacement to its substitution-flip rule.

## What Changes

- State the ignored checkout path and reviewed full commit directly in the
  drift template's setup comment.
- Verify the exact PR range with the existing content and range checks.

## Capabilities

### New Capabilities

- `drift-workflow-setup-instructions` documents the pinned setup inputs.

### Modified Capabilities

None.

## Impact

The setup comment of `templates/github-workflows/drift-scan.yml` and its
OpenSpec verification record.
