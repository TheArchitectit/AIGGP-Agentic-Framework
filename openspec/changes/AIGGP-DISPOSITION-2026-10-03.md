# Open-spec disposition — 2026-10-03

**Status: decision record.** Owner directive (verbatim): *"lets move ALL open
specs there and then leave this as a clean state with no open specs other than
ones that should be shipped."* This repo's `openspec/changes/` root now holds
zero open change packages. What follows is the complete accounting.

## Where everything went

### Moved to `TheArchitectit/repo-brainstorming` (12 packages, commit `13d913e`)

Verbatim copies under `devgate-open-changes/`, with `MANIFEST.md` recording
status and routing per package:

- aiggp-01-devgate-audit-reconciliation-hardening
- aiggp-02-fleet-spec-coherence
- aiggp-03-prompt-injection-defense *(routing: agent-guardrails family)*
- aiggp-04-semantic-content-filtering *(routing: agent-guardrails family)*
- aiggp-05-runtime-sandbox-isolation *(routing: agent-guardrails family)*
- aiggp-06-indirect-injection-provenance *(routing: agent-guardrails family)*
- aiggp-08-stitcher-proof-parity
- aiggp-10-repository-unification-migration *(returns here when the pull-in
  executes; direction corrected 2026-10-02 — guardrails INTO DevGate)*
- add-3d-vertical-slice *(in progress: 6 open / 0 done)*
- add-gitlab-forge-support *(native spec; commit decision pending owner)*
- devgate-product-tiers-fleet-manager *(in progress: 32 open / 5 done)*
- spec-audit-rollout *(in progress: 12 open / 6 done)*

### Archived here — work shipped, tasks closed (10 packages)

Under `openspec/changes/archive/2026-10-03-`:

- add-runner-image-cycling, add-secret-scanning, ai01-runner-monitor-impl,
  consolidate-shared-gate-logic, docs-and-data-truth-pass,
  fix-coherence-container-contract, fix-size-gate-shell-scope,
  harden-test-suite, self-check-the-mutation-harness
- fix-specs-gate-audit-2026-09 (57 done / 2 open — the 2 open items are
  fleet runtime measurements, not spec work; carried below)

### Untouched

`openspec/specs/` (31 published base specs — the shipped truth),
`openspec/changes/archive/` prior entries (13), `openspec/aiggp-source/`
(frozen as-imported originals, including retired aiggp-00/07/09).

## Carried-open items from fix-specs-gate-audit-2026-09 (verbatim)

These are lab-fleet measurements that outlive the package:

1. **Spoke coverage measured: ucs03 serves 17 GH runners, heartbeats 4.**
   Evidence pass (2026-09-26, read-only on the live hub + ucs03): the hub's
   registry has 13 rows — every `enrolled: true` row reports a heartbeat
   within the last minutes (so the hb path itself is healthy). Options on the
   table: (document the allowlist, no code); (C) re-enroll the missing 13 on
   ucs03 as provisioning, no spec change. Not blocking the drain.
2. **Private-repo hosted risk, measured: every spoke token on ucs03 is
   readable by every CI job on ucs03.** Evidence pass (read-only, no token
   values touched): the hub's `heartbeat_token` is the *only* credential on
   /heartbeat AND on /revoke (server.py authenticates revoke by the token
   itself), and on ucs03 the runner services AND the heartbeat env files
   share one UID — `ps` shows `devgate-runner-*` MainPID owned by `user001`,
   and all four `devgate-heartbeat-<runner>.env` files are …
   *(full text in the archived package's tasks.md, lines 584+)*

## aiggp-01 shipped-vs-gap table (measured 2026-10-03, code-verified)

| Requirement / QA item | Verdict |
|---|---|
| C1 scene_inventory ET.parse dead-end → regex parser primary | SHIPPED |
| C2/C3 scanner root escape → project-root.mjs layout contract | SHIPPED |
| C3 zero-test green → fail-closed, loud DEVGATE_ALLOW_NO_TESTS=1 opt-out | SHIPPED |
| C4 cargo filter bug → `cargo test --test <stem>` | SHIPPED |
| C6 npm HIGH classified dev-only → package.json runtime deps + fail-loud | SHIPPED |
| C7 deploy audits wrong tree → .devgate-basename layout detection | SHIPPED |
| H6 Python marker grammar → `# spec:` accepted | SHIPPED |
| H8 baseline contamination → overlay-default registry, explicit --baseline | SHIPPED |
| "no dead configuration" (dead-rule startup validation) | **NOT SHIPPED** — deferred idea |
| path confinement (traversal = finding, not follow) | **NOT SHIPPED** — deferred idea |

The two gaps are recorded as deferred native-spec ideas (the
add-gitlab-forge-support pattern: written against the shipped surface, when
wanted). They are not scheduled.

## Rules going forward (SA-12)

Open or parked spec packages live in `TheArchitectit/repo-brainstorming`.
This repo's `openspec/changes/` root holds only work scheduled to ship in
tree; completed work archives; published truth lives in `openspec/specs/`.
