# Next-phase plan

**Change:** `devgate-spec-coherence-service` · **Date:** 2026-09-17  
**Current state:** FULL spec set written for all sprints — 13 capability specs, 62 `coh-*` requirements, design v2 (R1–R9 amendments embodied), ADR-001…019, sprint plan S0–S8 in `tasks.md`. Strict validation passing; repo gates green. Status: Proposed, pending S0 audit/lead review.

This is a planning document. It accepts no ADR, sets no policy, and authorizes no commit. Repo process (`docs/WRITE_AUDIT_REVIEW.md`) is Write → Audit → Lead Review → Commit & Push (lead only). The write step is complete; nothing has been committed.

**Supersession note:** steps 1–3 below (contract amendments, Phase 0 scoping, thin-slice definition) have been executed and now live in `design.md` v2, the `specs/*` deltas, and `tasks.md` sprints S0–S8. This document remains as the grounding record; `tasks.md` is the operative plan. Fleet-integration specifics (hub check class, runner hosts, infra-repo provisioning) will be reconciled into `specs/integrations/spec.md` and design "Fleet integration notes" when the fleet reconnaissance completes — the 2026-09-25 two-tier rebalance (ucs03 CPU tier / dell-u2 GPU-only) is the latest such change and is recorded in that section, not here.

## Verified repository grounding

Facts confirmed in this checkout on 2026-09-17 (paths relative to repo root):

| Fact | Source |
|---|---|
| Agent guidance is `AGENTS.md`; stdlib-only (no pip deps), no new secrets/tokens, `HUB_*` env pattern | `AGENTS.md`, `hub/__init__.py` |
| File budgets: 300 soft / 500 hard lines for source, 600 hard for tests | `scripts/regression_sizes.py` |
| Fleet surface: `/enroll`, `/heartbeat`, `/revoke`, `/health` endpoints; `MonitorLoop` check classes; `AlertSink.raise_alert`; atomic registry state | `hub/server.py`, `hub/monitor.py`, `hub/alerts.py`, `hub/registry.py` |
| Runners report `podman_ok` — Podman is the spoke container runtime | `hub/schema/runners.schema.json` |
| Traceability: `<!-- id: <req-id> -->` in published specs ↔ `# // spec: <id>` in Python (regex matches `//` prefix only); advisory while `openspec/gate-config.json` is absent | `scripts/spec_traceability.py` |
| Requirement ID namespaces in use: `mon-*`, `gate-*`, `rule-*`; `coh-*` is free | `openspec/specs/` |
| Active change `ai01-runner-monitor-impl` has only task 7.5 (deploy verification) open; coherence is a distinct capability and must not bundle under it | `openspec/changes/ai01-runner-monitor-impl/tasks.md` |
| Repo gates: `python3 scripts/regression_check.py --all --pre-commit`, `node scripts/guardrails-scan.mjs`, `python3 scripts/spec_traceability.py --report`, `python3 -m pytest -q tests/` | `AGENTS.md` |

## Step 0 — close the write cycle (now)

1. Independent audit of the written package: fidelity to the submitted text, internal consistency, repo guardrails.
2. Lead review of `review.md` findings R1–R9; accept or amend ADR-001…ADR-010.
3. Lead commits the package. No code changes in this step.

## Step 1 — contract amendments (blocks Phase 1 code)

Amend `design.md` per `review.md` before any implementation:

- **R1** acyclic sealing order; detached attestation outside canonical decision bytes.
- **R2** versioned evaluation-context manifest: trusted `evaluation_time`, effective stage, baseline/exception/capability/captured-fact digests; replay vs fresh-promotion semantics.
- **R3** one decision/exit-code matrix; `assertion_results` ledger (one entry per required assertion); structured error envelopes.
- **R4** authenticated approval and policy authority; anti-rollback and revocation; enforcement boundary outside repository-controlled files.
- **R5** slice-1 uses bundled built-in evaluators only; launcher-validated isolation; plugin sandbox decision deferred.
- **R6** digest/canonicalization profile: SHA-256, RFC 8785 subset, raw-byte file hashing, image-index vs platform identity, input snapshotting.
- **R7** operational assertion schema: requirement refs, owners, typed selectors, finding-key rules, release-claim binding order.

Repository-level defaults to record at freeze:

- **D-a.** Requirement IDs use the `coh-*` namespace; delta specs receive `<!-- id: -->` markers when the contract freezes.
- **D-b.** No `openspec/gate-config.json` yet — coherence stays advisory until the Stage 2 ratchet is demonstrated on fixtures.
- **D-c.** Slice-1 reference runtime is a local stdlib process; the pinned Podman container is a Phase 2 concern. This deliberately deviates from "container from day one" (ADR-002 sequencing, not its intent) because this repo is stdlib-only and runners already report `podman_ok`. Record as a design amendment.

