# Define the consumer evidence boundary

## Why

DevGate and guardrail evaluators produce decisions and evidence, but they do not observe every consumer runtime surface or own the consumer's authorization policy. A consumer that uses these results needs an explicit boundary between checking a subject and authorizing an effect. Existing contracts cover evidence integrity, decision semantics, trusted evaluation context, and CI promotion; this change defines how a consuming application applies those contracts to its own tool and runtime surfaces without claiming universal interception.

## What Changes

- Define a consumer-owned contract for invoking required checks and validating their versioned results against the exact immutable subject and provenance.
- Keep advisory reporting distinct from mandatory fail-closed decisions; missing, unavailable, skipped, stale, or mismatched required evidence cannot authorize an effect.
- Require trusted, opaque tenant and tool context from the consumer's authority, and keep authorization of deployment, tool use, and other effects outside the evaluator.
- Limit evidence to the existing minimal-disclosure formats; raw prompts, credentials, and unrelated source content are not retained as proof.
- Specify hermetic acceptance cases for allowed, denied, unavailable, and mismatched evidence without external system writes.

## Capabilities

### New Capabilities

- `consumer-evidence-boundary`: consumer responsibilities for invoking and interpreting evaluator evidence without granting runtime authority to the evaluator.

### Modified Capabilities

None. This proposal reuses the published evidence, decision, context, policy, and integration contracts; it introduces no evidence schema, evaluator protocol, or authorization service.

## Impact

Planning and consumer-integration contract only. It does not change DevGate evaluator behavior, the OAP observe-only pipeline, runner/forge adoption conditions, or any consumer's production authorization policy. Optional integrations remain optional and must be named as such.