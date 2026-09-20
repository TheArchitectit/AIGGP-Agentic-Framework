## Design principles

- Fail closed, always: a broken sandbox is a stopped workload, not a best-effort one.
- Declared, not implied: the level is in the bundle and in the evidence.
- Least privilege by default: a workload gets exactly its declared rights; elevation is a bundle change.
- Ephemerality where it counts: the strongest levels are also the most disposable.

## Locked decisions

- Four levels: observer (read-only, no network, no secrets), restricted (scoped write, default-deny network, no secrets), contained (full workload in isolated container, declared egress only, declared secret classes), ephemeral (contained plus fully disposable host state, short-lived credentials).
- Default-deny network at every level; egress allowlists are bundle declarations.
- Secret access is by declared secret class (aligned with AIGGP-09); no level grants ambient credential access.
- Containment faults (seccomp/namespace/mount/runtime errors) map to ERROR verdicts with evidence.
- Conformance escape fixtures are versioned and public, like the injection corpus.

## Major components

1. Level definitions and capability matrix (published, versioned).
2. Runtime enforcers per backend (container, process isolation) mapping levels to mechanism.
3. Refusal path: workloads whose declared level cannot be enforced on the host do not run.
4. Fault detector translating containment errors into ERROR evidence.
5. Escape-fixture suite in CI.
6. Envelope field plumbing for level and runtime identity.

## Trust boundaries

- The enforcer trusts no workload declaration it cannot enforce: declaration is a request, enforcement is fact.
- Host capability detection is verified at startup; a host silently lacking a mechanism downgrades to refusal, not to weaker enforcement.
