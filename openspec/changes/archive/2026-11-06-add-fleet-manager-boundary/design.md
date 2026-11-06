# Design: add-fleet-manager-boundary

## Boundary layout

```
fleet-manager/              <- OD-002 root; the only home for product-tiers code
  README.md                 <- license notice + dependency rules (prose)
  manifest.json             <- machine-readable path declaration
  contracts/v1/             <- versioned cross-boundary contracts (box 1.2)
  tests/                    <- boundary-side tests
```

Nothing else is created by this change. The manifest's `paths` list is the
complete declaration; a file that appears under the root without a matching
pattern is a violation, which is the point — a new commercial path is a reviewed
commit to the manifest, not a directory someone added.

## The gate

`scripts/check_boundary.py`, exit 0 / 1 / 2 (clean / violation / malformed).

1. **Manifest validity.** Parse `fleet-manager/manifest.json`; every declared
   pattern must resolve inside the boundary root; the license must be
   `BSD-3-Clause` with `separate_grant: false` (OD-001). A manifest that is
   unreadable, not JSON, or names a path outside the root exits 2 — a gate that
   cannot read its declaration must never report a clean boundary.
2. **Coverage.** Every tracked file under `fleet-manager/` must match a
   declared pattern. Unmatched path → exit 1, naming it.
3. **Dependency direction.** Every source file outside the boundary is scanned
   for a reference to the boundary: `import fleet_manager`, `from
   fleet_manager…`, a string literal containing `fleet-manager/`, or
   `fleet_manager`. A hit outside an exempt path exits 1, naming file and line.
   The reverse direction (boundary importing core) is allowed and not checked.
4. **Scattered-code check.** With `--changed-base REF`, any changed path under
   a `forbidden_roots` entry (e.g. `enterprise/`, `commercial/`) exits 1:
   product-tiers code belongs under one root.

## Stated limits of the detector

- It is a static line scan, not an import resolver. A dynamically computed
  module name (`importlib.import_module(name)`) is not detected.
- It scans code files only (`.py`, `.sh`, `.rs`, `.js`, `.mjs`, `.ts`,
  `.tsx`, `.yml`, `.yaml`). Prose in `docs/` may name `fleet-manager/` freely;
  documentation is not a dependency edge.
- Comment lines (leading `#`) are skipped, so a commented-out import does not
  red. A gate that reds on prose gets muted.
- The exempt list is exactly the gate script and its test — the two files that
  must name the boundary to check it. A test pins that list to that set so it
  cannot quietly grow.

## Why the manifest lives inside the boundary

REPO-002 says the boundary contains "a machine-readable manifest of commercial
paths". Keeping it at `fleet-manager/manifest.json` means the declaration
travels with the thing it declares, and the extraction rehearsal in box 1.3
can copy the root without also having to remember a file elsewhere.
