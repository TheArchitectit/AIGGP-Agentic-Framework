# Reconcile upstream AIGGP pull requests

## Why

This coordination change records the November 25–26, 2026 review and merge
history for upstream AIGGP pull requests #32, #33, and #46–#49. The November 25
intake snapshot had conflicts on #32/#33 and an initial failed workflow receipt
on #48. Those are historical states; all six requests were merged by November
26 UTC after their applicable evidence and checks were reviewed.

## What changes

- Preserve intake ancestry, changed-file scope, and initial exact-head check
  receipts.
- Record the reconciliation and final CI evidence for #32 and #33.
- Track the separate review boundaries for #46, #47, and #48, including both
  initial failures and later successful receipts.
- Record #49's public readiness audit and its final merge receipt.
- Keep release decisions and publication in DG-22, outside this PR integration.

## Final disposition

- **#32:** reconciled the archived package; the related capability remains
  `UNPROVEN`.
- **#33:** retained the historical blocker; later owner decisions govern
  GitLab adoption and scope.
- **#46:** records an approved-release plan only; it does not execute or publish
  a release.
- **#47:** records candidate provenance only; all 182 `UNPROVEN` dispositions
  remain unchanged, with row evidence and sealing tracked separately.
- **#48:** fixes test-process launch handling; its initial receipt failed, then
  its updated exact-head workflow passed before merge.
- **#49:** carries the public readiness audit and proposed OpenSpec changes.

## Impact

Coordination artifacts only. No upstream capability or requirement changes.
There is no spec delta because this change defines no new product behavior or
upstream policy.
