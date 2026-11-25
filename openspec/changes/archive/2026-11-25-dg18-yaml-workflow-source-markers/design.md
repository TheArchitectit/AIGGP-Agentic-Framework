# Design

## Context

`scripts/lib/spec_discovery.py` supplies marker discovery to traceability and gap scanning. Its extension set excludes YAML, so both tools miss the first-line marker in `templates/gitlab-ci/includes/devgate-bootstrap.yml`.

The existing YAML workflow annotations are all file-level markers on line one. A local review of a general lexical scanner found inconsistent handling of apostrophes in plain values, escaped double quotes, and explicitly indented nested block scalars. A parser also confirmed that valid root scalars can contain an unindented line that looks like a marker.

## Decisions

- Recognize file-level annotations in the leading comment preamble of `.yml` and `.yaml` under `.github/workflows/`, `templates/github-workflows/`, and `templates/gitlab-ci/`. Accept only a top-level standalone comment in that preamble. Once the first YAML content line is reached, treat the rest of the document as YAML content. This covers all workflow annotations present at the reviewed revision and keeps annotation discovery out of scalar parsing.
- Exclude YAML in documentation, fixtures, tests, generated output, archives, and symlinked files. Keep the existing non-YAML source classes intact.
- Keep the discovery rule shared by traceability and gap scanning. The tests use distinct requirement IDs for literal, folded, quoted, root-scalar, and example controls so any incorrect credit is visible.

## Verification

Exercise a leading comment before real workflow YAML and the existing GitLab bootstrap marker. Verify decoys in owned and excluded paths, including quoted and block scalar payloads and root scalar documents. Verify that text after the preamble receives no credit. Run both scanning commands against the same fixture and compare the covered and uncovered sets.
