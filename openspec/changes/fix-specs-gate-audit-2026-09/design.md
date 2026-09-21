# Design: fix-specs-gate-audit-2026-09

## The shape the audit found

The tree claimed a hard spec gate and a self-test lane. Neither was doing what
its name said. Both failures are instances of one pattern — a check whose
success signal is independent of whether it did any work:

- `openspec validate --all --strict` **was** doing work, and failing 26/31, so
  the specs CI job was red. Correct behavior for a gate; the defect was 26 items
  of drifted spec text.
- `run-tests.mjs` **was not** doing work. It discovered zero test files and
  exited 0. That is the more dangerous failure: it is indistinguishable from a
  clean run, and it reports the same thing whether the repository has no tests,
  has tests the runner cannot find, or scanned the wrong tree entirely.

The audit's mutation battery makes the distinction concrete. Every root-
resolution mutation it tried left the lane green (0/10 killed), because a
zero-discovery exit-0 is insensitive to *which* tree it found nothing in. The
fixture's assertions could not distinguish "found the right tests" from "found
nothing" from "scanned a sibling directory" — the exit code was 0 in all three.

## Why the fix is two contracts, not one

Fixing only the root resolution (layout instead of walk-up) leaves the lane
sensitive to a *different* spelling of the same escape: an inverted-precedence
mutant ("try my own tree first, then fall back to an ancestor") passes every
layout assertion whenever the wrong tree happens to contain more tests. Fixing
only the zero-discovery check leaves the scanner evaluating the wrong tree while
happily reporting "600 passed" from files it does not own.

So the change pins both:

1. **Root by layout** (`root-anchor-01`) — `basename(devgateRoot) === ".devgate"
   ? dirname(devgateRoot) : devgateRoot`. This is not new logic; the correct
   contract already existed in `guardrails-scan.mjs` with a comment naming the
   exact escape. The change moves it into one shared module
   (`scripts/lib/project-root.mjs`) that all three scanners import, because the
   defect was not that the contract was unknown — it was that two other scanners
   never learned it. Copies drift; an import cannot.
2. **Non-vacuity** (`root-anchor-02`) — zero discovery is a failure with a
   reason, with one explicit opt-out that prints a distinguishable skip line.
   This is the contract that *survives* a layout-only fix, because it constrains
   the outcome rather than the mechanism.

The fixture (`tests/test_scanner_root_anchor.mjs`) exercises both, plus the
submodule positive control so a fix cannot over-correct to "always DevGate" and
strand real consumers.

## Mutation evidence

Each guard is pinned by a mutation that a specific check kills:

| Mutation | Killed by |
|---|---|
| Original ancestor walk-up (pre-fix code) | 6 checks — count is 2 (decoys) not 3, zero-discovery exits 0, semantic-scan count is 5 not 3, both opt-out checks run the wrong tree |
| Ancestor fallback after own-tree miss (inverted precedence) | 4 checks — standalone count, standalone exit, submodule count, submodule exit |
| Inert zero-discovery guard (guard present, never fires) | zero-discovery check (exit 0 where nonzero required) + parent-not-scanned check |
| `DEVGATE_ALLOW_NO_TESTS` truthy-test instead of literal `"1"` | opt-out check — `=0` would skip, which the check forbids |

The fixture's parent deliberately **carries** a `package.json`. A markerless
parent would let an inverted-precedence mutant pass with identical assertions,
because the walk-up would have nothing to stop at and both mechanisms would
agree. Reproducing the historical precondition is what makes the mutant
killable.

## Why the format contract is a spec and not just a commit

The 15 base specs failed on a *shape* rule (`## Purpose` required) that was
nowhere written down. `ci.yml:100` has cited `spec-fmt-01` in a comment since
the migrate-specs change, but no such requirement existed in the spec tree — the
comment described a contract that was never authored. That is the same
documented-vs-shipped gap the audit flags elsewhere, one level up: the CI
comment claimed a requirement the repository did not contain.

`openspec-format-conformance` writes it down for real, including the parts that
cost the most time to rediscover: umbrella insertion is not sufficient without
demotion (a level-2 requirement is a sibling, not a child); the strict-mode verb
check is uppercase-only, so a lowercase `shall` reads as an absent requirement;
and imported drafts must carry no IDs, because an ID makes the traceability gate
count unimplemented work as a tracked obligation.

## The negative control

A green strict run proves the tree is currently well-formed. It does not prove
the validator would refuse a malformed tree — if `--strict` were silently
downgraded to a no-op upstream, or the CLI resolved to something that always
succeeds, the job would keep passing. The `spec-fmt-04` control feeds a
synthetic malformed spec to the same command and requires rejection, so the
gate's ability to fail is itself tested.

Related and cheap: pin the `openspec` CLI version. The job currently runs
`npx openspec` with no version, so the validator's behavior can change without
any commit in this repository — a gate whose rules float is a gate whose green
means different things on different days.

## What this package deliberately does not do

- **No `skip_specs`.** Excluding the AIGGP packages from validation would have
  made the count green while leaving 29 files that the declared grammar does not
  accept. The tree is fixed, not the gate.
- **No requirement IDs on imported drafts.** Coverage pressure is not coverage.
- **No `## MODIFIED` deltas in AIGGP-02.** The `coh-*` requirements it overlaps
  exist only as deltas in an unarchived package, so a MODIFIED could not
  name-match them. Dispositioned in `reconciliation.md` instead.
- **No claim about the container path.** The audit's third finding — the
  containerized coherence path not yet rebuilt and re-pinned — stays open. This
  branch does not pretend otherwise; it is a merge-gate item on the
  coherence-service package, not a spec-format defect.
- **No fixing of the Python scanners' root resolution.** `regression_check.py`
  and `scene_inventory.py` carry the same walk-up defect this package fixed for
  the three Node scanners. It was found by this package's own fresh-eyes audit,
  not by the external audit, and it is recorded as an OPEN ledger item rather
  than quietly absorbed into a slice named for something else.

## Which `spec-fmt-*` IDs are marked, and why the others are not

Only `spec-fmt-04` carries a source marker. That is deliberate and not a gap
waiting to be filled:

- **`spec-fmt-01/02/03`** describe properties of the spec *tree* — Purpose and
  umbrella sections present, requirements demoted, delta grammar respected,
  imported drafts carrying no IDs. Their enforcing mechanism is
  `openspec validate --all --strict` itself, which is not a file in the
  repository and cannot host a `// spec:` comment. A marker added for them would
  have to point at some unrelated source line purely to move a coverage number,
  which is manufactured coverage — the exact thing `spec-fmt-03` forbids.
  They are honestly advisory-uncovered.
- **`spec-fmt-04`** is different: it names a check that *is* a file
  (`scripts/specs-validate-negative-control.sh`), so a real marker belongs there.

Discovering that the marker was invisible — `spec_traceability.py`'s
`SCAN_EXTS` did not include `.sh`, so the requirement read UNCOVERED while the
source looked marked — is recorded in the ledger. The fix widened `SCAN_EXTS`
and is pinned by `test_shell_script_marker_counts_as_coverage`.
