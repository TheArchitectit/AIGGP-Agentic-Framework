# Design

## Context

See proposal.md for the expired review and its scope. `docs/open-items-ledger.md` and `docs/open-items-triage.jsonl` record OI-001 as deferred with `review_by` 2026-11-22. `add-gitlab-forge-support/tasks.md` preserves the 2026-11-15 owner decision that GitLab remains an option and live instance work is dormant until adoption.

## Goals / Non-Goals

**Goals:** Give the owner an auditable local review point that captures current adoption status and the next authorized trigger.

**Non-Goals:** Perform instance discovery, request or store endpoint/auth details, contact a server, change historical dates, or activate live work by default.

## Decisions

- Keep this package independent of the dormant Sprint 0 implementation tasks; it reviews their owner disposition only.
- Accept either an owner-confirmed dormant state or an explicitly authorized activation decision. Do not infer which one is current.
- Describe the next trigger as an authorization event, such as an owner-approved adoption request, rather than inventing a new calendar date.
- Keep private endpoint values, internal aliases, and credentials out of all artifacts. The review uses only the existing local owner-decision record.

## Risks / Trade-offs

- The review package does not itself reset the expired triage date or clear the aging gate; any disposition change requires a separately authorized owner action.
- The former discovery notes are historical evidence only and do not establish current network reachability.
