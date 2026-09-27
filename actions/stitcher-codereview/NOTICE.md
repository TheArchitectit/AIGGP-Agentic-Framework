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

None to behavior. Three `guardrails-allow` trailing comments were added to
satisfy DevGate's own tree scan, each with a justification:
- `src/serve.ts` (PREVENT-003) — false positive: constant-time compare of a
  request header token against the configured secret; no hardcoded credential.
- `src/templates/types.ts` (PREVENT-011) — upstream `any` on an already-parsed
  diff record.
- `src/llm/provider.ts` (SEMANTIC-001) — the flagged Promise executor captures
  only `resolve`, so the chain cannot reject; a `.catch()` would be dead code.

Upstream source is otherwise byte-identical to commit 28e0bfe925fb.