Owner decisions from `acceptance.md` that gate Phase 0: Q1 (approval mechanism), Q2 (enforced-core classes), Q3 (max advisory age), Q4 (exception approvers), Q5 (byte-equivalent architectures), Q9 (gamerepo01 normative vs historical facts). Q6–Q8 and Q10 can defer to Phase 2+.

## Step 2 — Phase 0 discovery, scoped to this repo

- Inventory fleet/gate result shapes from `hub/monitor.py` check classes and the `/health` payload; record in a design appendix so the coherence result contract does not silently collide with existing fields (feeds Q8).
- Pilot provenance rule (R9): every fixture records source commit SHA, report digest, capture time, and source location; synthetic fixtures are labeled synthetic. The LobsterWars 13-violation baseline and the gamerepo01 identity-drift fixture are synthetic models until captured from the real repositories with owner approval.
- Freeze the canonical JSON profile, digest algorithm, and protocol versioning (R6) as golden vectors committed under `tests/fixtures/coherence/`.
- Name the central policy authority and exception approvers in the policy-bundle design; these live in the control plane, not in repository config.

## Step 3 — thin slice (first code; advisory mode only)

Scope: fixture-driven coherence core in this repository. No container, no signing, no network, no fleet integration.

Capability spec lands at `openspec/specs/spec-coherence-service/spec.md` with `coh-*` IDs per D-a.

Modules (stdlib-only, each under 500 lines, carrying `# // spec: coh-*` markers):

| Module | Responsibility |
|---|---|
| `hub/coherence/manifest.py` | subject manifest: normalized relative paths, SHA-256, symlink/submodule/exclusion policy |
| `hub/coherence/package.py` | package resolution, normative/informative boundary, canonical package digest |
| `hub/coherence/plan.py` | assertion graph: duplicate/cycle/undeclared-input detection; complete-outcome accounting |
| `hub/coherence/evaluate.py` | three built-in evaluators: product-identity consistency, traceability completeness, release-claim consistency |
| `hub/coherence/result.py` | canonical result JSON, finding sort order, exit codes `0/10/20/30/31/32/33/40` |
| `hub/coherence/evidence.py` | local evidence bundle, manifest digest, sealing, minimal-disclosure redaction |

CLI: `python -m hub.coherence --request request.json` using the amended R2 contract (evaluation time comes from the context file, never the wall clock).

Fixtures and tests (`tests/test_hub_coherence_*.py`, dual-runnable pytest/`__main__` pattern):

- Fixture A coherent repository → PASS; canonical bytes identical across 100 replays.
- Fixture B identity drift → VIOLATED with exact evidence locations.
- Fixture C-lite ratchet → four fingerprinted baseline violations + one new → FAIL; expired exception → FAIL; wildcard exception → invalid policy.
- Fixture E time-reading evaluator → capability denied or ERROR; never an inconsistent pass.
- Fixture F post-seal evidence tamper → digest verification fails.

Note: repo reconnaissance suggested starting from a requirement-marker validator; that duplicates the existing `scripts/spec_traceability.py`. Instead, the traceability-completeness assertion consumes that script's marker conventions as an input.

## Step 4 — gated follow-ons (not in the thin slice)

1. Pinned Podman container with launcher-validated isolation tests (R5).
2. Detached attestation signing in R1 order; required before any promotion-authorizing Stage 2 run (R8).
3. Fleet integration: a new `MonitorLoop` check class plus `AlertSink.raise_alert` wiring; hub endpoints and schema unchanged.
4. Stage-ladder rollout with real pilot baselines (provenance-gated), then `tasks.md` Phases 6–7 as submitted.

## Validation commands per step

```text
openspec validate devgate-spec-coherence-service --strict --no-interactive
python3 scripts/spec_traceability.py --report
python3 scripts/regression_check.py --all --pre-commit
node scripts/guardrails-scan.mjs
python3 -m pytest -q tests/
```

## Exit criteria — "next phase complete"

1. Package audited, lead-reviewed, and committed by the lead.
2. R1–R7 amendments accepted; design.md v2 is the frozen contract.
3. Thin slice green: pytest suite, `regression_check --all --pre-commit`, guardrails scan, and traceability report shows `coh-*` IDs covered; 100× replay byte-identical; fixtures A/B/C-lite/E/F produce their expected decisions.
4. Written provenance for every pilot fact used in fixtures.

## Explicit non-goals for this phase

No changes to existing gates or hub behavior; no branch-protection or fleet-enforcement flips; no automatic repair; no AI interpretation in the decision path; no agent commits.
