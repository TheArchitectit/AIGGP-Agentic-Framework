# Sprint plan — DG-02 monitor, scanner, and security gaps

Use the [sprint dispatch guide](../../SPRINTS.md) with this package’s [tasks](tasks.md), [proposal](proposal.md), and [batch 009 review](../dg-02-evidence-ledger-reconciliation/batches/batch-009/README.md).

Exercise the native entry point for this change. A change to session startup or manifest handling also needs a carrier-specific receipt. [Session adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Roles

- Lead: own requirement mapping and review decisions; sign off only after evidence reconciliation.
- Luna: implement/collect controlled tests and prepare redacted row evidence.
- Independent auditor: separate session verifies actual test behavior, outputs, provenance, and bundle validation.
- Accountable owners: monitor maintainer, scanner/gate maintainers, enrollment security owner, template maintainer, and DG-02 evidence owner.

## S1 — intake and baseline

- Treat batch 009 findings as bounded evidence leads: queue alert runner matching/thresholds, schedule-aware drift, and historical template-path gap.
- Map tasks 1.1–1.4 to `mon-online-01`, `mon-queue-01`, `mon-gates-01`, `mon-drift-01`; tasks 2.1–2.5 to marker/scanner, `coh-sec-01`, `mon-sec-01..02`, `ci-sec-01`; task 2.6 to row evidence.
- Capture current source/test locations, exact template path, current duplicate-enrollment outcomes, and secret-safe test logging constraints.
- Exit when each scenario has an owner and a testable fixture, with live-monitor access dependencies called out separately.

## S2 — implementation and evidence

- Tasks 1.1–1.4: qualify API-offline versus heartbeat staleness, label-aware queue alerts and thresholds, latest gate results/timeouts, and schedule-derived drift/grace behavior.
- Task 2.1: exercise per-language comment/scaffold handling, scene connections, Rust test scopes, and size limits with positive/negative fixtures.
- Tasks 2.2–2.4: check contained-path refusal before reads, reconcile duplicate enrollment response with atomic token use, and verify token hashing/revocation/log handling without exposing secrets.
- Task 2.5: correct stale template provenance, align scenario and shipped path, and qualify immutable references, version evidence, health checks, and documented secret parsing.
- Task 2.6: build requirement-specific bundles only where accepted provenance and expected digests are available.

## S3 — independent qualification

- Auditor replays defensive fixtures and checks diagnostic content, exit classes, non-disclosure, and boundary ordering directly.
- Auditor verifies source paths, CI/template receipts, expected bundle digests, and no false attribution of synthetic controls as live behavior.
- Lead resolves conflicting owner decisions and proposes only supported state transitions.

## S4 — integration and closeout

- Run monitor/scanner/security suites, strict OpenSpec, traceability, bundle validation, and state-gate review at final head.
- Handoff: task-to-requirement map, test results, redacted log samples, source provenance, bundle receipts, auditor verdict, and open runtime dependencies.
- Preserve UNPROVEN where historical provenance or deployment evidence remains absent; do not publish token or private host data.
