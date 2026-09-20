## Summary

Deliver the spec-coherence service as an AIGGP module: deterministic evaluation of a repository against its pinned OpenSpec package, per-project coherence history, an advisory-to-enforced adoption ladder, and attested evidence emitted in the AIGGP-00 envelope format.

## Problem

Specs and code drift apart silently across the fleet. Each repo's OpenSpec says one thing, the code does another, and nobody finds out until an audit. Roger's September 17 idea: DevGate already has a fleet runner for CI - run it as a container in an environment and gate OpenAPI/OpenSpec coherence for every repo over time. The design was delivered the same day; what it lacks is integration into the platform truth model, so its results would be yet another report nobody can verify.

## Desired outcomes

- Every fleet repo gets a deterministic coherence evaluation against its pinned spec package on a schedule and on demand.
- Results are AIGGP evidence envelopes: subject digests, bundle digest, module version, verdict per the platform algebra.
- Per-project history shows drift over time, queryable from the ledger.
- Adoption is laddered: inventory, advisory baseline, ratchet, enforced core, enforced full - never day-one blocking.
- The promote/halt contract serves the AI 3D design pipeline's candidate evaluation with the same machinery.

## Product boundary

The service evaluates coherence between declared specs and repository state; it does not repair source, rewrite specs, or decide release policy beyond its gate verdict. The evaluator never edits the repo. Nondeterministic advice (LLM or vision review) may annotate but can never set the blocking verdict.

## Users and calling systems

- Fleet CI executing the container against each repo.
- The AI 3D design pipeline consuming promote/halt verdicts for asset candidates.
- Mission Control reading coherence history from the ledger (read-only).
- Project owners climbing the adoption ladder per repo.

## Success measures

- Repeated evaluations of the same revision produce identical verdicts (determinism proof in CI).
- Every emitted result validates against the AIGGP-00 envelope schema and lands in the ledger.
- A repo can climb from Stage 0 to Stage 3 using only recorded ladder transitions, each with evidence.
- The 3D pipeline consumes a promote/halt verdict from a real run without custom glue.

## Risks

- Nondeterminism creeps in through evaluators that read clocks, network, or environment. Control: the deterministic execution contract from the September 17 package, plus fixture E (nondeterministic evaluator must fail conformance).
- Day-one blocking breeds resentment and workarounds. Control: the ladder is normative; skipping stages requires a waiver.
- The service becomes a second source of truth alongside the kernel. Control: it emits envelopes; aggregation and verdicts follow AIGGP-00.
