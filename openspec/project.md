# DevGate Agentic Framework — Project Context

## Purpose

DevGate is a language-agnostic quality-engineering framework. Consumers
use a local, untracked tooling checkout at `.devgate/`. Consumer CI can
provision pinned tooling in a clean workspace. DevGate ships static and CI
quality gates, a gated deploy pipeline, a self-hosted runner standard, a
runner-monitor hub, and a spec-coherence evaluation service that produces
digest-pinned, evidence-sealed decisions.

## Users

- **Consumer projects** — repositories that provision DevGate tooling at
  `.devgate/` and run its gates in CI. They own configuration in
  `.guardrails/` and keep tooling changes out of consumer source history.
- **AI agents** — read `AGENTS.md` and the skill templates; are subject to the
  Four Laws and the Write→Audit→Review→Commit process.
- **Fleet operators** — run self-hosted runners, the monitor hub, and the
  spoke-side watchdog per `docs/runner-monitor-monitor-hub.md`.
- **DevGate maintainers** — the architect and audit agents that evolve the
  framework itself under `openspec/` change packages.

## Core Workflows

1. **Consume**: provision an untracked `.devgate/` checkout → run pinned CI
   gates using the published templates → supply evidence to the protected
   consumer delivery path.
2. **Monitor**: enroll runners with one-time tokens → hub polls GitHub API +
   receives heartbeats → deduplicated issue alerts + JSONL audit trail.
3. **Evaluate**: build an OpenSpec package + policy + context →
   `python -m hub.coherence --request` (optionally `--launch-config` for
   containerized execution) → canonical result + sealed evidence + exit code.

## Style / Conventions

- Ship a standard-library runtime for the hub and core gates where specified.
  The CI and test workflows provision their pinned prerequisites, including
  the semantic scanner's TypeScript parser.
- Spec traceability markers: `<!-- id: <req-id> -->` in spec files,
  `// spec: <id>` / `# // spec: <id>` in source, gated by
  `scripts/spec_traceability.py`.
- Requirement ID namespaces: `mon-*` (monitor hub), `gate-*`, `base-*`,
  `doc-*`, `pub-*`, `rel-*`, `rule-*`, `scan-*`, `ci-*`, `fleet-*`,
  `coh-*` (spec-coherence service), `comm-*` (community sub-site
  capabilities).
- Exit-code honesty: a gate that evaluated zero inputs must never print the
  clean-pass line (no vacuous green); SKIPPED is stated, never implied green.
- The failure registry is append-only; specs are the source of truth for gate
  behavior; changes land through OpenSpec change packages under
  `openspec/changes/<change>/` (proposal, tasks, optional design + deltas).

## Constraints

- Keep the evaluator request path independent of CI and test dependencies.
- Monitor hub binds loopback by default; secrets are env-only, never committed.
- The coherence service is deterministic: time and stage come only from the
  signed evaluation context, never the host clock.
- Container execution is digest-pinned, read-only, non-root, network=none,
  cap-drop ALL; the container never self-certifies.

## Anything Else

Current coverage and dependencies are recorded in
[`docs/AIGGP-FUTURE-READINESS.md`](../docs/AIGGP-FUTURE-READINESS.md).
`docs/ROADMAP-2026-09.md` records the September baseline.
Prior audits live in `docs/qa/`; the failure registry in
`.guardrails/failure-registry.jsonl` records incident-proven rules.
