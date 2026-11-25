# Tasks

## 1. Review parity status and dependency

- [x] 1.1 Verify OI-002's historical `review_by` date is 2026-11-22 and compare its old triage text with the 2026-11-25 OI-001 scope decision; preserve both historical records.
- [x] 1.2 Confirm the hermetic parity drill runs actual gate subprocesses over the five-case pinned corpus and is invoked in CI; verify no two-live-forge result is claimed.

## 2. Record the owner decision

- [x] 2.1 Record the 2026-11-25 owner scope: live parity is optional operator acceptance after explicit GitLab adoption. Append a `not-actionable` triage row with no `review_by`; preserve the unchecked live task and make no external request.
- [x] 2.2 Run the hermetic template/adapter/interoperability parity tests and direct drill; run the aging gate and pinned strict OpenSpec validation. Windows focused tests pass 23/23 and all five direct cases pass; a Linux candidate copy with shell line endings normalized passes 23/23 and the same five direct cases.
