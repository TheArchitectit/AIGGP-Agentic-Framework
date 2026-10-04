# MC-side review — runner-toolchain-requests / fleet-toolchain-queue joint

**Date:** 2026-10-04 · **Reviewer:** Forge (Mission Control side)
**MC change package:** `TheArchitectit/missioncontrol` branch `feature/fleet-toolchain-queue` @ `55e7cd30` (local, unpushed at review time), base `ceb1d08` — verified live on GitHub.
**Hub contract:** `TheArchitectit/AIGGP-Agentic-Framework` branch `feature/runner-toolchain-requests` @ `69c16b5` (local, unpushed at review time) — **not readable by the reviewer**; this doc is written against the MC package's description of it plus the live MC tree.

## Verdict

The MC package is sound and its live-tree claims check out (all ten load-bearing
claims verified against `ceb1d08`, see below). Three design gaps must be
settled **hub-side before MC implements**, because MC's proxy shapes follow
`mon-tc-02`/`mon-tc-03`/`mon-tc-05` and two of the gaps live exactly in those
shapes. Settling them here is cheaper than during implementation.

## Gaps to resolve hub-side (design.md §Decisions amendment)

### G1 — Actor-claim protocol is undefined where MC's tier pattern cannot carry it

MC's existing admin-tier check (`src/middleware/auth/mod.rs:169`) is
**API-key-only by construction**: it derives `scopes` from the key record and
explicitly leaves JWT/cookie sessions unchanged. MC's decide route must accept
*cookie-session admins* as well as admin-tier keys. "Extend the /api/v1/keys
pattern" therefore does not describe the session case — an implementer will
improvise a scopes-equivalent for sessions, and that improvisation becomes the
de-facto contract.

**Requested (hub side, `mon-tc-03`):** define the signed actor-claim shape in
design.md — fields (`principal`, `timestamp`, `nonce`, `signature`), signing
key provenance (MC-held mesh credential), the exact statuses the hub returns
for: bad signature (401), refused credential class (403), replayed nonce or
concurrent decision (409), and the clock-skew tolerance for `timestamp`.
MC then cites that section instead of inventing semantics.

### G2 — Nonce issuer is unstated, and the wrong choice violates MC Requirement 1

MC Requirement 1 bans any persistent request state, including caches. If MC
were expected to *guarantee* nonce uniqueness across restarts, it would need
durable nonce state — directly conflicting. The consistent reading is:

**Requested (hub side, `mon-tc-03`):** state explicitly that **MC mints each
nonce per-decide in memory (never written to disk or logged) and the hub owns
replay detection** via its own nonce window. That keeps the only anti-replay
state where Requirement 1 says it belongs — the hub.

### G3 — Lane-image digest display vs the podman prohibition (one line, prevents a review cycle)

The queue scenario shows "current lane image digest" while root-tree
`fleet-runner-dashboard` L97 forbids digests in the *snapshot payload*. The
distinction (hub-reported evidence, not podman snapshot) is correct but lives
only in tasks 4.2/6.7, not in the spec text. An implementer grepping the spec
alone will either stall or "fix" the wrong thing.

**Requested (hub side, `mon-tc-02`):** label the read-response digest field as
**hub-owned observed evidence**, explicitly not sourced from runner snapshot
payloads. MC will mirror one sentence into its scenario.

## Corrections found during verification (MC package, small)

1. **PR language conflicts with standing rule.** proposal.md and tasks 6.6 say
   "pin both SHAs in the pull request" / "SHA and run URL in the pull
   request." Roger's standing rule is **branches only, never PRs**. Both repos
   should say "pin both SHAs in the branch handoff note."
2. **Spec-dir count.** `mission-control-rs/openspec/specs/` has **33** dirs at
   `ceb1d08`, not 34. Recheck the "34 before / 35 after" basis (may be counting
   a change dir).
3. **Adapters shapes.** `rad_a2a` is a **directory** in the live tree;
   `hermes.rs`/`loki.rs` are files. Task 1.1 should say "alongside `hermes.rs`,
   `loki.rs`, and the `rad_a2a/` module."

## Verified claims (all true at `ceb1d08`)

| Claim | Evidence |
|---|---|
| askama 0.12 + askama_axum 0.4 + axum 0.7, no Inertia, no `src/api/dashboard.rs` | Cargo.toml L14/33/34; ls |
| Router tiers `public_routes`/`protected_page_routes`/`auth_htmx_routes`/`protected_api_routes` | builder.rs L40/138/190/216 |
| Six SPA shell routes (`/admin`, `/admin/channels`, `/admin/groups`, `/runners`, `/logs`, `/projects/*rest`) | builder.rs L127–132 |
| `require_page_auth` layer ~L185 | builder.rs L187 |
| Admin prefix check line-exact at `middleware/auth/mod.rs:169`, `scopes_allow_admin` at L301 | sed L163–176 |
| `fleet/mod.rs routes()` = `/runners`, `/runners/:id/tasks`, `/ci-coverage` | L30–34 |
| `frontend-architecture` "SPA SHALL be removed" contradiction with router | spec L24 vs builder L127–132 — real, MC task 5.1 justified |
| auth-gate-coverage enumerates from router, reds unclassified mutations | spec Purpose verbatim |
| Root tree `fleet-runner-dashboard` L97 digest prohibition | verbatim match |
| Two openspec trees (code-level 33 specs; product-level 18) | ls counts |

## Landing sequence (unchanged, reconfirmed)

1. Hub branch `feature/runner-toolchain-requests` lands **with G1–G3 amended
   into design.md §Decisions** — this is the pin `69c16b5` → new SHA.
2. MC branch re-pins the dependency to the amended hub SHA, mirrors the one
   G3 sentence into its spec scenario, applies the three correction items.
3. MC implements against S0–S6 as written; gates 6.3/6.4 are the acceptance
   bar, not `openspec validate`.

**No pushes occurred to `missioncontrol` from this review.** This doc is a
branch in the hub repo only.
