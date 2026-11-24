# Tasks: Two Template Defects a Rootless Fleet Runner Exposed

Status is per-task. Both defects were observed on the DevGate fleet runner by a
consumer repository before this change existed; the tasks below are the
framework-side fix and its evidence.

## 1. Specification

- [x] 1.1 `ci-template-contract` delta with two additions (`ci-tpl-01`,
  `ci-tpl-02`).
- [x] 1.2 `openspec validate --all --strict` at the CI pin
  (`@fission-ai/openspec@1.14.3`) — 58/58 passed; the change validated after one
  requirement body was shortened below the strict length ceiling.

## 2. Implementation

- [x] 2.1 `templates/github-workflows/secret-validation.yml` installs the
  scanner into `$RUNNER_TEMP/bin` and appends it to `$GITHUB_PATH`; the SETUP
  header states the rootless constraint and names the measured failure.
- [x] 2.2 `templates/github-workflows/drift-scan.yml` emits `runner_json` (a
  JSON array) from the resolution step and the scan job consumes it with
  `fromJSON`; flow sequences are split, expressions skipped, alternatives are
  not merged, empty resolves to `ubuntu-latest`.

## 3. Tests

- [x] 3.1 `tests/test_secret_validation_template.py` — executed: the fetched
  scanner lands under `$RUNNER_TEMP/bin` and `$GITHUB_PATH`, and
  `/usr/local/bin` appears nowhere in the install arguments.
- [x] 3.2 `tests/test_drift_scan_template.py` — executed against fixtures:
  flow sequence, expression-shaped value, no declaration, and several
  alternatives; plus the scan job's `runs-on` is `fromJSON` of the emitted
  array.
- [x] 3.3 The framework suite passes locally (2044 passed; the one remaining
  failure before the pinned `tsx@4.23.15` was installed for the pi carrier was
  the environment gap CI's install step closes) and in the framework's own CI.

## 4. Evidence

- [ ] 4.1 Consumer-side evidence: a run of the adopted workflows on the fleet
  runner, recorded here by run id once the change lands.
