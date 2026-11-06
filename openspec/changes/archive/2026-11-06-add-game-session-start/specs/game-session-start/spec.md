# Spec: gameSessionStart

## ADDED Requirements

### Requirement: One manifest describes every session
<!-- id: session-01 -->
Every session SHALL be described by one `aiggp.session/v1` manifest, validated
against `.guardrails/prevention-rules/session-manifest.schema.json`. Unknown
fields SHALL be refused, and `kind` SHALL be the single enum `play`|`work`.
Two rules SHALL be enforced by the brain because the static subset cannot
express them: a declared `capture` block SHALL carry a non-empty `stream_id`,
and a `play` session under determinism SHALL carry a non-empty `seed`.

#### Scenario: the required fields, both kinds

- **WHEN** a manifest is validated
- **THEN** `schema`, `kind`, `game`, `opened_at` and `opened_by` are required
  of a `work` session and of a `play` session alike; `seed`, `scene` and
  `build` are play-side fields and `agent` is a work-side field, and declaring
  none of them is not an error

#### Scenario: an unknown field is refused, and nothing is logged

- **WHEN** a manifest carries a field the schema does not declare
- **THEN** the brain exits 2 naming the field, and the session log is not
  written

#### Scenario: the capture rule is a conditional, not a blanket requirement

- **WHEN** a manifest declares `capture` without a `stream_id`
- **THEN** it is refused naming `stream_id`
- **AND WHEN** a manifest declares no `capture` block at all
- **THEN** it validates - the rule fires only when the block is present

#### Scenario: `opened_at` is RFC 3339 UTC

- **WHEN** `opened_at` carries a numeric offset (`+02:00`) or no zone
- **THEN** the manifest is refused by the schema pattern; only the `Z` form is
  accepted

#### Scenario: reading the schema alone does not look complete

- **WHEN** a reader opens the schema
- **THEN** its description names both conditionals, the brain that enforces
  them and this spec, so the schema is never mistaken for the whole contract

### Requirement: The seed rule is one hard rule, at boot
<!-- id: session-02 -->
**WHEN** a manifest's `kind` is `play`, the project's `game-manifest.json` has
`determinism.enabled: true`, **AND** the manifest lacks a non-empty `seed`
**THEN** the brain SHALL exit 2 and refuse the session, appending nothing, and
the engine hook SHALL refuse to start the play-session. The rule SHALL have
exactly one implementation, in the brain. An absent `determinism.enabled` SHALL
mean off: the rule is opt-in.

#### Scenario: the determinism and seed matrix

- **WHEN** `determinism.enabled` is true and a seed is present
- **THEN** the play-session is accepted
- **WHEN** it is true and the seed is absent or blank
- **THEN** the session is refused (exit 2)
- **WHEN** it is false, or the key is not declared
- **THEN** no seed is required and the session is accepted

#### Scenario: a play root without a game manifest is refused

- **WHEN** a `play` session opens in a root with no `game-manifest.json`
- **THEN** the brain refuses it (exit 2): the runtime hook only exists in game
  repos that must have one
- **AND WHEN** a `work` session opens in that same root
- **THEN** it proceeds with an explicit `determinism: unknown` banner - never
  `clean`, never a silent default

#### Scenario: a policy that cannot be read is not guessed

- **WHEN** `determinism.enabled` is present and is not a boolean
- **THEN** the brain exits 1 (cannot say) rather than choosing whether the run
  is comparable

### Requirement: The advisory block is kind-filtered and honest-empty
<!-- id: session-03 -->
The brain SHALL return one advisory block as both human lines and machine
JSON. `work` SHALL carry the phase and its gates, registry hits, the
pre-work-check pointer and the gap line; `play` SHALL carry registry hits and a
screen-inventory block. Both SHALL carry the determinism banner and the capture
pointer, or an honest-empty `capture: none`. Any block that could not be
evaluated SHALL say so explicitly and SHALL NOT render as a clean or zero
result.

#### Scenario: a block that was not evaluated says so

- **WHEN** a `work` session names no phase
- **THEN** the block prints `phase: unknown - no phase claimed, no gates
  listed` and lists no gates
- **AND WHEN** it names a phase
- **THEN** the gate list is `unknown` because the phase matrix is planned
  (game-matrix-01) and no gate in this repository may claim it
