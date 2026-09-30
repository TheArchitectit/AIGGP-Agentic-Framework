# gameSessionStart — Design

**Date:** 2026-09-29
**Status:** Approved for implementation planning
**Repo:** AIGGP-Agentic-Framework (evolved in place; upstream merge is the delivery path)
**Testbed:** MergeKingdom (living integration)

## Problem

AIGGP has no session lifecycle. Work-sessions (an agent opening a game repo to
edit) and play-sessions (the game runtime booting a run) both start silently:
nothing emits context, nothing records that a session happened, and the
existing determinism policy ("an unseeded crash is not comparable") is only
enforced *after* a crash, when it is most expensive. This design introduces
`gameSessionStart`: one shared session-manifest contract served by both sides,
five agent carriers plus the engine side, advisory context at session start,
and exactly one hard check — relocated from crash-time to boot-time.

## Goals

1. One contract: every session — work or play — is described by the same JSON
   manifest (`aiggp.session/v1`).
2. Advisory context at session start: phase-gate status, failure-registry hits
   for the declared scope, pre-work-check pointer, capture-stream pointer
   (red-eye) when declared — filtered by session kind.
3. One hard rule on both sides: schema-invalid manifests are refused everywhere;
   play-sessions with `determinism.enabled` refuse to start without a seed.
4. Single brain: all rule logic lives in one module; carriers are thin native
   adapters. The seed rule is implemented exactly once.
5. Offline-first: session start never requires the network or the hub. The
   local append-only session log is the source of truth.

## Non-goals

- Hub server work, fleet dashboards, or session streaming (the log is designed
  as their future feed; nothing in this delivery blocks on them).
- Scope hard-gating on the agent side (pi-extension Law 2 already owns that).
- Real-time cross-session coordination.
- Vision-pipeline enrichment (`VISION_ENABLED` review tools): the `capture`
  block is designed to carry it; the integration itself is a later delivery
  and this plan does not block on it.

## Architecture (the hybrid)

**One brain, native hands, optional filing cabinet.**

1. **Brain — `scripts/game_session_start.py`** (Python, stdlib-only, matching
   the rest of `scripts/`). Owns everything that must never diverge: manifest
   schema validation, the seed hard rule, advisory context assembly, and the
   append-only session log write. Emits two forms of one result: machine JSON
   and a human-readable advisory block.
2. **Native hands — one adapter per carrier, each in its host's own idiom.**
   Adapters translate host event → manifest fields, invoke the brain, and map
   the brain's verdict to native behavior (inject context / refuse). Business
   logic in an adapter is a defect. The exception is the Godot hook, which
   *constructs* runtime manifest fields only the engine knows (seed, scene,
   build) — the rule that judges them still lives in the brain.
3. **Filing cabinet — `.guardrails/sessions.jsonl`**, append-only, written by
   the brain on every accepted session. A future `hub/sessions.py` ingests this
   log for fleet visibility. The hub is a consumer of the log, never in the
   session-start path.

## Components

| Component | Path | Role |
|---|---|---|
| Brain | `scripts/game_session_start.py` | Validate, rule, advise, log |
| Manifest schema | `.guardrails/prevention-rules/session-manifest.schema.json` | `aiggp.session/v1` definition |
| Session log | `.guardrails/sessions.jsonl` | Append-only history of accepted sessions |
| Godot engine hook | `engines/godot/game_session_hooks.gd` | Play-session side: build runtime manifest, refuse on hard rule |
| Red-eye contract note | `docs/REDEYE-SESSION-CONTRACT.md` | stream-id/seed contract with radredeye; capture opt-in |
| Claude Code adapter | `templates/hooks/claude-code/session-start.sh` | `SessionStart` hook; advisory → stdout |
| pi-extension adapter | `templates/hooks/pi-extension/session-init.ts` | Session-init handler; advisory → SessionStore/context |
| Codex CLI adapter | `templates/hooks/codex/session-start.sh` | Shell-contract shim |
| OpenCode adapter | `templates/hooks/opencode/session-start.mjs` | Plugin-hook shim |
| Xiaomi MiMo adapter | `templates/hooks/mimo/session-start.sh` | Shell-contract shim |
| Spec | `openspec/specs/game-session-start/spec.md` | Requirements + scenarios (below) |

Adapters are copied/consumed via `init.mjs` (new `--carriers` step), same as
the workflow templates. They are never vendored as consumer-owned logic.

## The manifest (`aiggp.session/v1`)

```json
{
  "schema": "aiggp.session/v1",
  "kind": "play" | "work",
  "game": "mergekingdom",
  "phase": "alpha",
  "opened_at": "2026-09-29T17:04:00Z",
  "opened_by": "runtime:godot-4.6" | "agent:claude-code",
  "scope": ["src/autoload/**", "data/**"],
  "seed": "1337",
  "scene": "res://scenes/main.tscn",
  "build": "0.1.0-beta",
  "capture": {"stream_id": "mk-alpha-1337", "review": true},
  "agent": {"carrier": "claude-code", "session_id": "abc"}
}
```

