# Design: consumer evidence boundary

## Context

The published `evidence-and-attestation`, `decision-contract`, `evaluation-context`, `adoption-and-policy`, and `integrations` capabilities already define evidence binding, canonical decisions, trusted policy context, and promotion semantics. The OAP evidence v2 pipeline is explicitly observe-only. This proposal adds the missing consumer-runtime responsibility boundary; it does not replace or extend those wire formats.

A DevGate check can establish only what its declared subject, inputs, policy, evaluator, and execution surface allow it to establish. A passing evaluator result is evidence for a consumer decision, not permission to deploy, call a tool, or write to an external system. The consuming application owns the required check set, trusted tenant/tool context, route coverage, and final authorization.

## Decisions

- **Reuse existing contracts.** Consumers validate the currently supported versioned decision/evidence contracts and their bindings. This change defines no new protocol, schema, identity issuer, or trust root.
- **Bind every mandatory result.** The consumer checks that required evidence names the immutable subject and source provenance it is about to act on, along with the supported contract/evaluator identity and a valid result. A changed subject, unsupported version, missing provenance, or unverifiable binding is not a pass.
- **Keep advisory and mandatory paths distinct.** Advisory mode may report a finding, unavailable check, or uncertainty, but does not itself authorize an effect. In a consumer-declared mandatory path, unavailable, missing, skipped, failed, stale, or mismatched required evidence fails closed before the effect. Only the consumer's trusted policy makes that path mandatory.
- **Keep authority with the consumer.** Tenant and tool context comes from a consumer-controlled trusted source as opaque references, not from repository text, prompts, agent claims, ambient environment, or evaluator output. The evaluator cannot issue or broaden effect grants.
- **Make coverage claims bounded.** The consumer declares which entry points and effects invoke the required checks. An unintegrated or unverified route remains unsupported; a local integration cannot claim universal interception across a client platform.
- **Minimize retained evidence.** Use existing redacted evidence and digests. Do not persist raw prompts, credentials, or unrelated subject content as consumer proof.
- **Test without external effects.** Exercise allow, deny, unavailable, and mismatch paths against local fixtures and a fake effect sink that records zero external writes.

## Non-goals

- Replacing DevGate's existing canonical decision, evidence manifest, attestation, evaluation context, policy, or OAP formats.
- Claiming that a guardrail intercepts every client event, prompt, tool invocation, or deployment path.
- Selecting a tenant identity system, tool catalog, enforcement product, or mandatory policy for consumers.
- Requiring optional GitLab, runner, or client integrations to be adopted.
- Storing prompts, secrets, or production request contents in evidence.

## Dependencies and ownership

The evaluator owner maintains the supported result contracts and produces evidence. The consumer owner selects required checks, supplies trusted context, verifies bindings, defines coverage, and authorizes effects. Consumer delivery qualification remains in `qualify-consumer-delivery-evidence`; this package addresses runtime evidence and effect authority rather than runner qualification or artifact promotion rehearsal.