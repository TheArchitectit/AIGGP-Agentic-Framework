# Proposal

## Why

The Windows parity drill reports `corpus-02-surface-divergence` as a usage
failure instead of the pinned surface-reach finding. `_materialize` replaces
`{root}` in JSON-serialized seed content with native `str(Path)`, which
introduces unescaped backslashes on Windows and makes the fixture invalid JSON.
The seeded corpus itself is stable and must remain unchanged.

## What Changes

- Use a JSON-safe slash-form absolute path when substituting `{root}` in seed
  file content.
- Keep native path handling for subprocess argv separate; do not alter the
  pinned corpus data or its digest.
- Add regression coverage that decodes the materialized JSON and verifies the
  resulting path remains absolute on Windows and POSIX.
- Run the five-case hermetic parity drill on Windows and Linux.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `forge-parity`: require hermetic seed materialization to preserve valid
  structured data across supported host path styles.

## Impact

`hub/forge/parity.py`, `tests/test_gitlab_forge_support.py`, and
`openspec/changes/add-gitlab-forge-support/specs/forge-parity/spec.md`. The
corpus files, expected findings, and lock digest remain unchanged.
