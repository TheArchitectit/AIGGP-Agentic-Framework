# Evidence at Scope Review

## Baseline

- Exact source snapshot: `ac61e20fa7a4afcc8e2827817446fa01cb5730ff`.
- `scripts/lib/spec_discovery.py` declares `SCAN_EXTS` without `.yml` or `.yaml` and `collect_markers` filters by that set.
- The real marker `# spec: glf-template-bootstrap-01` is at `templates/gitlab-ci/includes/devgate-bootstrap.yml:1`.
- `python scripts/spec_traceability.py --report` reports `glf-template-bootstrap-01: UNCOVERED`; the full report is 245/280 covered, 35 advisory uncovered. `glf-template-bootstrap-01` is an explicit member of the uncovered list.
- Existing active `spec-fmt-04/05` requirements concern strict CLI negative control and stable ID completeness. No active package in this snapshot defines YAML source classes or controls.

## Acceptance boundary

This package records a discovery-scope defect and proposed verification only. It changes no scanner or workflow source. DG-18 implementation and fixture evidence remain unchecked.

## Later baseline and scope review

The exact draft revision `6b08ee17b1309aba241f7156b9b9277fb37e4270` still
reported `glf-template-bootstrap-01` uncovered. It reported 246 of 282 total
markers covered. All eleven existing YAML source markers in the declared
workflow roots are leading comments on line one.

A local probe of a draft lexical scanner missed genuine markers after a legal
plain scalar apostrophe and counted an escaped-quote payload as a marker.
A YAML parser confirmed that a valid root scalar can also contain an
unindented marker-shaped line. These cases led to a leading-preamble rule.
The earlier lexical implementation is provisional and contributes no accepted
coverage.

## Implementation Verification

- The shared scanner now reads only top-level `# spec:` comments in leading
  preambles under the three owned workflow roots. It stops at first YAML
  content, excludes denied path components and symlinked files, rejects
  malformed attached ID suffixes, and decodes YAML as strict UTF-8. Existing
  non-YAML marker scanning is unchanged; no YAML parser or dependency was
  added.
- Focused command in the provided Python 3.12 test image:
  `python -m pytest -q tests/test_spec_yaml_workflow_markers.py tests/test_spec_traceability.py tests/test_spec_gap_scan.py`
  passed 48 tests. The focused YAML module alone passed 5 tests.
- The controlled tree verifies both scanners return the same covered and
  uncovered IDs across owned-root markers, scalar decoys, nested fixtures,
  symlinks, Unicode whitespace controls, and a Python-source control.
- The actual owned workflow roots contain 11 leading YAML marker comments;
  the shared scanner recognizes both `GLF-01` and
  `glf-template-bootstrap-01`. The scanner source carries `spec-fmt-06`.
- Full-tree traceability changed from 246/282 covered and 36
  uncovered at scope review to 248/282 covered and 34 uncovered. The two newly
  covered inventory IDs are `spec-fmt-06` and
  `glf-template-bootstrap-01`. Uppercase `GLF-01` was already covered in
  non-YAML source and adds no coverage count.
- OpenSpec 2.2.0 reported this change valid in strict mode.

## Independent and integrated laptop verification

The independent reviewer reran all 48 focused tests on Docker Desktop and
approved the measured change from 246/282 to 248/282. In a disposable test
tree with the required capability anchor, traceability and gap scanning
reported the same 34 uncovered IDs.

The repository's pinned OpenSpec CLI passed strict validation on the
integrated active tree. Pattern, semantic, regression, silent-success,
test-floor, and open-item checks completed locally. The test-floor check
collected 2,128 tests across 145 suites. The checksum generator rewrote the
scanner's release checksum, and all 160 checksums verified.
