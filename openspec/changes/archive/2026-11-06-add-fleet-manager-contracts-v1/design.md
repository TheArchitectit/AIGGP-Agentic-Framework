# Design: Fleet Manager versioned contracts v1

## Context

`fleet-manager/` is a one-way boundary (REPO-002, landed in
`add-fleet-manager-boundary`). Open core may not import it; the boundary may
import open core. Between the two, only documents cross.

## Goals

1. Every crossing document has a shape that lives in the repository, a version
   inside the document, and a test that fails when either drifts.
2. A consumer refuses rather than guesses — including on a version it does not
   implement.
3. A producer cannot emit a document its own contract rejects.
4. The set of open-core modules the boundary imports is small, declared, and
   pinned by a test, so extraction has a bounded dependency.

## Non-goals

The previous-version leg of REPO-004, the entitlement lifecycle matrix, and the
extraction rehearsal itself. Each is stated in the proposal with its reason.

## Decisions

### Three documents, not a general protocol

The boundary needs, in Phase 1: ask for capacity, answer about capacity, and
record what was done. Those are three documents. Inventing a general
envelope/RPC layer now would be a protocol with no second endpoint — the first
real consumer would redefine it anyway. When a fourth crossing appears, it is a
new schema in `v1/` **only if it is additive at the document level**; a change
to an existing shape is `v2/`.

### Closed schemas, therefore any shape change is a new major

`additionalProperties: false` on every object. That is what stops undeclared
fields crossing, and it has a consequence that is easy to miss: adding an
"optional" field would be rejected by every v1 consumer. So the versioning
policy cannot pretend minor versions are compatible — any shape change is
`contracts/v2/`. This is written in `contracts/v1/README.md` so nobody
rediscovers it in production.

### Version is in the document

No HTTP header, no path segment, no reader convention. `contract_version` is a
required property with `const: 1`, so a document that does not say what it is
fails validation, and a consumer holding the wrong schema cannot be handed a
document by accident.

`validate()` checks the version **first and alone**: a v2 document must be
refused as a version problem, not reported as a pile of shape errors from a v1
schema that was never meant to describe it. That distinction is tested
(`test_a_v2_document_is_refused_as_a_version_problem_only`).

### The schema states where its authority ends

The core's `hub/coherence/schemacheck.py` implements a JSON-Schema subset with
no `if/then`, and it is the validator that ships. So three rules live in
`fleet_manager/contracts.py` instead of the schema:

- `assignment` present iff `outcome == "assigned"`;
- `reason` present iff `outcome != "assigned"` (a decision without a reason
  cannot be acted on, and a grant plus an excuse in one document cannot be);
- `evidence` present when a receipt says `completed`.

This split is documented in the module docstring and the contracts README. A
schema that quietly under-checks is worse than one that says where it stops.

### Producers validate their own output

`build_capacity_decision` / `build_receipt` run `parse` on what they built and
raise `ContractInvalid`. The failure mode this removes is the common one: a
producer drifts from its schema and the consumer, written by someone else,
discovers it in a nightly.

`build_capacity_decision` also requires the *request document*, not a bare id:
the decision echoes a request that was itself validated, so a decision cannot
be built against a request nobody could have emitted.

### Refusals are typed and total

`ContractError` is a `ValueError`; `ContractUnsupportedVersion` and
`ContractInvalid` carry the numbers and the violation list. `validate()` never
raises on a hostile document — `None`, a string, a list and an int are all
refused with an error, not an exception from `doc.get`/`doc[...]`. That is what
lets the core side degrade explicitly ("unavailable") instead of answering a
crash with a crash.

### Entitlement isolation, in the only form Phase 1 has

OD-001 dropped the commercial split. There is no entitlement document, no
expiry, no revocation. What remains provable is structural: the v1 schemas are
closed and declare no `tier` / `entitlement` / `license` / `paid` field, so a
decision cannot depend on one. A test walks every v1 schema and fails if such a
field appears; another asserts `additionalProperties: false` everywhere.

## Risks

- **A closed schema is a commitment.** A field missed now costs a `v2/`
  directory. Accepted: the alternative is a permissive schema that silently
  grows, which is the failure REPO-003 exists to prevent.
- **The consumer here has no counterpart yet.** The core-side fixture is only as
  good as its author's reading of Sprint 2/4. Mitigation: it is data, it is
  small, and changing it is a reviewed diff — unlike a hidden assumption in
  prose.
- **One core import.** `hub.coherence.schemacheck` is a real dependency of the
  boundary package. Pinned by test; if the package is ever extracted, that
  module travels with the release as a published build input (REPO-005).
