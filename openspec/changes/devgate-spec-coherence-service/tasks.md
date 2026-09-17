# Implementation and validation roadmap (all sprints)

Dependency-ordered sprint plan for the full program. Sprint S0–S1 gate everything after them; S2–S3 are the thin slice; S4–S7 map to the submitted phases 2–5; S8–S9 map to phases 6–7. No sprint begins before its gate closes. "Blocks" names what cannot start until the sprint is accepted.

## Sprint S0 — close the write cycle

- [ ] Independent audit of the written package (fidelity to submitted text, internal consistency, repo guardrails).
- [ ] Lead review of `review.md` findings R1–R9 and design v2 amendment log.
- [ ] Accept or amend ADR-001 through ADR-010 (see `adrs.md`); record decisions in the ADR file.
- [ ] Record repo defaults: `coh-*` requirement namespace; no `openspec/gate-config.json` yet (advisory); stdlib slice-1 runtime with pinned container deferred (documented ADR-002 sequencing deviation).
- [ ] Owner decisions on acceptance.md questions Q1 (approval mechanism), Q2 (enforced-core classes), Q3 (max advisory age), Q4 (exception approvers), Q5 (byte-equivalent architectures), Q9 (gamerepo01 normative vs historical facts).
- [ ] Lead commits the package.

**Gate:** package audited, ADRs dispositioned, committed. **Blocks:** everything.

## Sprint S1 — contract freeze

- [ ] Freeze design.md v2 as the contract: sealing order (R1), context manifest (R2), decision/exit matrix + ledger + error envelopes (R3), authority model (R4), built-in evaluator rule (R5), digest/canonicalization profile (R6), assertion schema (R7).
- [ ] Publish versioned JSON schemas: request, context, canonical result, error envelope, assertion, package manifest, evidence manifest, exception, baseline entry.
- [ ] Commit golden canonicalization and digest vectors under `tests/fixtures/coherence/` (domain separation, RFC 8785 subset, raw-byte file hashing, CRLF-is-a-change, Unicode/path collision rejection).
- [ ] Write the decision/exit matrix as a testable table: every stage × outcome × error-class combination, including simultaneous crash+violation and exit/result disagreement.
- [ ] Define the execution-profile registry (profile label → platform digests → equivalence promise) for Q5 architectures.
- [ ] Map the coherence result contract against existing hub check-class shapes (`hub/monitor.py`) and record field-collision decisions (feeds Q8).
- [ ] Resolve R8 decisions: signing milestone (Stage 2 promotion-authorizing), offline sealing in slice, remote-upload retry semantics, retention channels and approvers.
- [ ] Adopt R9 provenance rule: every pilot fixture records source commit SHA, report digest, capture time, source location; synthetic fixtures labeled synthetic.

**Gate:** schemas + golden vectors committed; matrix table reviewed. **Blocks:** S2+.

## Sprint S2 — thin slice core (advisory, stdlib, this repo)

Modules under `hub/coherence/`, each <500 lines, stdlib-only, `# // spec: coh-*` markers on first implementing function:

- [ ] `manifest.py` — subject manifest: normalized paths, raw-byte SHA-256, symlink/submodule/exclusion policy, traversal/collision rejection, read-time re-verification (coh-id-02).
- [ ] `package.py` — package resolution, normative/informative inventory, frozen import closure, canonical package digest, detached-approval verification hook (coh-pkg-01..05, coh-id-03, coh-ev-07).
- [ ] `context.py` — evaluation-context load/validate, trusted-issuance check, replay vs fresh-promotion semantics (coh-ctx-01..03).
- [ ] `plan.py` — assertion graph: schema completeness, duplicates, cycles, undeclared inputs, planning-time traceability, complete-outcome accounting (coh-eval-02, coh-assert-01, coh-assert-04).
- [ ] `evaluate.py` — built-in evaluator runtime: declared-inputs-only mediation, limits → ERROR, three slice evaluators: identity-consistency, traceability-completeness (consuming `scripts/spec_traceability.py` marker conventions), release-claim consistency (coh-eval-06, coh-rt-05, coh-rt-06, coh-assert-02, coh-assert-03).
- [ ] `result.py` — ledger, finding sort/keys, canonical JSON serialization, decision/exit matrix, error envelopes (coh-dec-01..05, coh-eval-03, coh-assert-06).
- [ ] `evidence.py` — minimum-disclosure capture, redaction, bundle sealing, manifest digest, tamper verification (coh-ev-02, coh-ev-03, coh-ev-06).
- [ ] CLI `python -m hub.coherence --request request.json` — time only from context; exit codes per matrix.

Tests `tests/test_hub_coherence_*.py` (dual-runnable pytest/`__main__`, ephemeral-port/fake-server patterns where relevant):

- [ ] Fixture A coherent repository → PASS; canonical bytes identical across 100 replays.
- [ ] Fixture B identity drift (synthetic, labeled) → VIOLATED with exact evidence locations and approved-value comparison.
- [ ] Fixture C-lite ratchet → 4 fingerprinted baseline + 1 new → FAIL; one-fixed-one-new at constant count → FAIL; expired exception → FAIL; wildcard exception → invalid policy.
- [ ] Fixture D bypass → overlay removing a central assertion or choosing an unapproved evaluator → invalid policy/FAIL, never PASS.
- [ ] Fixture E nondeterministic evaluator (time read, unordered traversal) → denied/ERROR, never inconsistent passes.
- [ ] Fixture F evidence tamper post-seal → digest verification fails.
- [ ] Full exit-code sweep fixtures (0/10/20/30/31/32/33/40) each produce documented exit + parseable result/envelope.
- [ ] Error-envelope tests: null identities never fabricated; exit/result disagreement → ERROR for caller.

**Gate:** `python3 -m pytest -q tests/`, `regression_check --staged --pre-commit`, guardrails scan, traceability report all green; 100× replay byte-identical. **Blocks:** S3+.

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
