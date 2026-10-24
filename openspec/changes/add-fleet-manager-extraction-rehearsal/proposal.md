# Change: Fleet Manager extraction rehearsal

## Why

`add-fleet-manager-boundary` made `fleet-manager/` a declared boundary and
`add-fleet-manager-contracts-v1` made the crossing documents versioned. Neither
proves the package would survive leaving the repository. Today it says "no
hidden imports" in prose; a package that only builds because the whole tree is
sitting next to it is a promise, not a boundary.

REPO-005 asks for the rehearsal: copy the package somewhere isolated and prove
it works from declared inputs only — and, symmetrically, prove the open core
does not need it.

## What changes

`fleet-manager/scripts/extraction_rehearsal.py`, run in CI:

- **Phase A.** Copies `fleet-manager/` into an empty workspace, copies in only
  the declared build inputs (`hub/coherence/schemacheck.py` and the two package
  `__init__`s), asserts nothing else from open core is present, and runs the
  package's own test suite there.
- **Phase B.** Copies the repository *without* `fleet-manager/`, then collects
  the entire core test suite and runs the pattern scan. Nothing in the core may
  need the boundary to exist.

The real checkout is never modified; both workspaces are temporary.

One rule had to be refined to make this possible: the boundary gate treated any
mention of `fleet-manager/` outside the boundary as a violation, including CI
running the boundary's own tests. The manifest now declares
`invocation_paths` — files allowed to *name* the boundary because they start its
tests, never to import from it — and the list is pinned by a test, so widening
it is a reviewed diff rather than a silent hole.

## What this does not do

- It does not create a second repository. The rehearsal is evidence that
  extraction is possible, not authorization to perform it.
- It does not build a release artifact. "Published build inputs" today are the
  three declared files; when the package needs more, the list grows by reviewed
  diff and the rehearsal starts enforcing it.

## Impact

- New: `fleet-manager/scripts/extraction_rehearsal.py`, this change package.
- Changed: `fleet-manager/manifest.json` (`scripts/**` declared,
  `invocation_paths` added), `scripts/check_boundary.py` (invocation allowance),
  `tests/test_check_boundary.py` (two new planted cases + the pin), CI (one
  step).
- Traceability: three requirement IDs move from uncovered to covered, and
  `repo-002-02/03/04` — which were silently uncovered because
  `check_boundary.py`'s marker was space-separated and the parser is
  comma-separated — become covered.
