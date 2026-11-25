# Proposal

## Why

The requirement source-marker scanner recognizes Python, JavaScript, shell, Rust, Zig, SQL, Lua, and GDScript files, but does not scan YAML workflow files. At the exact PR #41 source snapshot, the newly delivered `glf-template-bootstrap-01` marker in `templates/gitlab-ci/includes/devgate-bootstrap.yml` is therefore reported uncovered even though the workflow include is the implementation surface. A repository-wide YAML extension enablement could also give accidental credit to examples or fixture text.

## What Changes

- Recognize standalone YAML comment markers only in the repository-owned CI source directories `.github/workflows/`, `templates/github-workflows/`, and `templates/gitlab-ci/`.
- Keep marker extraction constrained to actual comment lines and exclude docs, tests, fixtures, generated files, and archived examples.
- Add controls proving the real GitLab include marker is discovered and example/fixture markers do not satisfy an isolated requirement.

## Capabilities

### Modified Capabilities

- `requirement-id-inventory`: YAML CI definitions are eligible source-marker locations only in the declared source classes.

## Impact

`scripts/lib/spec_discovery.py`, a focused test module, and possibly the source inventory docs. Do not change any workflow behavior, marker IDs, requirement statuses, traceability ratchet, or gate mode in this package.
