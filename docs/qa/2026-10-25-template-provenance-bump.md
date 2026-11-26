# Template provenance - second reviewed round-trip: pin 1.13.0 to 1.14.3

Date: 2026-10-25 (UTC). Package: `spec-audit-rollout`, task 3.4 (SGA-21
scenario 3). Predecessor: `docs/qa/2026-10-22-template-provenance.md`.

## The alert, and why the first review declined

The 2026-10-24 sweep reported upstream drift on all four locked templates.
The first review (AIGGP issue #34) verified the drift and **declined the
bump on evidence**: 1.14.x promotes the requirement-text-over-500-characters
advisory to a `--strict` failure, so bumping the pin alone would have
reddened the specs gate in two trees.

Measured 2026-10-24 with the real CLI, `@fission-ai/openspec@1.14.3`
installed in a scratch prefix and `validate --all --strict`:

| Tree | Before | Cause |
|---|---|---|
| AIGGP | 31 passed, 13 failed (44 items) | 40 requirement texts over 500 chars |
| Mission Control (root) | 27 passed, 3 failed (30 items) | 4 requirement texts over 500 chars |

The re-open condition recorded in the tracker was the corpus change: compress
the over-long requirement bodies. That change landed first, in two repos:

- AIGGP `81879e1` + `ad31ce0`: 40 bodies compressed, 44/44 strict under both
  1.13.0 and 1.14.3, 0 requirement blocks over 500.
- Mission Control `7c3985b`: 4 bodies compressed (two of them MODIFIED deltas,
  compressed to match their main-spec counterparts so archiving the change
  cannot reintroduce the warning), 30/30 strict under both versions.

No requirement was renamed, split, or merged. Each body keeps its normative
SHALL/MUST statements and its elaboration moved verbatim into a named
scenario, which is the remedy the rule itself names. Requirement IDs are
unchanged, so AIGGP traceability stayed at 133/176 and the ratchet floor of
133 still holds (`--ratchet` exit 0).

## Verified locally before pinning

The `1.13.0 -> 1.14.3` template diff, reviewed line by line, is editorial:
three templates gain an `H1` title and `proposal.md` gains one expanded
comment about capability naming. No structural or rule-bearing change.

```
$ for f in design proposal spec tasks; do
    curl -sSL https://raw.githubusercontent.com/Fission-AI/OpenSpec/v1.14.3/schemas/spec-driven/templates/$f.md | sha256sum
  done
design    6ccc87f5017fb190e69e8759dd4e20d5ac3320cc4dabf152708bf8f2aa5205f8
proposal  0dd70e35db5c696ba8ac3cc3a53e2d6561865c1e4e7d49db5a1eaa3e4a6ad86e
spec      1cccfb573f031c6352bed2a879b7035ff710bc909112fc23d10bdcfcdd8d4318
tasks     fa67d99fb4a93b12d702f89ea83e1838219d1cad1c90a4192c402278001cd30e
```

Those four hashes are byte-identical to the files inside the installed
`@fission-ai/openspec@1.14.3` package, so the tag and the package agree -
the same two-way check the 1.13.0 lock was written under.

## The bump, and what it moved

One reviewed commit changes the pin in every place it is written:

- `templates/github-workflows/specs.yml` - `OPENSPEC_PACKAGE` (the copy
  consumers adopt);
- `.github/workflows/spec-fleet.yml` - `OPENSPEC_PACKAGE` (the staging copy);
- `.github/workflows/ci.yml` - the `npm install` line for the specs job;
- `spec-templates.lock.json` - `pinned_sha256`, `pin_source` (now the
  v1.14.3 tag URL), and `upstream_version` for all four entries;
- `README.md` - the documented install line.

The lock is not rewritten by anything automated: this commit is the only
writer (SGA-21 scenario 3).

## Re-measured after the bump

```
$ python3 scripts/spec-fleet-classify.py --root . --lock-file spec-templates.lock.json --lock-check-only --json
fault False   drift []   unknown []   unlocked []
  (all four: status not-vendored, pin_source_hash == pinned_sha256)

$ npx openspec validate --all --strict          # @fission-ai/openspec@1.14.3
Totals: 44 passed, 0 failed (44 items)

$ bash scripts/specs-validate-negative-control.sh
negative control passed: strict validation refused the malformed fixture,
naming its designed defect (missing ## Purpose), exit 1.

$ python3 scripts/spec_traceability.py --root . --ratchet
spec-traceability: 133/176 requirements covered (exit 0)

$ python3 scripts/spec-fleet-classify.py --root . --tier-file ... --repo-name TheArchitectit/AIGGP-Agentic-Framework --json
state "spaced", strict_state "ok", gaps 0, red false
```

The pin and its negative control are a pair, so the control was re-run
**against the new pin** rather than against the old one: a validator that
had been downgraded to a no-op would show green on the tree and still fail
to refuse the malformed fixture, and the control is what tells the two
apart.

## Stated boundary: Mission Control's second root

Mission Control validates two OpenSpec roots. The root tree is green at
1.14.3 (`30/30`). The Rust crate root (`mission-control-rs`, 34 items, 133
requirement blocks) still carries 22 requirement texts over 500 chars and
therefore fails `--strict` under 1.14.3 while passing under 1.13.0. It is
**not** covered by this template pin - Mission Control pins its CLI through
its own `package.json` (`^1.13.1`) and carries no copy of
`templates/github-workflows/specs.yml` - and it was not part of the
44-requirement corpus this round measured. Compressing that root is a
precondition for Mission Control's own pin move, recorded here rather than
folded in silently.

## Issue state

AIGGP issue #34 was closed on 2026-10-24 as reviewed-and-deferred. Its
re-open condition - the requirement-text corpus change - is now met, and
this commit is the adoption it asked for; the deferral note stands as the
record of why the bump did not happen a day earlier.
