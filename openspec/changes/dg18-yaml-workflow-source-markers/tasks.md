# Tasks

## 1. Add narrowly scoped YAML workflow marker discovery

- [ ] 1.1 Add `.yml`/`.yaml` source discovery only for `.github/workflows/`, `templates/github-workflows/`, and `templates/gitlab-ci/`; preserve all existing source-class behavior.
- [ ] 1.2 Require a standalone YAML comment marker and exclude docs/examples, tests/fixtures, generated files, and archives from the new YAML source class.
- [ ] 1.3 Add real-tree coverage for `templates/gitlab-ci/includes/devgate-bootstrap.yml` and isolated fixture-only controls for excluded examples, fixture paths, quoted scalars, and indented marker-shaped text inside literal and folded block scalars. Include a genuine dedented comment control.
- [ ] 1.4 Exercise traceability and gap scanning against the same fixture; confirm the coverage sets agree and the current eligible bootstrap marker is no longer reported uncovered.
- [ ] 1.5 Run focused tests, test-count floors, repository gates, and pinned OpenSpec validation; report changes to coverage and ratchet behavior without raising the ratchet solely to mask missed markers.

## 2. Candidate verification and review

- [ ] 2.1 Audit the whole YAML inventory and document why each included source directory is enforcement code and each excluded example/data path is not.
- [ ] 2.2 Obtain independent review of source eligibility, exclusions, both scanner consumers, and the real uncovered-marker regression.

## Workflow follow-up

Keep this package active until both scanners, exclusion controls, test suite, and independent review pass. Do not mark implementation complete from static path assertions alone.
