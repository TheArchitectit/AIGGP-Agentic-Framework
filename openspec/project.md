# DevGate Agentic Framework — Project Context

## Purpose

DevGate is a language-agnostic quality-engineering framework that consumers
embed as a `.devgate/` submodule (or standalone clone). It ships static/CI
quality gates (pattern, semantic, regression, file-size, schema, silent-success
scans), a gated deploy pipeline, a self-hosted runner standard, a runner-monitor
hub, and a spec-coherence evaluation service that turns OpenSpec packages into
digest-pinned, evidence-sealed decisions.

## Users

- **Consumer projects** — any repo that embeds DevGate as `.devgate/` and runs
  its gates in CI. They must never need to edit files inside the submodule
  (the `.guardrails/` overlay contract).
- **AI agents** — read `AGENTS.md` and the skill templates; are subject to the
  Four Laws and the Write→Audit→Review→Commit process.
- **Fleet operators** — run self-hosted runners, the monitor hub, and the
  spoke-side watchdog per `docs/runner-monitor-monitor-hub.md`.
- **DevGate maintainers** — the architect and audit agents that evolve the
  framework itself under `openspec/` change packages.

## Core Workflows

1. **Consume**: clone/submodule into a project → run the gates in CI using the
   `templates/github-workflows/` patterns → deploy via `scripts/deploy.sh`.
2. **Monitor**: enroll runners with one-time tokens → hub polls GitHub API +
   receives heartbeats → deduplicated issue alerts + JSONL audit trail.
3. **Evaluate**: build an OpenSpec package + policy + context →
   `python -m hub.coherence --request` (optionally `--launch-config` for
   containerized execution) → canonical result + sealed evidence + exit code.

## Style / Conventions

- Stdlib-only Python (hub, scripts); Node with no npm deps for `.mjs` gates.
- Spec traceability markers: `<!-- id: <req-id> -->` in spec files,
  `// spec: <id>` / `# // spec: <id>` in source, gated by
  `scripts/spec_traceability.py`.
- Requirement ID namespaces: `mon-*` (monitor hub), `gate-*`, `base-*`,
  `doc-*`, `pub-*`, `rel-*`, `rule-*`, `scan-*`, `ci-*`, `fleet-*`,
  `coh-*` (spec-coherence service).
- Exit-code honesty: a gate that evaluated zero inputs must never print the
  clean-pass line (no vacuous green); SKIPPED is stated, never implied green.
- The failure registry is append-only; specs are the source of truth for gate
  behavior; changes land through OpenSpec change packages under
  `openspec/changes/<change>/` (proposal, tasks, optional design + deltas).

## Constraints

- No pip/npm runtime dependencies for anything in the request path.
- Monitor hub binds loopback by default; secrets are env-only, never committed.
- The coherence service is deterministic: time and stage come only from the
  signed evaluation context, never the host clock.
- Container execution is digest-pinned, read-only, non-root, network=none,
  cap-drop ALL; the container never self-certifies.

## Anything Else

Active roadmap: `docs/ROADMAP-2026-09.md` (2026-09-19 full-repo review).
Prior audits live in `docs/qa/`; the failure registry in
`.guardrails/failure-registry.jsonl` records incident-proven rules.
