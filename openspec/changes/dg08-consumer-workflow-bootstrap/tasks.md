# Tasks

## 1. Implementation and verification

- [ ] 1.1 Update `drift-scan.yml`, `specs.yml`, and `text-integrity.yml` so every job that executes `.devgate/` provisions the consumer-owned full SHA before invoking gates; leave already self-bootstrapping `spec-coherence.yml` and workflows without runtime DevGate calls in their existing scopes.
- [ ] 1.2 Test each affected workflow's extracted bootstrap and job-specific required-file list against local bare fake-approved-source repositories at fixture SHAs, with no `.gitmodules` and no network access.
- [ ] 1.3 Add hermetic malformed SHA, wrong commit/root, incomplete clone, missing workflow-specific script/data, tracked path, and dirty/untracked reuse controls; verify every failure prevents gate execution and emits no green marker.
- [ ] 1.4 Preserve job-specific runtime requirements, including the text-integrity full-history range scan; retain action pins, permissions, runner selection, dependency versions, and named gate scope.
- [ ] 1.5 Reconcile wiring/onboarding docs and confirm the directory-wide scan found no other runtime workflow that invokes `.devgate/` without an existing bootstrap.
- [ ] 1.6 Run focused template tests, the repository suite and test-floor check, pinned OpenSpec validation, and the writer gates; record exact source revision and results.
