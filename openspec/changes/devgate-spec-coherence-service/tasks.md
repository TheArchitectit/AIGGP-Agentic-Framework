# Implementation and validation roadmap (all sprints)

Dependency-ordered sprint plan for the full program. Sprint S0–S1 gate everything after them; S2–S3 are the thin slice; S4–S7 map to the submitted phases 2–5; S8–S9 map to phases 6–7. No sprint begins before its gate closes. "Blocks" names what cannot start until the sprint is accepted.

## Sprint S0 — close the write cycle

- [x] Independent audit of the written package (fidelity to submitted text, internal consistency, repo guardrails) — review pass documented in `review.md`; guardrails/regression/traceability green.
- [x] Lead review of `review.md` findings R1–R9 and design v2 amendment log — approved 2026-09-17.
- [x] Accept or amend ADR-001 through ADR-010 — accepted with package approval 2026-09-17 (ADR-011…019 accepted alongside).
- [x] Record repo defaults: `coh-*` requirement namespace; no `openspec/gate-config.json` yet (advisory); stdlib slice-1 runtime with pinned container deferred (documented ADR-002 sequencing deviation) — recorded in `next-phase-plan.md`.
- [ ] Owner decisions on acceptance.md questions Q1 (approval mechanism), Q2 (enforced-core classes), Q3 (max advisory age), Q4 (exception approvers), Q5 (byte-equivalent architectures), Q9 (gamerepo01 normative vs historical facts) — proposed defaults recorded in `s1-freeze-record.md`; owner confirmation still open.
- [x] Lead commits the package — `eac440a` pushed to main 2026-09-17.

**Gate:** package audited, ADRs dispositioned, committed — CLOSED 2026-09-17. **Blocks:** everything.

## Sprint S1 — contract freeze

- [x] Freeze design.md v2 as the contract — recorded in `s1-freeze-record.md` §1.
- [x] Publish versioned JSON schemas (12) — `schemas/` (request, evaluation-context, result, error-envelope, attestation, assertion, package, evidence-manifest, policy-bundle, exception, baseline-entry, subject-manifest).
- [x] Commit golden canonicalization and digest vectors — `tests/fixtures/coherence/` (`compute_golden.py` + `vectors.json`, reproducible, `# // spec: coh-id-01, coh-id-05`).
- [x] Write the decision/exit matrix — `decision-exit-matrix.md` (stage × outcome × error-class, tie-breaking, caller contract).
- [x] Define the execution-profile registry — `execution-profile-registry.md` (amd64 byte-equivalent at launch; arm64 pending Q5).
- [x] Map coherence result against hub check-class shapes — `s1-freeze-record.md` §6 (feeds Q8; no hub schema change).
- [x] Resolve R8 decisions — design/specs (signing Stage 2 promotion-authorizing; offline sealing; retryable upload; retention channels); recorded §1/§7.
- [x] Adopt R9 provenance rule — fixtures synthetic until captured with owner approval; recorded §7.

**Gate:** schemas + golden vectors committed; matrix table reviewed — CLOSED 2026-09-17 pending owner confirmation of Q1–Q5/Q9 proposed defaults (`s1-freeze-record.md` §7). **Blocks:** S2+.

## Sprint S2 — thin slice core (advisory, stdlib, this repo)

Modules under `hub/coherence/`, each <500 lines, stdlib-only, `# // spec: coh-*` markers on first implementing function:

- [x] `canon.py` — restricted RFC 8785 canonicalization + domain-separated digests (coh-id-01, coh-id-05).
- [x] `manifest.py` — subject manifest: normalized paths, raw-byte SHA-256, symlink policy, traversal/collision rejection, read-time re-verification (coh-id-02).
- [x] `package.py` — package resolution, normative inventory, frozen import closure, canonical package digest (coh-pkg-01..05, coh-id-03, coh-ev-07).
- [x] `context.py` — evaluation-context load/validate, trusted-issuance check, replay vs fresh-promotion (coh-ctx-01..03).
- [x] `plan.py` — assertion graph: schema completeness, duplicates, cycles, central-required enforcement, planning-time traceability (coh-eval-02, coh-assert-01, coh-assert-04, coh-pol-01).
- [x] `evaluate.py` — built-in evaluator runtime: declared-inputs-only mediation, limits → ERROR, unapproved-evaluator → UNRESOLVED, dependency-blocked (coh-eval-02, coh-eval-06, coh-rt-05, coh-rt-06).
- [x] `evaluators.py` — three slice evaluators: identity-consistency (approved-value comparison), traceability-completeness, release-claim consistency (coh-assert-02, coh-assert-03, coh-assert-04).
- [x] `result.py` — ledger, finding sort/keys, canonical JSON, decision/exit matrix, error envelopes (coh-dec-01..05, coh-eval-03, coh-assert-06).
- [x] `evidence.py` — minimum-disclosure capture, redaction, bundle sealing, manifest digest, per-object tamper verification (coh-ev-02, coh-ev-03, coh-ev-06).
- [x] `__main__.py` — CLI `python -m hub.coherence --request request.json`; time only from context; exit codes per matrix.

