# art-creation-contract — Design

## Context

The fleet's game titles generate art through a generation pipeline
(concept → raw mesh → prepared mesh → baked albedo → packed game mesh →
renderer). The pipeline exists and is measured. What does not exist is any
statement of what its output is **for**, or any check that the output reached
the player.

One title was used as the observation base and exhibits every failure class
listed in the proposal. The detail behind those classes is operational and
lives outside this repository; the classes themselves are what this contract
generalises from, and they are stated in `proposal.md` for that reason.

The nearest existing contracts are `doc-truth` (a published claim must be
derivable), `evidence-and-attestation` (results are reproducible from a sealed
bundle), `publish-safety` (unknown state blocks publication) and
`gate-execution-contract` (a gate that evaluated nothing is not a pass). This
contract is the art-domain instance of those same instincts. Where they already
cover a case, this contract cites rather than restates.

## Decisions taken

### Q1 — One capability, not eight

The eight contracts in the originating standard are one coherent question —
*when is art done* — asked at eight points. Splitting them into eight
capabilities would produce eight packages each too thin to gate on, and would
scatter the single definition of done that all eight exist to protect.

Decision: one capability `art-creation-contract`, twelve requirements, with
`art-done-01` stating the definition and the rest protecting it.

### Q2 — The fidelity verdict stays human

Requirement `art-accept-01` deliberately names a *human* verdict. This is not a
gap waiting for automation. The observed failure class is precisely an
automated score answering a different question from the one that mattered: a
retention measure of `1.000` reported on an asset whose source silhouette was
the wrong shape.

Automation measures whether the pipeline preserved what it was given. Only a
reader can say whether what it was given was right. So the contract requires
the verdict and forbids substituting a score for it, while
`art-accept-02` requires the measurement to be recorded beside the verdict and
forbids deriving pass/fail from a measure that declares no threshold.

### Q3 — The brief is schema, not content

A title's pillars, palette and shape rules are content and live in the title's
repository. What is general is the *fields the brief must contain*, the rule
that generation without one is refused, and the rule that a concept is checked
against a named class rule.

Decision: `art-brief-01` fixes the required fields. It does not fix any value.

This is what makes the contract reusable. A horror title and a racing title
need different shape languages and the same brief.

### Q4 — Ledger is the inventory; counts are derived

The observed drift was a published count and an on-disk reality diverging
quietly. A count typed by hand cannot be checked against anything.

Decision: the ledger is the inventory (`art-ledger-01`), counts are derived
from it, and a published count that cannot be derived is a `doc-truth` failure
rather than a new rule here. The ledger row schema is fixed at the fields listed
in the requirement; titles may add fields, not remove them.

### Q5 — "Every target draws" is checked against the title's own renderer

The most expensive observed class was a shipped platform whose render loop
clears a colour buffer and submits no draw calls, with every gate green.

The check cannot be "does a window open" and cannot be "does a preview image
exist" — both were true while the platform drew nothing. It must be a frame
captured **from the title's own renderer on that target**, asserted to contain
game geometry.

Content-creation tool previews are excluded by name in `art-draw-01`, because
a DCC preview of an asset tells you nothing about whether the shipped target
can draw it. The originating title's own documentation records DCC preview
rendering as unreliable for exactly this.

### Q6 — The contract is allowed to grow

A standard written after a failure is the failure recurring at a higher level
of abstraction. `art-evolve-01` ties the contract to the failure registry the
fleet already maintains: a new class is logged with a prevention rule, and if no
existing requirement covers it the contract extends.

This is the mechanism that keeps the contract from becoming the next artifact
written in hindsight.

## Architecture

### Inputs

Three files in the title's repository:

| file | role |
|---|---|
| art brief (any path, declared) | C1 fields, versioned |
| pipeline document (any path, declared) | stages with named consumers |
| provenance ledger (any path, declared) | one row per asset |

The scanner is told the three paths. It does not guess them.

### Checks and their requirement