- `schema`, `kind`, `game`, `opened_at`, `opened_by` — required, both kinds.
- `seed` — REQUIRED iff `kind == "play"` and the project's `game-manifest.json`
  has `determinism.enabled: true`. Play-session advisory content otherwise.
- `scene`, `build` — play-sessions only.
- `agent` (`carrier`, `session_id`) — work-sessions only.
- `capture` (`stream_id`, `review`) — optional, both kinds; `stream_id` is
  required whenever the block is present. Declares the radredeye capture stream
  this session is tied to (see Red-eye integration). A play-session passes it to
  the `radredeye_capture` addon at boot. Absent block = no capture — the advisory
  says so honestly rather than implying a stream was watched.
- `phase`, `scope` — recommended both kinds; `scope` filters registry advice.
  When `phase` is absent the advisory block reports `phase: unknown` and omits
  the phase-gate list entirely (honest-empty: no phase claimed, no gates listed).
- One enum (`kind`), not two schemas: the hub, the session log, and future
  phase-gate work (`game-matrix-01`) see one row type.
- Manifests are immutable once logged. A reopened session is a new row — the
  failure-registry's append-only ethic applied to sessions.

## Data flow

Whoever opens the session (Godot hook or carrier adapter) constructs the
manifest → brain validates schema + seed rule → on hard-rule failure the brain
exits nonzero and the opener refuses the session → on success the brain appends
the manifest to `.guardrails/sessions.jsonl` and returns the advisory block:

- current phase's required gates (from the phase matrix), for `work` sessions
- failure-registry entries matching `scope`, both kinds
- pre-work-check pointer, `work` sessions
- screen-inventory warnings, `play` sessions
- red-eye pointer when `capture` is declared: the `stream_id` plus the
  inspection surface (`get_frame`, `semantic_diff`, gate report) — both kinds.
  When no `capture` is declared, an honest-empty `capture: none` line instead.