Tests `tests/test_hub_coherence.py` (dual-runnable, 33 tests):

- [x] Canonicalization: sorted keys, floats rejected, int64 bounds, domain separation, LF≠CRLF raw-byte hashing (coh-id-01, coh-id-05).
- [x] Subject manifest: build/digest stability, missing root, read-time mutation detection (coh-id-02).
- [x] Package: resolve, missing manifest, inventory digest mismatch (coh-pkg-01, coh-pkg-05).
- [x] Context: load, no-issuer rejection, invalid stage (coh-ctx-01, coh-ctx-02).
- [x] Plan: order, duplicate ID, cycle, central-required-omitted, missing field (coh-eval-02, coh-assert-01, coh-pol-01).
- [x] Evaluators: identity satisfied/unapproved-consistent/selector-empty (coh-assert-02), unapproved evaluator → UNRESOLVED, dependency-blocked (coh-eval-02, coh-eval-06, coh-rt-06).
- [x] Result matrix: enforced/advisory/error-dominates/pass/unresolved-blocks, finding sort, canonical error=null (coh-dec-01..05, coh-eval-03).
- [x] Evidence: seal+verify, tamper detected per-object (coh-ev-02, coh-ev-03, coh-ev-06).
- [x] End-to-end CLI + 100× replay → byte-identical canonical result, exit 0, PASS.

**Gate:** 129 tests green (96 pre-existing + 33 coherence); regression, guardrails, strict-validate, traceability (31 coh-* covered) all green; 100× replay byte-identical — CLOSED 2026-09-17. **Blocks:** S3+.

## Sprint S3 — slice hardening and pilot-shaped demos

- [ ] Context issuance tooling (control-plane stand-in for pilots): signed context files, stage registry, baseline/exception sets with fingerprint schema (coh-ctx-02, coh-pol-05).
- [ ] Advisory-age and exception-expiry reporting from result + context (coh-pol-03, coh-pol-06).
- [ ] Replay CLI (`semantics: replay`) demonstrating byte-reproduction of a historical decision, labeled non-promotion-authorizing (coh-ctx-03).
- [ ] Synthetic LobsterWars-shaped fixture: 13 named findings, full Stage 1 → Stage 2 ladder demonstration per acceptance Fixture C (labeled synthetic until R9 provenance capture exists).
- [ ] Publish `openspec/specs/spec-coherence-service/spec.md` from accepted deltas; decide `openspec/gate-config.json` posture for `coh-*` IDs.

**Gate:** ladder demo reviewed by lead; published spec traceable. **Blocks:** fleet-facing sprints.

## Sprint S4 — container and evaluator boundary (submitted Phase 2)

- [ ] Build multi-architecture pinned service image (Podman; runners already report `podman_ok`); record index vs platform digests per execution-profile registry (coh-id-04).
- [ ] Launcher-validated isolation: non-root, read-only root/inputs, dropped capabilities, no host sockets/network; launcher rejects violating configs; self-report not trusted (coh-rt-01, coh-rt-02).
- [ ] Bounded scratch + designated output location; atomic export; partial-output = ERROR (coh-rt-05, coh-rt-07).
- [ ] Default-deny egress with capture-step grants; captured responses become context facts (coh-rt-03, coh-ctx-04).
- [ ] Scoped secret injection + redaction tests (coh-rt-04).
- [ ] Built-in evaluator allowlist enforcement: repository-supplied executable rejected (coh-rt-06).
- [ ] Isolation test suite against the approved launcher and supported sandbox, not Dockerfile inspection alone.

**Gate:** isolation suite green on supported runners. **Blocks:** S6 enforced pilots.

## Sprint S5 — attestation and evidence store (submitted Phase 3)

- [ ] Detached attestation signing in sealing order; signer-set verification; revocation fail-closed (coh-ev-01, coh-ev-05).
- [ ] Attestation verification CLI; substitution detection tests.
- [ ] Immutable store adapter + offline local-bundle mode; retryable upload after seal (coh-ev-02).
- [ ] Authorized input-retention channel distinct from public evidence; retention expiry invalidates cache (coh-ev-04).
- [ ] Tamper, substitution, partial-upload, stale-cache, revoked-signer failure-injection suite.
- [ ] Complete cache-key enforcement: subject+package+policy+context+image+plugins+captured facts+TTL+retention+signer (coh-ctx-05).

