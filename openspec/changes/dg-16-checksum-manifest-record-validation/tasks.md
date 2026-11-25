# Tasks

## 1. Specify and implement record validation

- [x] 1.1 Add focused tests using disposable single-script Git repositories
  for malformed digest, duplicate valid record, and malformed duplicate then
  valid record.
- [x] 1.2 Reject malformed SHA-256 digests and duplicate normalized paths
  before storing records in the verification mapping.
- [x] 1.3 Run focused tests and verify the canonical shipped manifest passes;
  three focused regressions passed and the LF-normalized 160-entry candidate
  manifest verified successfully.

## 2. Candidate verification

- [ ] 2.1 Run pinned OpenSpec strict validation and the repository test suite.
- [ ] 2.2 Independently review the implementation and test evidence.

## Workflow follow-up

Archive after strict validation, focused and repository tests, manifest
verification, and independent review pass.
