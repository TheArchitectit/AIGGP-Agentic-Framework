# Design: Fleet Manager extraction rehearsal

## Context

A boundary that only holds while the whole repository is checked out is a
convention. REPO-005 asks for evidence, and the only credible evidence is a
build of the package with the rest of the repository absent.

## Decisions

### Two phases, because the property is symmetric

Extraction readiness is not one claim. The package must stand alone (phase A),
*and* the core must stand without the package (phase B). A rehearsal that only
copied the package would pass a package that the core secretly depends on — the
failure REPO-002-03 forbids and REPO-005 exists to detect. Phase B is also what
"core gates proven green with commercial code absent" means in practice.

### Phase A copies exactly the declared build inputs, then asserts nothing else

The workspace check is the load-bearing part: after copying, every file outside
`fleet-manager/` must be in `DECLARED_BUILD_INPUTS`. Without it, "it compiled
here" would be satisfied by any stray module that happened to be nearby. The
list is also pinned against the contract suite's import-surface test, so the
two statements of the dependency cannot drift.

### Phase B collects rather than runs the full suite

Running 1741 tests twice per push buys little over collecting them once: the
question is whether any core module, test module, or fixture *reaches* for the
boundary at import/collection time, and collection answers that in seconds. The
pattern scan runs for real because it is cheap and it walks every file.

The step states when `node` is absent and skips the scan half loudly, rather
than reporting a pass it did not earn.

### The gate needed one refinement: declared invocation sites

`check_boundary.py` scans `.yml`, so CI running `pytest fleet-manager/tests`
read as "open-core code references the boundary". That rule is right for
modules and wrong for the one file whose job is to *start* the boundary's
tests. Rather than exempting the workflow wholesale or teaching the scanner to
guess intent, the manifest gained `invocation_paths`: an explicit, reviewed
list of files that may name the boundary, pinned by a test, separate from
`exempt_paths` so the reason for each skip is written down.

The hole is real and bounded: an invocation site could smuggle an import. It is
mitigated by the file being a YAML workflow (it cannot import anything) and by
the pin making any widening a reviewed diff.

### The marker-format bug found on the way

`check_boundary.py` declared its coverage as
`# spec: repo-002-01 repo-002-02 repo-002-03 repo-002-04`. The discovery
parses comma-separated IDs, so only the first registered and three requirements
read UNCOVERED — including the one this change's own gate work belongs to.
Fixed to the comma form. It is recorded because a coverage number that is
quietly one-quarter of what it looks like is exactly the kind of green this
program is supposed to distrust.

## Risks

- **A 10-second rehearsal.** The copy is ~22 MB and the run is dominated by
  pytest import time in the extracted workspace. Acceptable per push; if it
  grows, `--source` already allows pointing it at a reduced tree.
- **Phase B's guarantee is collection, not execution.** Stated in the QA record
  so nobody upgrades the claim later.
