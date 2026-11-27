# game-session-start sprint plan

At `cb2205c` the index recorded **UNPROVEN**. Collect evidence for the existing historical claim. A present-day passing fixture alone cannot justify its ledger transition.

Route acceptance to the **framework tooling maintainer and the consuming game owner**. Bring a disposable project with explicit engine, session or scene inputs to intake.

**Session adapters.** Run the five carrier entry points and preserve a separate decision and log receipt for each. [Role and adapter assignments](../../SPRINTS.md#session-adapter-matrix).

## Sprint assignments

| Sprint and role | Work product |
| --- | --- |
| S1. Lead | Pin the spec and repository revision. Map the requirement IDs below to their source and establish who can accept framework behavior and any outstanding consumer evidence. |
| S2. Luna writer | Exercise the shared manifest and each of the five session adapters on accepted work and refused play fixtures. Record carrier identity, exit status and appended-log count. Start at [tests/test_game_session_start.py](../../../tests/test_game_session_start.py). |
| S2. Luna evidence collector | Trace the chosen scenarios from input to output. For each ID, record the fixture, source and test revisions, expected outcome, observed result and evidence location. Flag any absent fixture. |
| S3. Independent auditor | In another session, replay the cited entry point at the recorded SHA. Compare the results to the acceptance scenarios below, including refusals where specified. Return a verdict per ID and identify untested boundaries. |
| S4. Lead and accountable owner | Recheck the receipts for framework behavior and any outstanding consumer evidence. Publish the accepted scope or document the outstanding decision. Record the final SHA and the applicable checks. |

## Requirement acceptance

| ID and published contract | Scenarios to account for |
| --- | --- |
| [`session-01`](../../specs/game-session-start/spec.md#requirement-one-manifest-describes-every-session) One manifest describes every session | the required fields, both kinds / an unknown field is refused, and nothing is logged / the capture rule is a conditional, not a blanket requirement / `opened_at` is RFC 3339 UTC / reading the schema alone does not look complete |
| [`session-02`](../../specs/game-session-start/spec.md#requirement-the-seed-rule-is-one-hard-rule-at-boot) The seed rule is one hard rule, at boot | the determinism and seed matrix / a play root without a game manifest is refused / a policy that cannot be read is not guessed |
| [`session-03`](../../specs/game-session-start/spec.md#requirement-the-advisory-block-is-kind-filtered-and-honest-empty) The advisory block is kind-filtered and honest-empty | a block that was not evaluated says so / kind filtering / capture is named or honestly absent / registry advice is scoped, and ignored entries are not asserted |
| [`session-04`](../../specs/game-session-start/spec.md#requirement-accepted-sessions-append-to-one-immutable-log) Accepted sessions append to one immutable log | a refusal logs nothing / a reopened session appends / a play row carries the capture identity |
| [`session-05`](../../specs/game-session-start/spec.md#requirement-the-gap-line-reads-the-scanners-report-never-a-second-inventory) The gap line reads the scanner's report, never a second inventory | the number is read, not recomputed / a report from another tree is not this session's number / an absent report is unknown, never zero |
| [`session-06`](../../specs/game-session-start/spec.md#requirement-exit-codes-say-which-kind-of-signal-this-is) Exit codes say which kind of signal this is | what counts as refused, and what as cannot say / the two codes are not interchangeable / a runner must not guess |

## Evidence handoff

Record the source and test revisions, actual inputs, expected and observed outcomes, exit status and receipt location. Give the independent auditor the artifact and expected digest. Mark an unexecuted check with its reason.

DG-02 tracks DG02-U-165, DG02-U-166, DG02-U-167, DG02-U-168, DG02-U-169, DG02-U-170. [Row dispositions and batch seals](../../changes/dg-02-evidence-ledger-reconciliation/README.md).

[Published specification](../../specs/game-session-start/spec.md) and [sprint dispatch](../../SPRINTS.md).
