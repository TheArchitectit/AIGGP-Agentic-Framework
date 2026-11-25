# Evidence at Scope Review

## Baseline

- Exact source snapshot: `ac61e20fa7a4afcc8e2827817446fa01cb5730ff`.
- `scripts/lib/spec_discovery.py` declares `SCAN_EXTS` without `.yml` or `.yaml` and `collect_markers` filters by that set.
- The real marker `# spec: glf-template-bootstrap-01` is at `templates/gitlab-ci/includes/devgate-bootstrap.yml:1`.
- `python scripts/spec_traceability.py --report` reports `glf-template-bootstrap-01: UNCOVERED`; the full report is 245/280 covered, 35 advisory uncovered. `glf-template-bootstrap-01` is an explicit member of the uncovered list.
- Existing active `spec-fmt-04/05` requirements concern strict CLI negative control and stable ID completeness. No active package in this snapshot defines YAML source classes or controls.

## Acceptance boundary

This package records a discovery-scope defect and proposed verification only. It changes no scanner or workflow source. DG-18 implementation and fixture evidence remain unchecked.