**Gate:** attestation suite green; required before any promotion-authorizing Stage 2 run. **Blocks:** enforced pilots.

## Sprint S6 — adoption ladder and fleet integration (submitted Phases 4–5)

- [ ] Implement inventory/advisory/ratchet/enforced-core/enforced-full modes with authoritative stage record; requested-mode weakening rejected (coh-ctx-02, coh-pol-01).
- [ ] Anti-rollback policy selection; trusted-but-obsolete bundle rejection (coh-pol-01, coh-pol-02).
- [ ] Fingerprinted baselines; severity-escalation and recurrence-after-fix behavior (coh-pol-04, coh-pol-05).
- [ ] External enforcement boundary: required checks/rulesets/promotion-controller binding; workflow-deletion test (coh-pol-07).
- [ ] Hub integration: add a fifth `MonitorLoop` check class `_check_spec_coherence(repo, owner)` alongside the existing four (`_check_runner_status`, `_check_queue_drain`, `_check_gate_results`, `_check_drift_scan`), polling the check-runs API for a coherence workflow conclusion on `HUB_WATCHED_BRANCHES` and alerting via `_raise_alert(repo, "coherence_failure", runner, detail)` → existing `AlertSink` dedup `(repo, check-class, runner)`; hub endpoints and `runners.schema.json` unchanged unless the S1 field-collision map says otherwise (coh-int-02, coh-int-07).
- [ ] CI workflow following `templates/github-workflows/drift-scan.yml` pattern, `runs-on: devgate` (or repo labels like `devgate-game`), pinned runtime invocation + event wiring only; gate executes or reports explicit SKIPPED per `ci-run-01` (coh-int-01, coh-int-06).
- [ ] Thin pinned CI invocation template + local developer command with byte-equivalent results (coh-int-01, coh-int-05).
- [ ] Adapter default-deny: timeouts/unparseable results surface ERROR, never neutral/pass (coh-int-05).
- [ ] Account for repo-scoped runners and multi-runner hosts: stock `runner-enroll.sh` is single-runner-per-host (fixed unit names); per-runner units (`devgate-hb-<name>.{service,timer}`) where a host runs multiple spokes (coh-int-07).
- [ ] Outage, mirror, cached-attestation, protocol-mismatch behavior; migration guide + operator runbook.
- [ ] Real pilots behind R9 provenance, now that fleet recon confirms the repos are real registered spokes: gamerepo01 (runner `dell-u2-game`), a LobsterWars-class repo, and one clean repo; capture lineage/13-violation facts from the real repos with owner approval before labeling fixtures non-synthetic; Stage 2 ratchet demo blocks a new violation while named debt remains advisory.

**Gate:** Stage 3 readiness review inputs complete. **Blocks:** enforced rollout.

## Sprint S7 — 3D vertical slice (submitted Phase 6)

- [ ] 3D composite subject manifest: world IR, GLB assets, engine scene, executable build, captures, evaluation records; part-digest composition (coh-3d-01).
- [ ] Map first room's normative requirements to stable assertion IDs under the operational assertion schema.
- [ ] Capture pipeline under pinned configuration; captures as declared inputs, evaluators never render (coh-3d-04).
- [ ] Gate one Godot build and one bounded repair through the same contract; no pipeline-specific branching (coh-3d-03).
- [ ] Prove repaired digest invalidates earlier attestation; new PASS binds repaired digest (coh-3d-02, acceptance Fixture G).
- [ ] Vision observations advisory-only until reproducibility criteria met (coh-assert-05).

**Gate:** evidence-backed promotion + deterministic halt demonstrated. **Blocks:** 3D enforcement.

## Sprint S8 — hardening and release (submitted Phase 7)

- [ ] Threat model + container escape review (evaluator boundary emphasis).
- [ ] 100-repeat determinism suite per supported architecture per execution-profile equivalence promise.
- [ ] Failure injection: missing specs, evaluator crash, denied egress, exhausted resources, bad signatures, evidence loss, input mutation mid-run.
- [ ] Compatibility + deprecation policy; schema versioning tests.
- [ ] SLOs: evaluation availability, maximum advisory age.
- [ ] Runbooks: outage, rollback, policy recovery, key rotation, evaluator revocation.
- [ ] Stage 3 readiness review before any enforced fleet rollout.

**Gate:** all 12 release acceptance criteria in `acceptance.md` demonstrably met.

## Cross-sprint invariants

- Every new requirement ID carries `<!-- id: coh-* -->` in specs and `# // spec: coh-*` on first implementing function.
- Stdlib-only in this repository; no new secrets/tokens beyond the established env pattern; instance state never committed.
- No sprint flips branch protection, fleet enforcement, or gate-config posture without explicit lead approval.
- Synthetic fixtures stay labeled synthetic until provenance capture replaces them.
