# Design

## Context

See proposal.md for the review scope. OI-002's triage entry is deferred through 2026-11-22 and says live evidence depends on OI-001. The original change records a hermetic five-case drill over real gate subprocesses, pinned corpus version `2026-11-15.1`, and a blocking CI step; it explicitly does not claim two-live-forge parity.

## Goals / Non-Goals

**Goals:** Capture a fresh owner decision on whether live parity remains dormant or is authorized, tied to the latest OI-001 decision, without downgrading the hermetic evidence.

**Non-Goals:** Execute the corpus on a live forge, ask for forge access or outside evidence, update dates, or treat adapter-level equivalence as a two-platform green.

## Decisions

- Read the latest OI-001 decision before recording OI-002's conditional state; if OI-001 has no new decision, preserve that dependency as unresolved rather than assuming adoption.
- Keep hermetic parity evidence and live two-forge readiness as separate claims.
- Record the owner outcome and the event that could authorize a future live review; do not invent a date or live result.

## Risks / Trade-offs

- A fresh decision record does not create the second forge needed for live parity or alter the existing dormant integration state.
- The existing CI drill proves parity across adapter paths over a pinned corpus, not independent execution on two live CI platforms.
