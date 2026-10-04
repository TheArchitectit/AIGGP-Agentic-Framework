# Capability: OAP Evidence Consumer Contract

## Purpose

Define a narrow, result-preserving adapter between AIGGP/DevGate coherence
evidence and an OAP authority. AIGGP produces verifiable evidence; OAP decides
whether it is required and independently authorizes effects.

## Requirements

### Requirement: Exact DevGate evidence binding
<!-- id: coh-oap-01 -->
An OAP consumer SHALL verify the DevGate artifact's tenant/project, exact
subject digest, package/policy/context digests, evaluator/image identity,
canonical decision, evidence-manifest digest, attestation, signer validity,
and freshness against independently approved context before use.

#### Scenario: wrong candidate
- **WHEN** a valid PASS artifact for subject D1 is presented for D2
- **THEN** OAP rejects it and no operation is authorized

### Requirement: Faithful status mapping
<!-- id: coh-oap-02 -->
The adapter SHALL preserve native decision, exit/error class, assertion states,
producer identity, and evidence references. ERROR, FAIL, SKIP, UNKNOWN,
INCONCLUSIVE, and ADVISORY SHALL NOT be strengthened to mandatory PASS. Replay
is non-promotion-authorizing unless current policy explicitly re-attests it.

#### Scenario: evaluator error
- **WHEN** DevGate returns an evaluator error or incomplete execution
- **THEN** OAP records non-PASS and applies its own deny/queue/exception policy

### Requirement: OAP remains effect authority
<!-- id: coh-oap-03 -->
A DevGate artifact SHALL never grant an OAP principal, tenant, role, scope,
credential, action, resource, exception, or effect permission. OAP SHALL derive
and authorize those values independently at the effect boundary.

#### Scenario: signed PASS with native denial
- **WHEN** a verified DevGate PASS exists but OAP action authorization denies
- **THEN** the effect is denied; evidence is retained only as an attributable
  input/result

### Requirement: OAP-to-DevGate evidence remains attributed
<!-- id: coh-oap-04 -->
If DevGate consumes an OAP result, it SHALL preserve OAP producer/version/native
status, exact subject/request binding, policy/configuration digest, evaluator
identity, and evidence reference. The result SHALL be an explicit assertion
input under DevGate policy, not a replacement for DevGate coherence evaluation.

#### Scenario: unexercised OAP library
- **WHEN** an OAP result comes from an unregistered or unexercised library path
- **THEN** DevGate records unavailable/library-only/non-PASS status and does not
  fabricate a passing assertion

### Requirement: Direction-specific authorization
<!-- id: coh-oap-05 -->
Each adapter direction SHALL have an independent audience, credential, action
scope, expiry/revocation policy, and audit identity. Adapter credentials SHALL
not mutate policy, trust roots, required checks, adoption stage, exceptions,
roles, or signing keys.

#### Scenario: opposite direction credential
- **WHEN** a Guardrails/OAP submission credential is used to retrieve or mutate
  DevGate policy
- **THEN** authorization denies before data access or side effects

### Requirement: Artifact-first and bounded delivery
<!-- id: coh-oap-06 -->
The first implementation SHALL support deterministic protected artifact/CLI
exchange with bounded size, redaction, expiry, idempotency, duplicate handling,
and offline verification. A network service requires a separate operational
approval and SHALL use encrypted transport, audience-bound workload identity,
rate limits, timeouts, and explicit outage behavior.

#### Scenario: online service unavailable
- **WHEN** a later online delivery endpoint is unavailable
- **THEN** the consumer applies the approved deny/queue/exception policy and
  never creates a stale or synthetic PASS

### Requirement: End-to-end conformance before mandatory use
<!-- id: coh-oap-07 -->
Before a result can satisfy any mandatory OAP or promotion gate, tests SHALL
exercise the real producer, artifact/transport, verifier, mapping, and consumer
path. Tests SHALL cover tamper, wrong subject, wrong policy/evaluator, replay,
expiry, revoked signer, missing/error/skipped result, unsupported schema,
unknown critical field, cross-tenant denial, payload bounds, redaction, and
status laundering.

#### Scenario: observe-only pilot
- **WHEN** the contract passes conformance but mandatory owner approval is absent
- **THEN** output remains advisory/observe-only and cannot authorize an effect,
  merge, release, or policy mutation
