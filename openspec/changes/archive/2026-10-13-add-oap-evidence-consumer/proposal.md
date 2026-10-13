# Change: Add OAP Evidence Consumer Contract

> **Status:** Proposed and blocked on OAP native authority readiness. This is
> not a shipped OAP integration, organization enforcement service, or AIGGP
> kernel replacement.

## Summary

Define the narrow AIGGP/DevGate contract for an OAP authority to consume
DevGate canonical evaluation results and for DevGate to accept optional OAP
security evidence as an attributed assertion input. The contract transports
identity-bound evidence; it does not authorize OAP effects, mutate policy, or
make AIGGP the organization authority.

## Scope

- Reuse existing DevGate canonical identity, evaluation context, decision,
  evidence, and detached-attestation semantics.
- Preserve native producer identity and all non-PASS states.
- Add the versioned mapping in `mapping.md` and then implement schema/fixtures;
  the mapping is not complete until those artifacts exist.
- Support artifact/CLI exchange first; defer a network API until a real second
  consumer and operations owner exist.
- Require OAP native authorization/effect gates before any result can be used
  for an OAP mandatory operation.

## Non-goals

- No OAP tenant/grant/credential/effect implementation in AIGGP.
- No Guardrails runtime implementation or receipt-based authorization.
- No retired AIGGP kernel/CA/runner identity package.
- No required-status-check controller, central admin UI, shared DB, or workflow
  that repository content can use to self-approve.

## Dependencies and order

1. OAP native security authority package is implemented and independently
   reviewed for the selected pilot operation.
2. AIGGP canonical evidence contract remains stable and its existing
   verification tests are green.
3. This change adds the adapter and fixtures in observe-only mode.
4. A separate owner decision may promote one exact consumer path to mandatory.

## Ownership

AIGGP owns canonical DevGate decisions, sealed evidence, attestation, and
faithful adapters. OAP owns whether a decision is required and whether an
operation is authorized. OAP must independently derive principal, tenant,
action, target, grant, revocation, and current policy. A valid AIGGP result is
never an OAP permit.
