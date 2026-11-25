# Evidence at Scope Review

## Baseline

- Exact source snapshot: `ac61e20fa7a4afcc8e2827817446fa01cb5730ff`.
- Read-only review found three workflow files with runtime `.devgate/` usage and recursive submodule checkout: `templates/github-workflows/drift-scan.yml`, `specs.yml`, and `text-integrity.yml`.
- `spec-coherence.yml` has a distinct in-tree bootstrap at lines 164-190 and is not included in this finding. `bundle-size-check.yml` and `file-size-check.yml` mention `.devgate` in comments but do not invoke it at runtime.
- No live consumer workflow was launched and no external repository, credential, or runner was used.

## Source anchors

- `templates/github-workflows/drift-scan.yml:49-59,109-139` checks out recursively, then invokes `.devgate/scripts/` entry points.
- `templates/github-workflows/specs.yml:64-67,102-126` checks out recursively, then executes the strict negative control, traceability checks, and gap scanner from `.devgate/scripts/`.
- `templates/github-workflows/text-integrity.yml:69-94,102-116,136-144` sets `.devgate/scripts`, checks out recursively, runs charset/encoding/corruption checks, and dispatches declared `.devgate/tests/` controls.

## Acceptance boundary

This is scope evidence only. DG-08 implementation tasks remain unchecked; none of the three affected workflow jobs has been accepted through a clean consumer run yet.
