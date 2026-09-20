## Design principles

- Small and dependency-free relative to modules. The kernel must be auditable by one person in a sitting.
- Content addressing everywhere. Identity is digest, not name plus good intentions.
- No central reinterpretation. Fleet systems distribute, observe, and verify; they never re-decide a verdict.
- Determinism or it did not happen. Same inputs, same bundle, same verdict, same rendered document.

## Locked decisions

- Subject identity: canonical identifiers for repository, revision, change set, artifact, runtime action, agent, workflow, and environment. Each is a typed structure with a digest, not a bare string.
- Bundle identity: the bundle digest covers manifest, policy references, parameters, waiver rules, evidence categories, and rendering metadata. Any change is a new bundle version. Moving references (branch names, latest tags) are invalid inside a bundle.
- Evidence envelope: signed; carries subject digests, bundle digest, module identity and version, capability claimed, raw result, timestamps, and provenance chain. The envelope schema is versioned.
- Verdict algebra: PASS, FAIL, SKIP, ERROR, EMPTY. Aggregation rules are part of the kernel and versioned; no aggregation may collapse EMPTY or ERROR into PASS. SKIP requires a reason code and is auditable.
- Waivers: scoped to subject and control, owned by a named identity, reasoned in text, and expiring. An expired waiver is a FAIL input, not a silent pass. Waivers are ledger entries, not config.
- Ledger: append-only, hash-chained, exportable. The verifier is a standalone binary/script with no module imports.
- Renderer inputs: the kernel defines the deterministic data contract for generated deployment documents; rendering itself is a module/tool, not kernel.

## Major components

1. Schema library: subject, bundle, evidence, verdict, waiver, ledger, module, conformance schemas, versioned together.
2. Bundle builder: deterministic build from structured source; same source, same digest.
3. Verifier: validates envelopes, aggregation, waiver validity, and ledger integrity offline.
4. Conformance kit: canonical valid fixtures and invalid counterexamples per schema; a runner that reports module conformance per claimed capability.
5. Semantic diff: human-reviewable diff between bundle versions (the pre-deploy review surface).

## Trust boundaries

- Modules are untrusted producers: the kernel validates every envelope against schema, digest, signature, and aggregation rules.
- The renderer is untrusted: document regeneration must reproduce from kernel data, so a hand-edited document is detectable.
- Mission Control is a client: it can request runs and host waiver workflows, but waiver objects are validated by the kernel.
