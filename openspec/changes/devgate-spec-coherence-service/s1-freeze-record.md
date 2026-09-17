# S1 freeze record

**Date:** 2026-09-17 · **Sprint:** S1 (contract freeze) · **Status:** proposed for owner confirmation

This records the design.md v2 freeze, the published schemas, the golden vectors, the decision/exit matrix, the execution-profile registry, and the proposed defaults for the remaining owner decisions. Items marked "owner decision" are proposed defaults — they take effect only on owner confirmation.

## 1. Contract freeze

design.md v2 is the frozen contract. The seven blocking review findings are embodied as follows:

| Finding | Frozen resolution | Spec / ADR |
|---|---|---|
| R1 attestation cycle | Acyclic sealing order: inputs → evidence → manifest → decision → detached attestation → envelope | `evidence-and-attestation` (coh-ev-01, coh-ev-07), ADR-011 |
| R2 missing time/stage | Evaluation-context manifest is a bound input; fresh-promotion vs replay semantics; complete cache key | `evaluation-context` (coh-ctx-01..05), ADR-012 |
| R3 error precedence | Single decision/exit matrix + assertion ledger + structured error envelopes with explicit nulls | `decision-contract` (coh-dec-01..05), ADR-013 |
| R4 declared authority | Authenticated control-plane authority; anti-rollback; external enforcement boundary | `adoption-and-policy` (coh-pol-01, 02, 07), ADR-014 |
| R5 plugin isolation | Built-in evaluators only until a plugin-sandbox ADR; launcher-validated isolation | `container-runtime` (coh-rt-02, 06), ADR-015 |
| R6 identity profile | SHA-256 + restricted RFC 8785; raw-byte hashing; domain separation; index vs platform digest | `canonical-identity` (coh-id-01..05), ADR-016 |
| R7 assertion operability | Operational assertion schema; approved-value identity; release-claim binding; split traceability; model advice non-canonical | `assertions-and-evaluators` (coh-assert-01..06), ADR-017 |

## 2. Published schemas

| Schema | File | Governs |
|---|---|---|
| request | `schemas/request.schema.json` | coh-int-01, invocation adapter |
| evaluation-context | `schemas/evaluation-context.schema.json` | coh-ctx-01..05 |
| result | `schemas/result.schema.json` | coh-dec-03, coh-eval-03 |
| error-envelope | `schemas/error-envelope.schema.json` | coh-dec-02 |
| attestation | `schemas/attestation.schema.json` | coh-ev-01, coh-ev-05 |
| assertion | `schemas/assertion.schema.json` | coh-assert-01..06 |
| package | `schemas/package.schema.json` | coh-pkg-01..05 |
| evidence-manifest | `schemas/evidence-manifest.schema.json` | coh-ev-02 |
| policy-bundle | `schemas/policy-bundle.schema.json` | coh-pol-01, coh-pol-02 |
| exception | `schemas/exception.schema.json` | coh-pol-06 |
| baseline-entry | `schemas/baseline-entry.schema.json` | coh-pol-04, coh-pol-05 |
| subject-manifest | `schemas/subject-manifest.schema.json` | coh-id-02, coh-3d-01 |

Schemas are stdlib-validatable (no pip). `additionalProperties: false` everywhere on wire contracts so unknown required fields are refused.

## 3. Golden vectors

Committed under `tests/fixtures/coherence/`: `hello_lf.txt`, `hello_crlf.txt`, `canonical_sample.json`, `compute_golden.py`, `vectors.json`. `compute_golden.py` carries `# // spec: coh-id-01, coh-id-05` and is the canonicalization compatibility contract — recomputation must reproduce `vectors.json` byte-for-byte. Verified reproducible on this host (two consecutive runs identical).

## 4. Decision/exit matrix

`decision-exit-matrix.md` — the published total ordering (coh-dec-01/04/05, coh-eval-02). Every stage × outcome × error-class resolves to one decision and exit code; ERROR dominates FAIL; exit/result disagreement is ERROR for the caller.

## 5. Execution-profile registry

`execution-profile-registry.md` — launch profile `linux-amd64-v1` byte-equivalent (existing fleet is amd64); `linux-arm64-v1` pending owner decision Q5, semantic-equivalence only until an arm64 runner is provisioned.

## 6. Hub check-class shape map (field-collision decisions, feeds Q8)

Hub `MonitorLoop` today (verified `hub/monitor.py`): four check classes — `_check_runner_status`, `_check_queue_drain`, `_check_gate_results`, `_check_drift_scan` — alert via `_raise_alert(repo, check_class, runner, detail)` → `AlertSink.raise_alert(repo=..., check_class=..., runner=..., detail=...)`, deduped by `(repo, check_class, runner)`.

Coherence integration adds a fifth check class `_check_spec_coherence(repo, owner)` (S6) consuming the coherence workflow's check-run conclusion per repo on `HUB_WATCHED_BRANCHES`. Field-collision decisions:

- Coherence adds **no new hub schema fields**: it rides the existing check-run conclusion channel, not the registry. `runners.schema.json` is unchanged.
- The existing `_check_gate_results` reads generic check-run conclusions; the coherence check class reads the coherence workflow conclusion specifically, keyed by workflow name, so the two do not double-count the same run.
- Alert `check_class` for coherence is a new value (`coherence_failure`), distinct from existing classes, so dedup keys do not collide with drift/gate/queue alerts.
- No existing hub result fields are renamed; backward compatibility (Q8) is preserved by addition only.

## 7. Proposed defaults for owner decisions (S0 open items)

| Q | Proposed default | Rationale |
|---|---|---|
| Q1 approval mechanism | Detached control-plane approval record binding package digest + authority + repo scope + validity window (ADR-011/014). | Self-referential approval is invalid (coh-ev-07); detached is verifiable and revocable. |
| Q2 enforced-core classes | Slice-1 enforced core: product-identity consistency, traceability completeness, release-claim consistency. | Matches the recommended thin slice; smallest set that proves the product difference. |
| Q3 max advisory age | 30 days at Stage 1, renewable once with owner + written reason + new expiry + control-plane approval. | Bounded; forces LobsterWars anti-goal to surface. |
| Q4 exception approvers | Control-plane authority (fleet policy owner); repository exceptions additionally require repo maintainer + control-plane countersign. | Keeps approval outside the gated repo. |
| Q5 byte-equivalent architectures | amd64 only at launch; arm64 semantic-equivalence only until provisioned. | Fleet is amd64; do not claim unverifiable equivalence. |
| Q9 gamerepo01 normative vs historical | gamerepo01 fixture starts synthetic; normative product identity is the package's declared identity, historical lineage is informative. | R9: no private narrative inference at runtime. |

## 8. S1 gate status

- [x] design.md v2 frozen (this record).
- [x] Schemas published (12).
- [x] Golden vectors committed + reproducible.
- [x] Decision/exit matrix written.
- [x] Execution-profile registry written.
- [x] Hub check-class field-collision map recorded (Q8 inputs).
- [x] R8 decisions folded into design/specs (signing milestone Stage 2; offline sealing; retryable upload; retention channels).
- [x] R9 provenance rule adopted (fixtures synthetic until captured with owner approval).
- [ ] Owner confirmation of Q1–Q5, Q9 proposed defaults.

**Gate:** S1 is complete pending owner confirmation of the proposed defaults. S2 (thin slice) is not gated on that confirmation — it builds against the frozen contract and records the confirmed defaults when they arrive.
