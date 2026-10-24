# `fleet-manager/` — the product-tiers boundary

This directory is the package boundary for product-tiers work (the Fleet
Manager). It exists so the boundary is a **declaration** — a reviewed list of
paths with a gate behind it — rather than a directory that grew.

Program package: `devgate-product-tiers-fleet-manager` (Sprint 1 box 1.1).
Design decision record: `openspec/changes/add-fleet-manager-boundary/design.md`.

## License

BSD 3-Clause, under the repository's root [`LICENSE`](../LICENSE). There is
**no separate grant for this directory** — owner decision OD-001 (2026-09-29)
descoped the commercial license split for Phase 1, so a second license text
here would be a claim the project has not made. A future commercial split can
reuse this root; it is not part of Phase 1.

## Dependency rules

One direction only:

- code under `fleet-manager/` **may** import open-core code;
- open-core code **must not** import, require, or load anything from
  `fleet-manager/`.

The second rule is what keeps the open core buildable without the boundary. A
cross-boundary call must go through a versioned contract (box 1.2,
`contracts/v1/`), never an import of an internal class, database model, or
non-versioned schema.

## Adding a path

A new directory or file here is a **reviewed commit to `manifest.json`**, not
an untracked directory. `scripts/check_boundary.py` fails a file under this
root that no declared pattern matches — that failure is the point.

```
python3 scripts/check_boundary.py --repo .                 # full check
python3 scripts/check_boundary.py --repo . --changed-base origin/main
```

Exit codes: `0` clean, `1` violation (named), `2` manifest unreadable or
unusable. Exit 2 is not a pass: a gate that cannot read its declaration never
reports a clean boundary.

## What is not here yet

- `contracts/v1/` — declared as a pattern, empty until box 1.2.
- Extracted build — box 1.3 rehearses extraction in CI; this root is evidence
  for that rehearsal, not authorization to create a second repository.