Advice is filtered by `kind` (a work-session doesn't hear about scene count; a
play-session doesn't hear about lint rules).

## Enforcement

One hard rule, stated for the OpenSpec verbatim:

> **WHEN** a session manifest's `kind` is `play` and the project's
> `game-manifest.json` has `determinism.enabled: true` **AND** the manifest
> lacks a non-empty `seed` **THEN** `game_session_start.py` exits nonzero and
> the Godot hook refuses to start the play-session. The same refusal applies to
> any manifest failing `aiggp.session/v1` schema validation, on either side.

Everything else is advisory; the brain prints it, nothing blocks. This is the
existing determinism-evidence policy ("an unseeded crash is not comparable") —
relocated from crash-time to boot-time, where it is cheapest. It matches the
house rule that gates refuse to lie: a run with determinism on but no seed
would look comparable and is not.

**Failure behavior — fail-closed at the schema level, fail-open at the advice
level:**

| Condition | Behavior |
|---|---|
| Malformed manifest (either side) | Hard refuse. Nothing that cannot describe itself runs. |
| Missing `game-manifest.json` | `work`: proceed with explicit `determinism: unknown` banner (honest "I know nothing" — never print "clean"). `play`: hard refuse — the runtime hook only exists in game repos that must have one. |
| Brain exception mid-run | Nonzero exit, partial output flushed to stderr. Adapter maps to native failure (hook block, `recordHalt`, `push_error` + abort). |
| Duplicate session start | Append anyway. The log is history, not a set (same honesty-in-duplicates stance as the failure registry). |
| `.guardrailsignore` / `guardrails-allow` | Filter registry-hit *advice* only. Never the hard rule — you cannot annotate away a missing seed. |

**Exit codes:** `0` = valid session (advisory printed); `2` = hard-rule refusal
(matches `game_regression.py` `--fail-if-empty` "2 means refused" convention);
`1` = brain malfunction.

## Adapter contract

Each shim implements exactly three steps:

1. Translate host event → manifest JSON fields (`kind: "work"`,
   `agent.carrier`, `session_id`, `scope`).
2. Invoke `python3 scripts/game_session_start.py --stdin`.
3. Map the verdict to native behavior: exit 0 → inject advisory block via the
   host API; exit 2 → refuse/block per host idiom.

Anything beyond those three steps is a defect. Claude Code + Godot land first;
the other four shims follow the contract once those prove it.

## Red-eye integration (radredeye)

radredeye is the framework-agnostic visual capture layer (6 MCP tools:
`get_frame`, `submit_frame`, `semantic_diff`, `list_streams`, `list_sinks`,
`health`; 5 review gates: CAPTURE_OK / SCORE_PRESENT / LOOP_CLOSED / PERF /
DETERMINISM; a SQLCipher failure registry compatible with
`log_failure.py`). gameSessionStart names the session those eyes belong to.
Three ties, each onto something radredeye already has:

1. **Run seed → review comparability.** radredeye-review's `seed(frame)` is a
   per-frame pixel content hash — a frame fingerprint for dedup, never a run
   identity. The manifest's `seed` is the run identity. When `capture` is
   declared, the brain records `stream_id` alongside `seed` on the session log
   row, and regression entries appended for that stream (via
   `radredeye-registry`, the same append-only `.guardrails/failure-registry.jsonl`
   contract as `log_failure.py`) carry the same `seed` + `stream_id`. A scored
   frame and a crash then join one comparable identity — the session row. This
   is the game-regression determinism-evidence requirement ("record the seed and
   input trace") delivered at capture time instead of crash time: an unseeded
   run cannot masquerade as a comparable one. `seed(frame)`'s frame-hash
   semantics are untouched — the two seeds solve different problems, and the
   manifest names both: `seed` (run) plus `capture.stream_id` (frame stream).
2. **Work-session advisory gets eyes.** When `capture` is declared the advisory
   prints the stream id and the inspection surface: `get_frame`,
   `semantic_diff` (replay comparison), gate-report status. An agent at session
   start sees how the game *looks*, not just how it lints. No `capture` → the
   honest-empty `capture: none` line, never silence.
3. **Review regressions flow to the shared registry.** A failed DETERMINISM or
   LOOP_CLOSED gate becomes a registry entry carrying `stream_id` + `seed`;
   the next session-start advisory surfaces it through the existing
   scope-filtered registry-hit block. The loop closes: capture → review →
   registry → session-start context → better edits.

**Guard rails (none of these change):**

- Capture stays opt-in — red-eye's own rule ("no hidden capture") matches the
  manifest's: a declared `capture` block *is* the opt-in.
- The brain stays stdlib-Python and offline. It never calls MCP — it *mentions*
  the tools; MCP-speaking carriers query them mid-session.
- The hard rule is unchanged. Nothing here adds a second gate.
- The 3-step adapter contract is unchanged; `capture` is just more manifest
  fields the host fills in.

**Layout:** `engines/godot/game_session_hooks.gd` composes with the
`radredeye_capture` addon at boot (explicit opt-in, same integration pattern as
`AdGameHooks`); `docs/REDEYE-SESSION-CONTRACT.md` records the stream-id/seed
contract for radredeye-side readers. Vision-pipeline enrichment (the
`VISION_ENABLED` review tools) rides the same `capture` block in a later
delivery — see Non-goals.

## Testing & rollout

**AIGGP CI** — `tests/test_game_session_start.py` (Python, no engine needed,
mirroring `test_game_regression.py`): schema validation matrix (valid/invalid
manifests, including the `capture` block: accepted with `stream_id`, rejected
without), the seed rule across all four combinations of `determinism.enabled`
× `seed`, kind-filtering of advisory output, red-eye advisory echo of
`stream_id` and the honest-empty `capture: none` line, exit-code contract,
append-only log semantics (session row carries `seed` + `capture.stream_id`
when declared).

**MergeKingdom** — living integration: wire the Godot hook + Claude Code hook
there; its CI run is the recorded evidence for the full stack. Where the game
declares capture, wire `radredeye_capture` through the Godot hook's opt-in.
(A synthetic fixture with headless Godot in AIGGP's own CI remains a possible
later hardening; MergeKingdom goes first.)

**Rollout order:**

1. Spec + schema + brain + tests in AIGGP (including the `capture` block)
2. Godot engine glue — prove the play side on MergeKingdom, with opt-in
   `radredeye_capture` wiring; write `docs/REDEYE-SESSION-CONTRACT.md` +
   red-eye-side regression entries carrying `seed` + `stream_id`
3. Claude Code + pi-extension shims — prove the work side (advisory carries the
   red-eye pointer when `capture` is declared)
4. Codex / OpenCode / Xiaomi MiMo shims to the adapter contract
5. `hub/sessions.py` ingestion (deferred; designed-for)

`init.mjs` gains the `--carriers` template-copy step. CHANGELOG + CHECKSUMS
regenerate per repo convention.

## Open mapping

- New spec `openspec/specs/game-session-start/spec.md` with Requirements and
  Scenarios covering: shared manifest schema, seed hard rule both sides,
  advisory content, append-only session log, adapter contract, honest-empty
  (a session that evaluated nothing does not report clean), and the red-eye
  contract (`capture` block with required `stream_id`; session-linked registry
  entries carry `seed` + `stream_id`).
- The phase matrix gains `game-session-start` as a named gate other rows can
  reference later (`game-matrix-01` remains planned).