- **AND WHEN** `.guardrails/pre-work-check.md` is absent
- **THEN** the pointer reads `absent`, not a path that does not exist

#### Scenario: kind filtering

- **WHEN** the session is `work`
- **THEN** no scene or screen-inventory line is printed
- **AND WHEN** the session is `play`
- **THEN** no phase-gate list and no gap line is printed

#### Scenario: capture is named or honestly absent

- **WHEN** `capture` is declared
- **THEN** the block names the `stream_id` and the inspection surface
  (`get_frame`, `semantic_diff`, the gate report)
- **AND WHEN** it is not declared
- **THEN** the block prints `capture: none` - never silence, and never an
  implied stream

#### Scenario: registry advice is scoped, and ignored entries are not asserted

- **WHEN** the session declares `scope`
- **THEN** only unresolved registry entries overlapping that scope are listed,
  with the scope named in the line
- **AND** `.guardrailsignore` SHALL filter this advice only - never the hard
  rule
- **AND WHEN** the merged registry cannot be read
- **THEN** the block reads `registry hits: unknown`, not `0`

### Requirement: Accepted sessions append to one immutable log
<!-- id: session-04 -->
Every accepted session SHALL be appended to `<root>/.guardrails/sessions.jsonl`
as one canonical JSON row equal to the validated manifest, and an existing row
SHALL never be updated. A reopened session SHALL append a second row - the log
is history, not a set. A refused session SHALL append nothing. A row SHALL
carry `seed` and `capture.stream_id` when declared, so a capture or review
entry appended later can join it by session.

#### Scenario: a refusal logs nothing

- **WHEN** a session is refused for any reason
- **THEN** the log file is unchanged

#### Scenario: a reopened session appends

- **WHEN** the same manifest is opened twice
- **THEN** the log carries two identical rows in order

#### Scenario: a play row carries the capture identity

- **WHEN** a play-session declares a seed and a capture stream
- **THEN** its log row carries both, unchanged

### Requirement: The gap line reads the scanner's report, never a second inventory
<!-- id: session-05 -->
The `work` advisory SHALL print `worst-tracked gaps: N` read from the
spec-gap scanner's `--json` report, never from a second inventory: the brain
SHALL NOT run the scanner. N SHALL be the count `--fail-on-gaps` acts on
(unspaced + partially tracked + uncovered ids); CLAIMED-BUT-ABSENT SHALL never
contribute. A missing, malformed, or foreign report SHALL render `unknown` with
its reason, and SHALL never render `0`.

#### Scenario: the number is read, not recomputed

- **WHEN** the report says 7 and the root has no source files at all
- **THEN** the line prints 7 - a rescan would have printed 0 or refused

#### Scenario: a report from another tree is not this session's number

- **WHEN** the report's `root` does not resolve to the session's root
- **THEN** the line prints `unknown` naming the other root

#### Scenario: an absent report is unknown, never zero

- **WHEN** no report exists at the documented path
- **THEN** the line prints `unknown` and the reason; the string
  `worst-tracked gaps: 0` does not appear

### Requirement: Exit codes say which kind of signal this is
<!-- id: session-06 -->
The brain SHALL exit `0` accepted, `2` refused a known session, or `1` cannot
say. `2` SHALL be the trustworthy refusal and `1` the malfunction - the
inverse of the secret-scan family, whose `1` is findings and `2` an unusable
scanner. The contrast SHALL be documented where both families are wired and
SHALL NOT be unified.

#### Scenario: what counts as refused, and what as cannot say

- **WHEN** the session is refused
- **THEN** the reason is known - a schema-invalid manifest, a play session
  without a seed under determinism, or a play session in a root with no
  `game-manifest.json` - and the exit code is 2
- **AND WHEN** the brain cannot evaluate
- **THEN** the exit code is 1 - an unreadable schema, no manifest supplied, or
  an unreadable determinism policy

#### Scenario: the two codes are not interchangeable

- **WHEN** a malformed manifest is supplied
- **THEN** the exit code is 2, because the session was refused and the reason
  is known
- **AND WHEN** no manifest is supplied at all
- **THEN** the exit code is 1, because the brain cannot evaluate anything

#### Scenario: a runner must not guess

- **WHEN** a runner wires session start into a pipeline beside a secret-scan
  step
- **THEN** it distinguishes the two families by reading this requirement, not
  by assuming they agree
