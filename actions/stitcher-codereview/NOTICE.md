# Attribution — stitcher-codereview (OpenSpec Review)

This directory vendors **stitcher-codereview** ("OpenSpec Review"), a
spec-aware code review tool that verifies a PR diff against an OpenSpec change.

- **Upstream (author):** https://github.com/drwhofan2k18-pixel/stitcher-codereview
- **Vendored from commit:** 28e0bfe925fb (main, 2026-09-19)
- **Vendored version:** 0.4.1
- **License:** MIT (as declared by the author in `package.json`)
- **Credit:** © drwhofan2k18-pixel — original author and maintainer.

Vendored into DevGate so in-account GitHub Actions workflows can resolve the
gate via `uses:` (a cross-account private action cannot be resolved, and this
repo is public with a BSD-3-Clause license). Only the files needed to run the
composite action are vendored: `action.yml`, `package.json`,
`package-lock.json`, `tsconfig.json`, and `src/`.

Upstream is MIT-licensed; redistribution and modification are permitted with
this notice retained. See `README.md` for the upstream README.

## Local modifications (DevGate)

The vendoring commit `c9d1194` is the provenance record, not a boundary: per
the owner decision of 2026-11-14 this repository owns the action, and the
aiggp-08 stages below are first-party changes on top of upstream v0.4.1.

Initial vendoring modifications:

Three `guardrails-allow` trailing comments were added to satisfy DevGate's own
tree scan, each with a justification:
- `src/serve.ts` (PREVENT-003) — false positive: constant-time compare of a
  request header token against the configured secret; no hardcoded credential.
- `src/templates/types.ts` (PREVENT-011) — upstream `any` on an already-parsed
  diff record.
- `src/llm/provider.ts` (SEMANTIC-001) — the flagged Promise executor captures
  only `resolve`, so the chain cannot reject; a `.catch()` would be dead code.

aiggp-08 changes (2026-11-15):

- Stage 1: bidirectional commit/task traceability (`src/checks/commitMap.ts`,
  wired through `src/checks/tasks.ts` and the engine).
- Stage 2: coherence evidence references on requirement verdicts and findings
  (`src/evidenceRef.ts`); an undeclared change is now flagged high and cannot
  receive a clean verdict.
- Stage 3: reverse drift over a change-less range (`checkReverseDrift`) plus
  the `--drift-only` CLI mode and `scripts/stitcher-drift.mjs` gate.
- Stage 4: `.pre-commit-hooks.yaml` and `scripts/stitcher-local.mjs` parity
  harness.
- Stage 5: SARIF results carry `properties.evidenceRef`.
- Stage 6: GitHub/GitLab refuse to post a comment with no evidence link.
- Stage 7: whole-repo `--scan repository` mode is exercised by tests and the
  scheduled drift scan.
- Stage 8: adapter provenance (tool, version, input and raw-output digests)
  and the `guardrails-scan` / `secret-scan-declared` adapters.
- Stage 9: `src/verdict.ts` promote/halt contract keyed to subject digests,
  with `--verdict` on the CLI.
- Tests: `test/fixture-a..h` (Fixtures A-H), `test/stages-wiring.test.ts`.

One documentation edit: `README.md`'s Roadmap link pointed at upstream's
`docs/ROADMAP.md`, which is not in the vendored subset (only the files the
composite action needs are), so the link resolved to nothing. It now points at
upstream's file on GitHub and says the roadmap is not vendored here.