| check | requirement | evidence |
|---|---|---|
| brief present and referenced | `art-brief-01` | ledger `brief_ref` |
| shape rule named per class | `art-brief-02` | brief contents |
| stage has a consumer | `art-stage-01` | pipeline document + tree |
| consumer path exists | `art-stage-01` | title tree |
| no artifact outside the ledger | `art-ledger-01` | directory walk |
| counts derivable | `art-ledger-01` | ledger vs published |
| replication + exercised restore | `art-bytes-01` | ledger + restore record |
| fidelity verdict present | `art-accept-01` | ledger row |
| measurement labelled, not gated | `art-accept-02` | ledger row |
| per-target frame capture | `art-draw-01` | capture manifest |
| rights explicitly recorded | `art-rights-01` | ledger row |
| quantity gate suppressed while fidelity red | `art-qty-01` | derived |

### Out of scope

- **Where the bytes live.** The contract requires versioning, replication and
  a tested restore. It does not prescribe a repository, an object store or a
  content-addressed scheme. That is an operator decision per fleet.
- **How art is generated.** The generation tool, model and host are outside.
- **Art direction values.** See Q3.
- **Renderer implementation.** The contract requires that a target draws; it
  does not say how.

## Honest limits

- **The fidelity gate is not automatable and is not meant to be.** The scanner
  can check that a verdict exists and names a class rule. It cannot check the
  verdict is *correct*. That residual is stated, not hidden.
- **"Contains game geometry" is a weak assertion.** The practical check is
  non-uniformity of the captured frame plus a declared expected region, not
  scene understanding. A target that draws a flat clear colour fails; a target
  that draws the wrong geometry may pass. Strengthening this is expected to be
  iterative.
- **No fleet-wide adoption is implied by landing this contract.** Titles opt in
  by declaring their three paths. Until a title declares them, the scanner
  reports `NOT_APPLICABLE`, never green.
- **The originating title is a fixture, not a model.** It is useful because it
  is currently failing every class. It is not an exemplar of how to pass.

## Data shape

### Ledger row (minimum fields)

```json
{
  "id": "prop_example",
  "class": "furniture",
  "stage": "packed",
  "brief_ref": "art-brief@3",
  "prompt": "…",
  "seed": 41025,
  "digests": {
    "concept": "sha256:…",
    "raw": "sha256:…",
    "prepared": "sha256:…",
    "albedo": "sha256:…",
    "packed": "sha256:…"
  },
  "prep_stages": { "normal_repair": true, "voxel_remesh": true, "texture_bake": true },
  "fidelity": { "verdict": "accept", "rule": "furniture:orthogonal", "reviewer": "human" },
  "measurement": { "name": "silhouette_retained", "value": 0.97, "threshold": null },
  "rights": "unknown",
  "placement": null
}
```

`stage` is an enum drawn from the pipeline document's declared stages.
`measurement.threshold` is null exactly when the measure declares no pass
point, and a null threshold means the value cannot gate.

### Capture manifest

```json
{
  "target": "web",
  "frame_sha256": "sha256:…",
  "renderer": "title-own",
  "contains_game_geometry": true,
  "captured_at": "2026-11-08T00:00:00Z"
}
```

`renderer: "dcc-preview"` is rejected by `art-draw-01` and the scanner refuses
the row.

## Risks

| risk | mitigation |
|---|---|
| the fidelity gate becomes a rubber stamp | the contract forbids substituting a score; the scanner checks the verdict *names a rule*, which is hard to fake without reading the brief |
| the ledger becomes a second source of truth against the files | rows carry digests (`art-ledger-01` requires them) so a reader can bind a row to an artifact; the scanner checks digest *presence*, and comparing each digest against the artifact bytes is the stated follow-on, not implemented here |
| titles declare the paths and then never fill them | the scanner reports `NOT_APPLICABLE` until declared and fails on declaration-with-no-rows |
| "contains game geometry" stays weak | stated in Honest limits; expected to tighten as captures accumulate |
| the contract ossifies | `art-evolve-01` and the failure registry |
