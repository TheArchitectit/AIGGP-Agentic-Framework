# Design

## Context

See proposal.md. `spec-fmt-01` already requires CLI and marker agreement, but the current marker parser recognizes 243 IDs among 251 canonical headings. The strict CLI validates structure but does not enforce the repository's ID-comment convention.

## Goals / Non-Goals

**Goals:** compare the same canonical requirement set across both tools; make heading-to-ID errors actionable; preserve every existing valid identity.

**Non-Goals:** create implementation markers for unrelated requirements, change OpenSpec's format, or promote any requirement state.

## Decisions

- Treat each `### Requirement:` heading in a published spec as one inventory entry. Require one valid ID in its requirement block and reject empty, ellipsis, duplicate, or otherwise unsupported tokens in parser fixtures; the literal examples in current prose are not requirement markers. Alternative considered: count only comments as today; rejected because missing headings remain invisible.
- Reconcile parsed IDs by capability against `openspec list --specs` counts plus requirement IDs extracted from full `openspec show <capability> --type spec --json` output. Report missing, extra, duplicate, and malformed entries separately. A successful CLI run alone is insufficient.
- Assign stable new IDs only after searching source markers, archived deltas, tests, and documentation for existing candidate references. Do not attach a requirement to code without verifying its enforcement role.
- Keep strict CLI validation and the negative malformed-control test in CI; add the identity completeness check adjacent to traceability.

## Risks / Trade-offs

- [Renumbering can strand references] -> preserve all valid IDs and add only the eight missing ones; enumerate reference updates before changing any ID.
- [Parser disagreement can produce false green] -> compare capability and ID sets, and include fixture cases for zero, malformed, duplicate, and missing IDs.

## Migration Plan

Inventory references, assign IDs to the eight unmarked headings, retain the literal prose examples, add the comparison gate and negative controls, run strict validation and traceability, then archive only after review. Rollback reverts the gate and additions together; existing valid IDs stay untouched.
