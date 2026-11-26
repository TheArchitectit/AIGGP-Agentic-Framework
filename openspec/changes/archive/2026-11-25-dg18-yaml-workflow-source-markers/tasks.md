# Tasks

## 1. Discover workflow-level YAML annotations

- [x] 1.1 Limit YAML annotation discovery to the three specified owned workflow roots. Exclude examples, fixtures, tests, generated content, archives, and symlinks. Preserve existing source modes.
- [x] 1.2 Recognize a real top-level preamble comment. Stop at the first YAML content line so quoted or block values cannot be interpreted as markers.
- [x] 1.3 Add coverage for the existing GitLab bootstrap marker and separately identified YAML literal, folded, quoted, root-scalar, and excluded example controls.
- [x] 1.4 Run traceability and gap scanning against the same controlled tree and confirm their covered and uncovered results agree.

## 2. Verify and archive

- [x] 2.1 Run focused tests, test-count floors, repository gates, and pinned OpenSpec validation. Record the marker count change.
- [x] 2.2 Obtain independent review of scope, test controls, and coverage at the GitLab source. Archive once implementation and evidence are complete.
