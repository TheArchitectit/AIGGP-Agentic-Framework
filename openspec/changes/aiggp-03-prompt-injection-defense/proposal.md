## Summary

Add direct prompt-injection defense to the Guardrails runtime module: classification of inbound instructions and content against injection patterns, mediation (block, sanitize, escalate) at command/edit/git/action boundaries, and evidence emission per decision, proven against an adversarial conformance corpus before any verified maturity claim.

## Problem

Agent-operated workflows read untrusted content constantly - web pages, emails, tickets, documents - and that content can contain instructions aimed at the agent, not the human. An agent that cannot tell "content I am processing" from "orders I must follow" is one poisoned page away from acting for an attacker. Guardrails main v3.7.1 has runtime validation and mediation surfaces, but injection defense is not yet proven against an adversarial suite, and the platform rule is: unproven is proposed, full stop.

## Desired outcomes

- Every instruction-bearing input crossing a mediation boundary is classified: user-authorized instruction, content data, or suspected injection.
- Suspected injection is mediated per policy: block, sanitize-and-continue with disclosure, or escalate for human decision.
- Every decision emits an AIGGP evidence envelope: subject (runtime action, agent, session), bundle digest, classifier version, raw classification, verdict.
- A versioned public adversarial corpus proves detection: direct injection, instruction-in-content, encoded payloads, multi-turn setup, authority impersonation, exfiltration lures.
- False-positive budget declared per deployment; classification is tunable only through the bundle, never ad hoc.

## Product boundary

This spec covers direct prompt injection and instruction-in-content at runtime mediation boundaries. Indirect-injection provenance (origin chains for content) is AIGGP-06; sandbox containment after a decision is AIGGP-05. The classifier is a module capability: it can never redefine verdict truth, and its output annotates kernel evidence rather than replacing it.

## Users and calling systems

- The Guardrails Go MCP server mediating agent actions.
- IDE and agent-loop transports carrying instructions and content.
- Operators tuning policy through bundle parameters.

## Success measures

- Adversarial corpus pass rate at or above the declared bar per category, with every miss recorded as a finding.
- False-positive rate at or below the declared budget on a benign corpus.
- 100 percent of mediation decisions emit valid envelopes verifiable offline.
- Conformance is repeatable by a third party: corpus plus pinned bundle plus module version reproduces the result.

## Risks

- Overclaiming detection capability (the classic security-product failure). Control: no verified label without corpus evidence; misses published, not buried.
- Classifier becomes a single point of trust. Control: defense in depth - classification informs mediation; sandboxing (AIGGP-05) limits blast radius; provenance (AIGGP-06) reduces what reaches the classifier as "trusted."
- Arms race against adaptive attackers. Control: corpus versioning and scheduled red-team refresh are part of the spec, not goodwill.
