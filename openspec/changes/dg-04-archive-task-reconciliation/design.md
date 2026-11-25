# Design

## Context

See proposal.md. The audit found 43 archive directories and 719/829 checkbox tasks checked. Historical archives include known migration/disposition notes, so a checkbox-only classification would lose context.

## Goals / Non-Goals

**Goals:** retain original historical state and publish a separately reviewable task-to-evidence mapping.

**Non-Goals:** rewriting old tasks, treating every unchecked task as live, or asserting implementation from a checked box.

## Decisions

- Assign a new reconciliation ID to each archived task whose checkbox remains unchecked and to each completed delta capability without a clear canonical successor. IDs live only in the reconciliation artifact and successor work, never retroactively in archive task files.
- Use dispositions `implemented`, `superseded`, `deferred`, `retired`, `still-open`, or `unsubstantiated`; each requires a rationale and source pointer. `implemented` requires code/test evidence; checked state alone is insufficient.
- Map `still-open` tasks into new active changes with fresh task IDs and owner; preserve historical unchecked boxes.
- Reconcile archive delta names against current spec paths and Git history. Keep records of moved packages and distinguish cross-repository transfer from publication here.

## Risks / Trade-offs

- [False completion from archive checkboxes] -> require independent code/test pointers.
- [Large inventory difficult to review] -> batch by archive date and publish stable IDs with per-row rationale.

## Migration Plan

Generate the 829-row source roster, select all unchecked and unmapped delta tasks, reconcile against history/spec/source/test evidence, create successor tasks only for substantiated outstanding work, and validate that historical archive text is unchanged.
