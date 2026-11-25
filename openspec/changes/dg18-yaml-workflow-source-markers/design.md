# Design

## Context

`scripts/lib/spec_discovery.py` is the shared source of requirement and marker discovery for both traceability and gap scanning. Its `SCAN_EXTS` excludes `.yml` and `.yaml`; `collect_markers` therefore cannot see the source comment at `templates/gitlab-ci/includes/devgate-bootstrap.yml:1`. The gate reports `glf-template-bootstrap-01` uncovered. Existing `spec-fmt-04/05` work covers strict validation and stable requirement IDs, not YAML source discovery.

## Goals and Non-Goals

**Goals:** recognize real YAML workflow source comments in a narrow set of AIGGP-owned source paths, keep both consumers of the shared discovery function consistent, and make example/fixture exclusion executable in tests.

**Non-Goals:** parse all YAML, scan arbitrary YAML configuration or data, expand the marker grammar for other languages, change traceability coverage policy, add source markers to workflows in this package, or mark any capability exercised.

## Decisions

1. Limit the new YAML source class to `.yml`/`.yaml` files under `.github/workflows/`, `templates/github-workflows/`, and `templates/gitlab-ci/`. Leave composite action metadata and arbitrary repository YAML out of scope unless separately justified.
2. Accept only a standalone comment line with optional indentation followed by `# spec:` and the existing comma-separated ID grammar. Recognize scalar context before accepting a marker. Treat indented contents of literal and folded block scalars as payload. Resume comment recognition after the scalar ends at a dedent. Use syntax-aware or conservative context detection.
3. Exclude path components used for examples, fixtures, tests, generated output, and archives even when they appear beneath an otherwise eligible source prefix. Keep the current non-YAML discovery behavior unchanged.
4. Keep the allowlist/path predicate in the shared discovery module so `spec_traceability.py` and `spec_gap_scan.py` report identical results.

## Validation design

- In the real source tree, assert `collect_markers` sees `glf-template-bootstrap-01` from `templates/gitlab-ci/includes/devgate-bootstrap.yml`.
- In an isolated temporary root with a requirement ID, place the only matching marker in `docs/examples/workflow.yaml` and separately in `tests/fixtures/workflow.yml`; neither may satisfy that requirement.
- Use separate controls for a quoted scalar and for standalone-looking marker lines under both `run: |` and a folded `>` scalar. Assert that each payload marker is excluded and a genuine comment after the scalar dedents is discovered.
- Run both consumers against the same fixture and compare their coverage result.

## Risks and Trade-offs

- **Too broad a source extension set:** scope YAML by exact project-owned CI source directories and an executable exclusion test.
- **A genuine YAML workflow outside those roots is missed:** report it as a gap for review rather than globally crediting arbitrary data files.
- **The same ID exists both in implementation and a fixture:** the isolated fixture-only control prevents unrelated in-scope code from masking exclusion behavior.
