# Design

## Context

See proposal.md for the expired review and its scope. `docs/open-items-ledger.md` and `docs/open-items-triage.jsonl` record OI-001 as deferred with `review_by` 2026-11-22. `add-gitlab-forge-support/tasks.md` preserves the 2026-11-15 owner decision that GitLab remains an option and live instance work is dormant until adoption.

## Goals / Non-Goals

**Goals:** Record the owner's confirmed scope (GitLab support alongside GitHub) and preserve the real-instance task as conditional acceptance after explicit adoption.

**Non-Goals:** Perform instance discovery, request or store endpoint/auth details, contact a server, change historical dates, or activate live work by default.

## Decisions

- Use the supported `not-actionable` triage state for the current product-scope decision, with `recorded: 2026-11-25` and no `review_by`. The aging checker accepts this state without a review date; it requires a future `review_by` only for `deferred`.
- Append the new triage row so the prior 2026-11-15 record and expired 2026-11-22 date remain historical evidence. The loader uses the latest row for each ID.
- Keep the original OI-001 checklist row unchecked and keep Sprint 0 open. Explicit GitLab adoption is the trigger to re-triage and complete operator acceptance.
- Keep private endpoint values, internal aliases, and credentials out of all artifacts. This decision does not assert current reachability or adoption.

## Risks / Trade-offs

- The disposition does not state a new instance exists or clear the operator task; it removes the expired deferral from the current aging decision while preserving the conditional task.
- The former discovery notes are historical evidence only and do not establish current network reachability.
