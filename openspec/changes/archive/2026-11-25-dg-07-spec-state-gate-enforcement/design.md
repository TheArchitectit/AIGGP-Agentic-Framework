# Design

## Context

See proposal.md. The current workflow runs on `push` to `main` and labels itself detection-only. The local hook documents `--no-verify` as a bypass. Remote branch protection is owner-managed configuration unavailable in a local checkout.

## Goals / Non-Goals

**Goals:** make the enforcement claim auditable and time-bound.

**Non-Goals:** change enforcement, infer remote settings, or add markers to YAML/prose as if they were code sites.

## Decisions

- Use a reviewed disposition record with workflow path/event/ref timing, hook path/bypass, default branch name, protection source and capture time, reviewer, and classification of each control.
- For unavailable host settings, record UNKNOWN/NOT_RUN and what permission/source is missing. Do not infer unprotected or protected state.
- Keep `spec-state-09` unchanged in identity; source coverage remains absent unless an actual enforcement site is supported by the traceability scanner.

## Risks / Trade-offs

- [Branch rules drift] -> timestamp and identify source of the readback; reassess after policy changes.
- [Reviewer overstates a push check] -> explicitly categorize push workflow as after-the-fact detection and local hook as bypassable prevention.

## Migration Plan

Inspect local workflow/hook, obtain read-only host protection evidence if authorized, compare public claims, then record a disposition; document any correction without modifying remote controls.
