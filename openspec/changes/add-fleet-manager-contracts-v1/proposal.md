# Change: Fleet Manager versioned contracts v1

## Why

`add-fleet-manager-boundary` made `fleet-manager/` a real boundary and made CI
refuse open-core imports of it. It did not answer the next question: if the two
sides cannot see each other's code, what *do* they exchange?

Right now the answer is "nothing yet", which means the first thing written
across that boundary would define it by accident — a dict here, a JSON blob
there, a field added without a version, a consumer reading whatever happened to
be present. REPO-003/REPO-004 exist to prevent exactly that, and box 1.2 of
`devgate-product-tiers-fleet-manager` is where they land.

## What changes

Three documents, one directory, one version, tested in both directions:

| schema | direction |
| --- | --- |
| `capacity-request` | core → Fleet Manager |
| `capacity-decision` | Fleet Manager → core |
| `operation-receipt` | Fleet Manager → evidence plane |

- `fleet-manager/contracts/v1/` holds the three closed JSON Schemas, the
  versioning policy, and the two fixtures that stand in for the other side.
- `fleet-manager/fleet_manager/contracts.py` is the Fleet Manager's side: it
  validates, refuses wrong versions, refuses malformed documents with named
  paths, and **refuses to produce an invalid document** (the builders validate
  what they built).
- `fleet-manager/tests/test_contracts_v1.py` runs both directions from the
  package alone, plus the version dispatch, the entitlement-isolation check and
  the pinned core-import surface.
- CI runs that suite as its own step, so the extraction rehearsal (1.3) can run
  the same command in an isolated workspace.

## What this deliberately does not do

- **No real core producer yet.** Core emitting a `capacity-request` is Sprint 2
  (plan/apply) and Sprint 4 (adapters) work. The core side of the test is a
  fixture that says, in machine-readable form, what core will require.
- **No previous-version leg.** v1 is the first version; there is no previous
  one to run the current implementation against. The test says so where the gap
  is, and the leg re-opens when `contracts/v2/` exists.
- **No entitlement lifecycle tests.** OD-001 dropped the commercial split for
  Phase 1, so there is no entitlement to be absent, expired, malformed or
  revoked. What Phase 1 can prove is structural: the v1 schemas are closed and
  declare no tier/entitlement field, so a paid-tier flag cannot be expressed at
  all. That is tested.
- **No extraction rehearsal.** That is box 1.3.

## Impact

- New: `fleet-manager/contracts/v1/**`, `fleet-manager/fleet_manager/**`,
  `fleet-manager/tests/**`, this change package.
- Changed: `fleet-manager/manifest.json` (+`fleet-manager/fleet_manager/**` —
  the boundary gate refused the new package until it was declared, which is the
  gate working), `.github/workflows/ci.yml` (one test step).
- No open-core file gains a reference to the boundary; the boundary gate's
  dependency-direction half is unchanged and still green.
