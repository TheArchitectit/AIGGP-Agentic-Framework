# Design

## Context

See proposal.md for the review scope. OI-002's triage entry is deferred through 2026-11-22 and says live evidence depends on OI-001. The original change records a hermetic five-case drill over real gate subprocesses, pinned corpus version `2026-11-15.1`, and a blocking CI step; it explicitly does not claim two-live-forge parity.

## Goals / Non-Goals

**Goals:** Record that two-live-forge parity is optional acceptance after GitLab adoption while preserving hermetic parity as a ship requirement.

**Non-Goals:** Execute the corpus on a live forge, ask for forge access or outside evidence, update dates, or treat adapter-level equivalence as a two-platform green.

## Decisions

- Use the supported `not-actionable` state for the live half with `recorded: 2026-11-25` and no `review_by`; the aging gate requires a future review date only for `deferred`.
- Append the new triage row and preserve the historical row and expired review date.
- Keep the OI-002 backlog row unchecked and the two-live-forge task open until explicit adoption. Keep hermetic parity tests and CI verification separate from live acceptance.
- Do not infer adoption, a second live forge, or a two-platform green result.

## Risks / Trade-offs

- This disposition does not create the second forge needed for live parity or alter the existing dormant integration state.
- The existing CI drill proves parity across adapter paths over a pinned corpus, not independent execution on two live CI platforms.
