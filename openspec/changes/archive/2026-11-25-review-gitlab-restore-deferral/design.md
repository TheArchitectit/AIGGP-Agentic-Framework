# Design

## Context

See proposal.md for the review scope. OI-003's triage row says “blocked on OI-001,” while the `add-gitlab-forge-support/tasks.md` 2026-11-18 dormant-set note groups GLF-10 with owner-deferred conditions that activate only if GitLab is adopted. The existing task also says no real instance backup/restore drill has run; a synthetic report and validator do not satisfy that proof requirement.

## Goals / Non-Goals

**Goals:** Record that a real restore drill is optional acceptance after GitLab adoption and remains mandatory before any gate depends on the selected instance.

**Non-Goals:** Select an instance, contact it, request a backup or restore report, change dates, or declare the restore requirement satisfied.

## Decisions

- Use the supported `not-actionable` state with `recorded: 2026-11-25` and no `review_by`; the aging gate requires a future review date only for `deferred`.
- Append the new triage row and preserve the historical row and expired review date.
- Keep OI-003 unchecked and GLF-10 open until explicit GitLab adoption. A real backup restore remains required before any gate depends on the selected instance.
- Keep endpoint, backup location, and authentication details outside this package; the review is disposition-only.

## Risks / Trade-offs

- The disposition records current product scope but does not establish instance adoption or complete a live restore drill.
- The local validator and synthetic tests can establish input readiness only; they do not prove a live restore drill.
