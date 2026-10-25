# Design: gameSessionStart (step 1 of the approved rollout)

Source of intent: `docs/superpowers/specs/2026-09-29-game-session-start-design.md`
(approved for implementation planning, 2026-09-29). This document records the
decisions this change had to make that the design left to implementation, and
the boundaries it deliberately does not cross.

## The brain validates; carriers translate

`scripts/game_session_start.py` owns manifest validation, the seed rule, the
advisory assembly and the log write. It is stdlib-only plus two in-repo
helpers it shares rather than copies: `gate_common` (root contract, glob
matching, `.guardrailsignore`) and `gate_overlay` (merged bundled + project
failure registry). No carrier adapter exists in this change.

## The Draft-07 subset, and the two rules it cannot express

The brain carries a subset validator with the same rule set `rules_check.py`
uses (`type`, `enum`, `pattern`, `required`, `properties`,
`additionalProperties: false`, `items`, `$ref`) plus `minLength`/`minItems`.
That is enough for the manifest shape and not enough for the conditionals the
contract needs:

1. **`capture` present implies a non-empty `stream_id`.** Measured nuance: the
   validator applies a sub-schema only when its key is present, so a static
   `required: ["stream_id"]` inside `capture` is not vacuous - it refuses the
   present case and says nothing about an absent one. The brain keeps its own
   explicit check anyway, because the design names it as a brain rule and a
   future validator upgrade must not silently drop it. A test pins the
   conditional (`capture` without `stream_id` refused; no `capture` accepted).
2. **`play` under `determinism.enabled: true` requires a non-empty `seed`.**
   This depends on the *project's* `game-manifest.json`, not on the manifest
   being validated, so no schema over the manifest can express it.

The schema's `description` names both and points at this spec, so a reader of
the schema alone never thinks validation is complete.

## `determinism.enabled`: opt-in, and absent means off

The design required the field to land with the rule. It is documented in
`scripts/game-framework-README.md` under the game-manifest contract:

- `determinism.enabled: true` - a play-session must declare a seed.
- `determinism.enabled: false` - the rule is off.
- key absent - off. A project that never declared a policy cannot be broken
  retroactively, so opting in is the only way to be subject to the rule.
- value present but not a boolean - exit 1 (cannot say). The brain will not
  guess whether a run is comparable.
- `game-manifest.json` absent - a `play` session is refused (exit 2, the
  runtime hook only exists in game repos that must have one); a `work` session
  proceeds with `determinism: unknown`.

## The advisory block

Deterministic by construction: no timestamps, host names or wall-clock values
reach the lines, so a test can compare them exactly.

Work sessions print, in order: header, `phase`, `phase gates`, `determinism`,
`registry hits`, `pre-work check`, `worst-tracked gaps`, `capture`.
Play sessions print: header, `determinism`, `registry hits`,
`screen inventory`, `capture`.

- **Phase gates are `unknown`, and that is the honest answer.** The phase
  matrix is `game-matrix-01`, marked planned and explicitly forbidden from
  claiming enforcement ("no gate in this repository may claim phase-matrix
  enforcement"). Printing a gate list here would be that false claim.
- **Screen inventory is a pointer, not a scan.** `scene_inventory.py` prints a
  human report and returns an exit code; it has no structured output. Parsing
  its prose at session start would be a second, fragile implementation of
  "what the inventory found". The play-side block therefore states that the
  inventory was not evaluated at session start and names the command; the
  Godot hook delivery (rollout step 2) owns firing it. This is a stated
  boundary, not an implied pass.
- **Registry hits** list unresolved entries whose `affected_files` or
  `file_glob` overlap the declared scope, capped at five, sorted by
  `failure_id`, with `.guardrailsignore` filtering advice only. An
  unreadable merged registry renders `unknown` - the bundled baseline shipping
  zero entries means nothing was read, not "no failures".

## The gap line

`worst-tracked gaps: N` is read from the gap scanner's own `--json` output at
`.guardrails/spec-gap-report.json` (or `--gap-report PATH`). The brain never
runs the scanner: the package's whole premise is one inventory source, and a
second scan at session start would also make the line disagree with the CI row
that judged the same commit.

- N is the count `--fail-on-gaps` acts on: `unspaced + partially_tracked +
  uncovered_ids`. `claimed_but_absent` never contributes, matching the
  scanner's rail 3.
- The report's `root` must resolve to the session's root. A report from
  another tree is `unknown` naming that tree - a stale artifact must not be
  presented as this session's inventory.
- Absent, unreadable, or wrong-shaped report: `unknown` with the reason. The
  string `worst-tracked gaps: 0` never appears without a report saying 0.
- When the report names unspaced capabilities, one more line names the worst
  (`worst: <capability> [<evidence>]`), because the scanner already sorted
  them worst-tracked first.

**Stated boundary: nothing writes the report to the default path yet.** The
documented producer is the gap scanner itself:

```
python3 scripts/spec_gap_scan.py --root . --json > .guardrails/spec-gap-report.json
```

Until a repository runs that (or a CI row publishes it as an artifact and a
session-start adapter fetches it), the line honestly reads `unknown`. Adding
such a producer was deliberately not folded in: running the scan from the
brain is the second inventory this box forbids, and a committed report would
be stale by the next commit.

## Exit codes

`0` accepted, `2` refused a known session, `1` cannot say. This is the inverse
of the secret-scan family (`1` findings, `2` scanner unusable). Both
conventions now live in `scripts/`; the spec states the contrast as a
requirement (session-06) so a runner must read it rather than assume the
families agree.

## The session log

`.guardrails/sessions.jsonl`, one canonical row per accepted session
(`sort_keys`, compact separators, ASCII-escaped) equal to the validated
manifest. Canonical bytes make two identical manifests produce identical rows
and let a test compare rows with `==`. Immutability is the failure registry's
ethic applied to sessions: a reopened session is a new row, duplicates
included.

## What this change does not do

Rollout steps 2-5 of the design, each its own reviewed delivery:

- the Godot engine hook and the play-side screen-inventory block;
- the Claude Code, pi-extension, Codex, OpenCode and Xiaomi MiMo adapters;
- `docs/REDEYE-SESSION-CONTRACT.md` and the red-eye registry join;
- `hub/sessions.py` ingestion of the log;
- a producer for the gap report at its default path.
