# Design

## Context

The verifier currently parses manifest lines into a path-to-digest mapping.
Dictionary assignment silently replaces earlier entries, and digest syntax is
not checked before that assignment. A duplicate path can therefore conceal an
invalid row.

## Goals / Non-Goals

**Goals:** fail closed on malformed SHA-256 text and repeated normalized paths;
retain existing path selection, digest comparison, and diagnostics.

**Non-Goals:** change checksum generation, the tracked file inventory, manifest
format, or unrelated CI behavior.

## Decisions

- Parse and validate each digest as exactly 64 hexadecimal characters before
  recording it.
- Normalize manifest paths with the verifier's existing safe path rules and
  reject a repeated normalized path before any mapping overwrite.
- Test duplicate valid rows, malformed digest rows, and malformed duplicate
  followed by valid rows using temporary one-script Git repositories.

## Risks / Trade-offs

- [Existing manifest has an undocumented duplicate] -> run the verifier and
  inspect the canonical manifest before changing behavior.
- [Path aliases bypass duplicate detection] -> compare the normalized path key
  actually used by verification.

## Migration Plan

Add tests, implement validation, run focused verifier tests and the canonical
manifest verifier, then regenerate only if final tracked script bytes changed.
