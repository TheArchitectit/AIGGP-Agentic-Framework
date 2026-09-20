## Summary

Define and implement the AIGGP enforcement kernel: canonical subject identity, versioned content-addressed policy bundles, signed evidence envelopes, verdict algebra, scoped expiring waivers, an append-only ledger with a standalone verifier, module identity and conformance profiles, and deterministic renderer inputs for generated deployment documents.

## Problem

Today, truth is reinvented per tool. DevGate, Agent Guardrails, and Mission Control each decide what "green" means in their own terms, and the audits showed where that leads: gates reporting success over unscanned work, zero-test runs exiting green, a control plane that centralizes optimism instead of evidence. Without one shared, verifiable truth model, merging the products merges the confusion.

## Desired outcomes

- One verdict algebra across the platform: PASS, FAIL, SKIP, ERROR, EMPTY. EMPTY and ERROR can never aggregate into PASS under any aggregation rule.
- One evidence envelope every module emits, signed, with provenance chain and content digests.
- One policy-bundle format: versioned, content-addressed, carrying manifest and schema version, policy and module digests, parameters, compatibility requirements, waiver rules, required evidence categories, non-empty discovery expectations, signatures, and deterministic rendering metadata.
- One ledger: append-only, exportable, verifiable offline by a standalone verifier with no module dependency.
- A public conformance kit with canonical valid examples and invalid counterexamples, so any module can prove compatibility.
- Deterministic renderer inputs so a generated guardrail document reproduces exactly from bundle plus ledger.

## Product boundary

The kernel owns identity, digests, evidence, verdicts, waivers, ledger, conformance, and renderer inputs. The kernel does NOT parse source languages, classify prompts, operate runners, talk to GitHub or GitLab, or render dashboards. If logic is scanner-, runner-, transport-, forge-, or UI-specific, it is a module. This boundary is the anti-monolith test and it is normative.

## Users and calling systems

- DevGate repository module (emits evidence, consumes bundles and verdicts).
- Guardrails runtime module (same contract).
- Runner modules and forge adapters (enrollment identity, signed state).
- Mission Control (reads ledger and evidence through the public protocol; cannot create verdict facts).
- External adopters running the conformance kit against their own modules.

## Success measures

- DevGate and Agent Guardrails both emit kernel-valid test fixtures without changing their engines (Phase 3 shadow-adapter exit).
- The standalone verifier validates a real ledger export offline and rejects tampered copies.
- A generated deployment document regenerates byte-identically from the same bundle plus ledger.
- A third party can run the conformance kit against a toy module and get a meaningful pass/fail.

## Risks

- Kernel scope creep turns it into the monolith we are avoiding. Control: the boundary test above, applied in review; anything module-shaped is rejected from kernel.
- Schemas so strict that real modules cannot emit them. Control: Phase 3 shadow adapters on one real DevGate gate and one real Guardrails check before any blocking use.
- Readable-vs-structured failure: bundles become unreadable YAML soup and review moves back to prose. Control: readable schema, semantic diff, deterministic preview renderer, stable control IDs.
