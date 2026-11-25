# Design

## Context

See proposal.md for the review scope. OI-003's triage row says “blocked on OI-001,” while the `add-gitlab-forge-support/tasks.md` 2026-11-18 dormant-set note groups GLF-10 with owner-deferred conditions that activate only if GitLab is adopted. The existing task also says no real instance backup/restore drill has run; a synthetic report and validator do not satisfy that proof requirement.

## Goals / Non-Goals

**Goals:** Let the owner reconcile the current status using local records, tie it to an OI-001 instance/adoption decision, and retain a real restore-drill prerequisite if the owner activates reliance.

**Non-Goals:** Select an instance, contact it, request a backup or restore report, change dates, or declare the restore requirement satisfied.

## Decisions

- Treat the ledger, triage entry, and current owner-decision block as separate records to reconcile; do not silently rewrite “blocked” as “dormant.”
- Accept an owner decision that keeps the item dormant or activates a selected-instance review; do not assume either outcome.
- If activated, preserve the existing rule that a real backup restore must be evidenced before a gate depends on the instance.
- Keep endpoint, backup location, and authentication details outside this package; the review is disposition-only.

## Risks / Trade-offs

- The source records currently use different status language; the package requests owner reconciliation rather than claiming they already agree.
- The local validator and synthetic tests can establish input readiness only; they do not prove a live restore drill.
