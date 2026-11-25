# Tasks

## 1. Reconcile the status records

- [x] 1.1 Compare the OI-003 ledger row and historical triage date with the prior dormant-set decision and 2026-11-25 owner scope; preserve the historical records.
- [x] 1.2 Confirm the synthetic validator/report is not a real restore drill and keep the real restore prerequisite before any gate depends on an adopted instance.

## 2. Record the owner decision

- [x] 2.1 Record the 2026-11-25 owner scope: live restore acceptance is optional after explicit GitLab adoption. Append a `not-actionable` triage row with no `review_by`; preserve GLF-10 as an unchecked, adoption-triggered task without requesting private information.
- [x] 2.2 Verify no live restore proof is claimed, run the aging gate, and run pinned strict OpenSpec validation. The aging gate reports 3 aged items triaged, 0 expired deferrals; OpenSpec 1.14.3 validates the current tree.
