# Proposal: add-fleet-manager-boundary

> Program package: `devgate-product-tiers-fleet-manager`, Sprint 1 box 1.1.
> Owner decisions OD-001 and OD-002 were taken 2026-09-29 and are recorded in
> `devgate-open-changes/devgate-product-tiers-fleet-manager/tasks.md`.

## Why

The repository is one tree today: `hub/`, `scripts/`, `lib/`, `engines/`,
`templates/`, `tests/`. A product-tiers line of work (fleet manager, evidence
plane) is planned, and the failure this guards against is not "someone writes
commercial code" — it is that commercial code arrives scattered across the open
root, with the open core importing it, so that the boundary can only be
discovered later by untangling imports.

`docs/qa/2026-09-29-product-tiers-fleet-manager-baseline.md` measured the
starting point: no `enterprise/` or `fleet-manager/` directory exists, and the
package boundary is the public tree only.

OD-001 descoped the commercial license grant for Phase 1: BSD 3-Clause
everywhere, no second LICENSE. What remains to enforce is the **package
boundary** — where the code lives, which way dependencies point, and that a new
path under the boundary is a reviewed declaration rather than an accident.

## What changes

- A top-level `fleet-manager/` root exists and is the only home for
  product-tiers code.
- `fleet-manager/manifest.json` is the machine-readable declaration of the
  boundary: the declared paths, the license, and the roots that must never
  hold product-tiers code.
- `fleet-manager/README.md` carries the license notice and the dependency
  rules in prose, because a manifest is not a review comment.
- `scripts/check_boundary.py` is the gate: it checks the manifest against the
  tree, checks that no open-core file imports the boundary, and reds on a
  changed path that puts product-tiers code outside the root.
- CI runs it as a required step in the `specs` job.

## What this deliberately does not do

- No commercial license text, no entitlement check, no second repository. OD-001
  and REPO-005's "evidence, not authorization" both defer those.
- No `contracts/v1/` content yet. The manifest declares the path pattern; the
  versioned contracts and their bidirectional tests are box 1.2.
- No extraction rehearsal. That is box 1.3 and needs the contracts to exist
  first.
