# Red-Eye Session Contract (`aiggp.session/v1` x `radredeye`)

This document defines the boundary between DevGate's `gameSessionStart` contract (`aiggp.session/v1`) and the `radredeye` capture, review, and failure-registry crates. Both systems stay independent by default; when a session opts into visual capture, they join on two immutable strings (`seed` and `capture.stream_id`) without sharing runtime state.

---

## 1. Opt-In Rule

A `play` or `work` session NEVER starts `radredeye` capture unless the caller declares the `capture` object in the session manifest:

```json
{
  "schema": "aiggp.session/v1",
  "kind": "play",
  "game": "mergekingdom",
  "phase": "alpha",
  "opened_at": "2026-11-01T12:00:00Z",
  "opened_by": "runtime:godot-4.7",
  "seed": "1337",
  "scene": "res://src/main/Main.tscn",
  "build": "0.1.0+git.d26d94c",
  "capture": {
    "stream_id": "mergekingdom-alpha-1337",
    "review": true
  }
}
```

- When `capture` is omitted, `game_session_start.py` prints `capture: none` and `engines/godot/game_session_hooks.gd` does not instantiate or enable `radredeye_capture`.
- When `capture` is present, `capture.stream_id` MUST be a non-empty string (`session-01`); an empty or missing `stream_id` is refused with exit code `2` before any session log row is written.

---

## 2. `stream_id` Naming Convention (One Owner, Never Derived Twice)

`capture.stream_id` is chosen once by the session opener (the engine hook or test harness) and passed into both `game_session_start.py` and `radredeye_capture`.

- **Recommended convention**: `<game>-<phase>-<seed>` (for example, `mergekingdom-alpha-1337`), or `<game>-<seed>-<run_nonce>` when `phase` is omitted.
- **Single-source rule**: Consumers (`hub/sessions.py`, `radredeye-review`, failure-registry queries) MUST read `capture.stream_id` verbatim from the manifest or registry entry and MUST NOT recompute it from `(game, phase, seed)`. If two tools derived the stream identifier independently, a missing `phase` or formatting difference would silently break the join.

---

## 3. `seed` (Run Identity) vs `ReviewLine.seed` (Frame Pixel Hash)

The identifier `seed` appears in two places with distinct meanings. Confusing them breaks determinism triage:

| Field | Owner | Meaning | Example |
|---|---|---|---|
| `aiggp.session/v1` `.seed` | `game_session_start.py` / `failure-registry.jsonl` | The deterministic RNG / run seed supplied when the play-session booted (`session-02`). Identifies the *run*. | `"1337"` |
| `radredeye_review::gates::ReviewLine.seed` | `crates/radredeye-review/src/gates.rs` | A hex content hash of a single frame's RGB buffer (`pixel_hash`), used by `radredeye-review` to deduplicate identical frames and compare determinism across two frame directories. Identifies a *frame buffer*. | `"a3f901c2048b7e11"` |

When `radredeye-review`'s `DETERMINISM` gate detects a frame hash mismatch between two runs of the same session seed, the failure logged to `.guardrails/failure-registry.jsonl` records the **session run seed** in `seed` (e.g. `"1337"`) and the capture stream in `stream_id` (e.g. `"mergekingdom-alpha-1337"`), while frame hashes stay in `error_message` / `root_cause`.

---

## 4. Godot Hook Wiring (`engines/godot/game_session_hooks.gd`)

On play-session boot, `GameSessionHooks.start_play_session(...)`:

1. Builds the `aiggp.session/v1` manifest (`kind: "play"`, `game`, `opened_at`, `opened_by`, `seed`, `scene`, `build`, and optional `phase`, `scope`, `capture`).
2. Invokes `python3 <devgate>/scripts/game_session_start.py --manifest <tmp> --root <project_root>`.
3. If `game_session_start.py` exits non-zero (`2` refused, `1` cannot say), logs the refusal via `push_error` and aborts the play-session (`quit_on_refusal` / `SceneTree.quit(exit_code)`).
4. If exit is `0` and `capture.stream_id` is present, probes for `res://addons/radredeye_capture/screenshot_autosave.gd`. When the addon is installed, attaches a capture node configured with `output_directory = "user://redeye_captures/" + stream_id` and `enabled = true`. When the addon is absent, records an explicit warning without failing the session.

---

## 5. Failure Registry Join (`sessions.jsonl` <-> `failure-registry.jsonl`)

When a play-session or `radredeye-review` gate logs a failure via `scripts/log_failure.py`, it passes `--seed <seed>` and `--stream-id <stream_id>`:

```bash
python3 scripts/log_failure.py \
  --error-message "DETERMINISM gate failed at frame 0042" \
  --category regression --severity high \
  --affected-files src/autoload/game_manager.gd \
  --fix-commit pending \
  --regression-pattern "randi\\(\\)" \
  --prevention-rule "route gameplay RNG through the seeded session generator" \
  --seed "1337" \
  --stream-id "mergekingdom-alpha-1337" \
  --status active
```

- `scripts/game_session_start.py` surfaces `[seed=<seed> stream=<stream_id>]` on matching registry hits in the session-start advisory block so the next agent or play run sees which deterministic seed and capture stream produced the regression.
- `hub/sessions.py` joins `.guardrails/sessions.jsonl` rows with `.guardrails/failure-registry.jsonl` entries on `capture.stream_id == entry.stream_id` (primary key) or `(session.seed == entry.seed and entry.seed != "")` (seed fallback when `stream_id` was not recorded).
