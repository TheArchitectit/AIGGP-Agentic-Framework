# Tasks

## 1. Specify and implement Unicode-safe tracked-path inventory

- [x] 1.1 Use binary `git ls-files -z` records; select supported script suffixes without depending on Git quoting; preserve exact valid UTF-8 paths independently of `core.quotePath` and do not change inventory roots/extensions.
- [x] 1.2 Reject invalid UTF-8, repeated supported paths from unmerged index stages, and manifest-unrepresentable paths (line separators and backslash) before either mode proceeds; share error behavior and preserve an existing manifest on generation failure.
- [x] 1.3 Add disposable-Git tests for ordinary plus `r\\u00e9sum\\u00e9.py` names with `core.quotePath=true`, internal-space path preservation, exact records, and successful verification.
- [x] 1.4 Add separate tracked LF, CR, backslash, U+2028, and invalid-byte candidate fixtures on POSIX; assert the specific failure in both modes and no manifest mutation. Add a noncandidate final-suffix newline control and an unresolved three-stage Git index control on both hosts.
- [x] 1.5 Run focused checksum suites (Windows: 5 tests with the POSIX test skipped; Linux: 6 tests), canonical LF generator verification, strict OpenSpec validation and `git diff --check`; regenerate `CHECKSUMS.sha256` for final tracked script bytes. Regenerated `tests/expected-counts.json` from 2,082 tests in 143 suites.

## 2. Candidate verification and independent review

- [ ] 2.1 Verify the final manifest and CI checksum step at the integrated candidate head, including the DG-13 Bash diagnostic regression and DG-16 malformed/duplicate-record controls.
- [x] 2.2 Obtain independent review of path-byte handling, candidate filtering, platform controls, manifest-preservation behavior, and evidence before archive.

## Workflow follow-up

Keep this package active until implementation, exact-head CI, and independent review pass. Do not claim a hosted or release acceptance result from a local fixture run.
