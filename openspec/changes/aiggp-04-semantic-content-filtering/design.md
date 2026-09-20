## Design principles

- Named classifiers only: a filter decision without classifier identity is not evidence.
- Declared failure modes: every category states what wrong looks like in both directions.
- Bundle-pinned versions: behavior changes are digest changes.
- Auditable redaction: removed content is hashed into evidence; nothing vanishes.

## Locked decisions

- Core category set at launch: secrets/credentials, personal data, licensed/copyrighted material, explicit content. Extensions require the full category package (corpus, failure modes, budget).
- Action set per category: allow, redact, block, escalate. Defaults are conservative at send/commit boundaries.
- Confidence handling: thresholds are bundle parameters; sub-threshold classifications at enforcement boundaries default to escalate, not allow.
- Classifier identity: provider, model, version, and quantization/runtime where applicable, all recorded per decision.
- Evidence minimization: envelopes carry hashes and category metadata, not raw sensitive content.

## Major components

1. Category registry (bundle-defined, versioned).
2. Classifier adapters (pluggable, identity-stamped).
3. Mediation wiring shared with AIGGP-03 boundaries.
4. Redaction engine with hashed audit trail.
5. Corpus runner per category (detection and false-positive suites).
6. Drift monitor: scheduled corpus re-runs alerting on behavior change.

## Trust boundaries

- Classifier adapters are untrusted versioned components; identity is verified against the bundle pin.
- Evidence never contains raw sensitive payloads; hashes allow after-the-fact verification without disclosure.
- Escalation responses arrive through authorized channels only (no content-driven override - consistent with AIGGP-03).
