# 2026-10-25 - the bundled silent-success allowlist was foreign again: 1,727 entries, and a gate now fails on them (`base-own-01`)

Requirement: `baseline-ownership` / `base-own-01` - *"Every entry in a bundled
baseline data file (failure registry, silent-success allowlist, prevention
rules, openspec specs) SHALL reference only paths, bugs, and capabilities of
this repository; a hygiene gate SHALL fail when a bundled entry references a
path absent from this tree."* The capability's own purpose states the stake:
*"a waiver in one repo can never silence a finding in another."*

The failure-registry half of that sentence was closed earlier today
(`docs/qa/2026-10-25-baseline-hygiene-foreign-entries.md`). This record is the
silent-success-allowlist half, which turned out to be the larger one.

## What was measured

`.guardrails/silent-success-allowlist.json` at `41d21b5`: **1,727 entries**,
**1,727** of which name a path absent from this tree.

| path prefix | entries |
|---|---|
| `internal/` | 1454 |
| `tests/` | 225 |
| `go/` | 40 |
| `cmd/` | 8 |

All 1,727 are family `go_return_nil_after_ignored_error` - a family this
repository *does* declare, which is why the "capabilities" clause alone would
have passed them. There is no `go/`, `internal/`, `cmd/` or `tests/` directory in
this checkout; the layout is gamerepo01's Go tree.

`bash scripts/silent-success-scan.sh` on the same tree: exit 0,
`0 allowlisted, 0 excluded by family exclude_globs, 1727 allowlist entr(ies)`.
The gate reported a number it never used: four families are enabled in the
bundled rules, none of them match a file here, so **every one of the 1,727
entries was inert** - 12,093 lines shipped to every install to suppress
findings in a tree this repository does not contain.

## It was a regression of a landed fix, three commits long

The file's own note said one thing and the file said another. Traced through
`git log --follow` with the entry count at each commit:

| commit | date | entries | what it did |
|---|---|---|---|
| `beedec1` | 2026-09-19 | **0** | QA H3 decontamination: emptied the file, wrote the "EMPTY by design" note |
| `16ce30e` | 2026-09-20 | **1725** | "retire the two fixed internal/admin/bootstrap.go markers" - a pre-decontamination copy written back over the decontaminated file, minus two entries |
| `b3f951b` | 2026-09-21 | 1724 | drops one dead entry |
| `eeb2884` | 2026-09-23 | 1727 | adds `cmd/admin-grant` markers |
| `239e30b` | 2026-09-27 | 1727 | adds `pruned_at` / `note_pruned`: *"allowlist verified intact (1727 entries)"* |

