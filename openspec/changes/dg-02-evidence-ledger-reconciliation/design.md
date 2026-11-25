# Design

## Context

See proposal.md. The baseline has 182 rows in `state-unproven.jsonl`. Existing requirements `spec-state-01` through `spec-state-08` define commit bounds, source location, sealing, and preserving unprovable claims.

## Goals / Non-Goals

**Goals:** individually review the full roster and make each conclusion reproducible and tamper-evident.

**Non-Goals:** weakening proof requirements, bulk-promoting claims, rewriting history, or introducing lifecycle states.

## Decisions

- Preserve the original `state-unproven.jsonl`; produce a separate JSONL inventory with one row per reviewed spec/requirement, outcome, proof conjuncts, evidence digests, reviewer and timestamp.
- Seal the inventory and supporting evidence with the repository's existing evidence format and validator. A hash alone is insufficient proof; the existing validator remains authoritative.
- Keep missing proof explicit. A `proved` disposition authorizes consideration of a ledger transition but does not itself close a requirement.
- Reconcile in reviewable batches and verify every source row occurs exactly once.

## Risks / Trade-offs

- [Historical evidence is absent] -> preserve UNPROVEN and name the absent conjunct.
- [Large report is hard to inspect] -> provide stable row keys and a sealed manifest per batch, plus an aggregate roster digest.

## Migration Plan

Extract the 182-row baseline, review evidence, write separate dispositions, seal and validate the artifact, then append only evidence-qualified ledger transitions and update closures. Rerun the state gate and generated index check. Do not edit old ledger or roster rows.
