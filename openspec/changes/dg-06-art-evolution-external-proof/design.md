# Design

## Context

See proposal.md. The extension guide describes this as a human obligation and states per-game content is out of scope. The registry is append-only; the traceability gate treats markers as locators, not semantic proof.

## Goals / Non-Goals

**Goals:** preserve the process requirement while making responsibility and external evidence scope explicit.

**Non-Goals:** automate human art judgment, assert any game build is shipped, or mark the requirement code-covered.

## Decisions

- A disposition record for an actual failure class includes registry entry ID, affected requirement(s), owner, whether the prevention is local or external, and a direct evidence reference.
- External consumer outcomes require evidence from the consumer repository (commit, test/build result, target); a local guide or synthetic fixture is not accepted. Missing evidence is `NOT_RUN`.
- Where no executable enforcement site exists, keep `art-evolve-01` source-uncovered. Existing requirement identity remains unchanged.

## Risks / Trade-offs

- [A registry entry may expose private project details] -> record only the public failure class and evidence pointer; keep private operational data in its owning repository.
- [Human review can be skipped] -> preserve explicit unproven/NOT_RUN disposition and named owner rather than infer completion.

## Migration Plan

Review extension procedure, identify a real human-reviewed registry event if available, otherwise record NOT_RUN. Collect external owner/build evidence only from the actual consumer. Keep canonical source marker absent where no code enforces the human obligation.
