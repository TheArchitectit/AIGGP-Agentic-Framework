# Pilot: DevGate gates vs `TheArchitectit/zombie-hero-match`

**Date:** 2026-09-23 · **Mode:** read-only (clone + scan; no changes pushed)
**Layout:** consumer adoption path — DevGate mounted as `.devgate/` inside
the clone (what `scripts/init.mjs` creates)

This is the first real-repo execution of the gate suite (the spec tree's
R9-provenance fixtures remain synthetic; nothing here labels fixtures
non-synthetic).

## Results

| Gate | Result | Detail |
|---|---|---|
| guardrails (pattern) | **PASS** (clean) | vanilla-JS game, no pattern violations |
| semantic (TS compiler) | **FAIL → 4 findings** | first run: refused to pass with the parser missing (fail-closed worked); after `npm i typescript@5`: **4 × SEMANTIC-001 — Promise chains missing `.catch()` in `sw.js`** (a service worker: unhandled rejections there can break background sync) |
| silent-success (4 live families) | **PASS** (clean) | zero allowlist entries needed — no suppression debt |
| file-size | **finding** | `index.html` and `zombie-hero-match.html` are **byte-identical duplicates** (1,556 lines each, same md5 `3710569f…`) — a fix to one silently diverges from the other |

## What the pilot demonstrates

1. **Fail-closed is real**: with the parser absent, the semantic gate
   refused to report a clean scan and named the remediation
   (`npm install --no-save typescript@5`) — the exact no-vacuous-green
   contract.
2. **Zero-noise adoption**: this repo reached a green baseline (pattern +
   silent-success) with **zero allowlist entries** — the counter-example
   to the rad-gateway 1,725-entry pattern (issue #16).
3. **Real findings on first contact**: 4 unhandled-promise violations in
   the service worker and a full-file duplicate — both actionable, both
   found without tuning.

## Recommended actions for the consumer repo

1. Deduplicate `zombie-hero-match.html` (serve or redirect; keep one copy).
2. Add `.catch()` handlers to the 4 `sw.js` promise chains, or annotate
   deliberate ones with `// guardrails-allow SEMANTIC-001: <reason>`.
3. Adopt the submodule + baseline workflows via `scripts/init.mjs` if the
   repo wants the gates on every push.