So a commit whose message says "retire the two ... markers" retired two and
restored 1,725, and three later commits edited the restored copy - one of them
recording it as *verified*. The current file carried **both** the
decontamination note ("the 1,726 gamerepo01 entries that shipped here until
2026-09-19 were decontaminated") **and** the `note_pruned` claim that they were
verified intact. Nothing read either sentence; the gate only counted.

This is the same class of error the failure-registry slice found in
`FAIL-20cc1a39`: a value that looks maintained because a later commit touched
it. A count in a message is not a check.

## Why it matters beyond tidiness

`scripts/silent-success-scan.sh` reads the allowlist from the **submodule**
(`devgate_root / .guardrails / silent-success-allowlist.json`, deliberately not
overlaid) and matches it against the **project** tree. That is exactly the
cross-repository suppression the capability exists to forbid: a bundled waiver
keyed into whatever tree the consumer is scanning.

It is live today, not historical. Fifteen consumer checkouts in this fleet carry
a `.devgate` submodule. Twelve of them ship a pinned copy of this allowlist and
**ten** of those hold 1,725-1,737 entries (`openagenticbench` and
`R.A.D.1.C.A.1` pin an empty copy; `dead-air`, `GlitchDungeon` and
`mission-control-rs` have no allowlist at their pin at all). `rad-gateway`'s
pinned copy holds **1,737** - its own markers, maintained inside DevGate's
baseline, which is how a shared baseline becomes a fork of one project's
allowlist.

## What changed

1. **The data.** `.guardrails/silent-success-allowlist.json` is empty again
   (12,097 lines deleted), with a note that states the rule, the overlay
   contract and the three-commit history instead of contradicting itself. The
   false `pruned_at` / `note_pruned` fields are gone rather than reworded.
2. **The overlay the note had promised but the scanner never implemented.** The
   note already said a consumer's entries belong in
   `<project>/.guardrails/silent-success-allowlist.json`; the scanner read no
   such file and its header said the allowlist "is NOT overlaid ... stays
   submodule-only by design". Emptying the baseline without this would strand
   every consumer that relies on those entries. `scripts/silent-success-scan.sh`
   now merges the project overlay's `entries` into the baseline's - **additive**,
   never id-keyed: coverage is a `(file, marker)` set, so an overlay can widen
   coverage but can never delete a baseline requirement. No overlay -> baseline
   only (byte-identical behaviour for consumers that have not adopted one); a
   malformed overlay fails closed, like the rules overlay next to it.
3. **The gate.** `scripts/baseline_ownership_check.py` (new, wired into CI's
   gates job) fails a bundled allowlist entry whose `file` does not exist in the
   tree that ships the file, or whose `family` the bundled rules do not declare,
   and fails closed when either bundled file is missing or malformed.

## Evidence, same input, old tree vs new

`git archive 41d21b5` into a scratch tree, then the new gate against it:

```
HEAD tree (the 1,727 entries):  exit 1
  ... entry #0 names 'go/cmd/game/battle_test.go', which does not exist in this tree (base-own-01)
  ... entry #1 names 'go/cmd/game/exit_flag_test.go', ... (base-own-01)
  ... entry #2 names 'go/cmd/game/main_test.go', ... (base-own-01)
  ... and 1702 more finding(s) (1727 total)
  baseline-ownership-check: FAIL - 1727 finding(s)

this tree (entries: []):        exit 0
  baseline-ownership-check: OK - bundled allowlist entries under <repo> are this repository's
```

`bash scripts/silent-success-scan.sh` after the change: exit 0,
`0 allowlisted, ... 0 allowlist entr(ies)` - the same verdict the 1,727 inert
entries produced, which is the point: they suppressed nothing here.

## Tests

- `tests/test_baseline_ownership_check.py` - **14 tests**. Live path clean and
  empty allowlist clean (positive controls), foreign path -> error, one foreign
  entry among live ones still fails, undeclared family -> error, absolute path ->
  error, entry without `file` -> error, missing / malformed / non-list-entries
  allowlist -> fail closed, missing rules file -> fail closed, `--max-report`
  truncates and counts, and two assertions about this repository itself (the
  gate passes on it, and the bundled `entries` list is empty by contract).
- `tests/test_silent_success_overlay.py` - **4 more** (7 -> 11): the project
  overlay covers a consumer marker and the merge line names both sides; a
  different marker in the same file is NOT covered (control); bundled entries
  still cover when an overlay is present (additive, not replacing); a malformed
  allowlist overlay fails closed.

## Verification

- Full local battery, every command from `ci.yml`, captured exit codes: pytest
  suite, fleet-manager contracts, extraction rehearsal, node fixtures,
  `run-tests.mjs`, semantic scan, guardrails-scan, silent-success,
  `failure_registry_check`, `baseline_ownership_check`, `rules_check`,
  `check_exec_bits`, `check_charset`, `check_encoding`, `check_corruption`
  (content and pushed range), `gen_floors`, `check_manifest_join`,
  `artifact_hygiene`, `regression_check` over the pushed range, `secret-scan`
  over the pushed range.
- `tests/expected-counts.json` regenerated with `gen_floors.py --update` for the
  new suite (the `test-suite-floor` join fails on a suite with no row).

## Not done here, and said rather than implied

- **The 1,727 entries were not migrated anywhere.** They are preserved in git
  (`git show 16ce30e:.guardrails/silent-success-allowlist.json`); shipping them
  in a migration file inside this repository would be the same foreign data in a
  different file. Each consumer that relies on them copies its own entries into
  its own overlay - the 2026-09-13 design (`D1`) already said exactly that.
- **Consumers were not touched.** Twelve checkouts carry a copy and ten of those
  have entries in it; nothing changes
  for them until they bump the pin, and then the overlay is where their entries
  go. `dead-air` is the only local checkout with an overlay rules file (2
  families enabled) and it carries no bundled allowlist copy at its pin, so its
  state is its own to settle.
- **Prevention rules and openspec specs are not covered by the new gate.**
  Prevention rules carry globs (`*.go`, `Dockerfile`), not repository paths, so
  there is no path-existence predicate to settle; openspec specs are prose. Both
  are named in the gate's docstring as out of its mechanical reach rather than
  left looking covered - `spec_traceability.py` covers requirement ids and
  `base-specs-01` covers the game-merge pointer rule.
