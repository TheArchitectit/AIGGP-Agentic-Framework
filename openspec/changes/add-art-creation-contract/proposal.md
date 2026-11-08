# Proposal: art-creation-contract

## Why

Games in the fleet generate art, and nothing in the system defines what
"generated art" is *for* or when it is finished. The result is not a shortage
of assets. It is assets that cannot be trusted: a set with no shared language,
bytes with one unversioned copy, a documented pipeline artifact nothing reads,
and — most expensive — shipped targets that draw nothing while every gate
reports green.

Eight failure classes observed on one title, stated as classes because this
repository is public and the operational detail lives elsewhere:

1. **No shared language.** Four props, four prompts, four incompatible
   silhouettes — a bed that is an oval, a table that is a circle, a stand that
   is a solid square. Nothing held the set to a geometric rule, so nothing
   failed until a human looked at them together.
2. **Unversioned bytes.** A cleanup deleted a batch of prepared meshes and
   baked albedos from the working host. They were rebuilt from raw inputs, but
   nothing noticed the loss until a human asked why the game looked wrong.
3. **A stage with no reader.** The pipeline document promised a terminal
   artifact (`assets/<id>/mesh`) and the stage that produces it was never
   written. The pipeline "ended" at a file nothing loaded.
4. **Done meant "file written."** Packed meshes sat on disk while the renderer
   had no texture path at all. The stage that was missing was not the asset —
   it was the consumer.
5. **A target that draws nothing.** One shipped platform's render loop clears
   a color buffer and calls it a frame. It has never drawn 3D. No gate looked,
   because no gate asks whether a target renders game geometry.
6. **A quantity gate standing in for a quality gate.** "Library floor: 100"
   drove the work. A hundred assets in four incompatible shape languages is
   not a library.
7. **A score passing on the wrong question.** A silhouette-retention measure of
   `1.000` was reported on an asset whose source silhouette was the wrong
   shape. Retention measured perfectly; fidelity was never asked.
8. **Method written after the mess.** The art brief came into existence to
   explain a failure, not to prevent one.

None of these are art-quality problems. They are **contract** problems, which
is why they belong here beside `gate-execution-contract`,
`evidence-and-attestation`, `publish-safety` and `doc-truth`. They will recur
on the next title unless they are made checkable.

## What Changes

- **One definition of done, in the contract.** An asset is done when it is
  visible in a shipped build on every target platform and its provenance is
  complete. Not when a file is written. Not when a counter increments. Not
  when a stage logs success. Every failure above is some weaker definition
  accepted in its place.
- **A required art brief before any generation.** Readability brief, art
  direction pillars, palette and value structure, **shape language by class**,
  footprint/scale grid, material families, and the camera/lens statement. The
  shape language is the rule that would have caught the oval bed. Generation
  without a brief is refused.
- **Every pipeline stage names its consumer.** Input, output, the code that
  reads the output, and its determinism requirement. A stage whose output has
  no consumer is not a stage and must not be reported as one.
- **A provenance ledger is the inventory.** One machine-readable row per asset
  carrying stage, brief reference, prompt, seed, content digests, prep-stage
  flags, rights and review verdict. **Counts are derived from the ledger and
  never typed**; a hand-typed count is treated as unsourced.
- **Bytes are versioned and replicated**, with a restore path that has been
  exercised. Cleanup is a recorded deletion, never a disk-pressure side effect.
- **Acceptance is two-sided.** Fidelity — a human verdict against the brief —
  and retention — a measurement. Neither substitutes for the other. An
  automated score must never be the only gate.
- **Every target must draw.** A rendered-frame capture per shipped platform, in
  CI, from the game's own renderer. A platform that clears a buffer and calls
  it a frame is a failing target, not a passing one.
- **Rights recorded at generation.** `unknown` is a recorded value. Unknown
  rights block the public build and never block creative work.
- **Quantity gates run last**, and cannot pass while any asset is failing the
  fidelity gate. Shortfall and fidelity-failure are reported separately and
  never collapsed into one number.
- **The contract grows from the failure registry.** Each new art failure class
  is appended with a prevention rule, and the contract is extended where a
  class is not already covered. This is what keeps the standard from becoming
  the next thing written after the next mess.

## Impact

- **New capability** `art-creation-contract` (spec deltas in this change).
- **New scanner** `scripts/art_creation_scan.py`, which reads a game's art
  brief, pipeline document and provenance ledger and fails on the conditions
  above. Enforcement is mechanical; the fidelity verdict stays human by
  design.
- **No change to existing capabilities.** `publish-safety` and
  `doc-truth` already cover the publish-time and document-truth halves that
  this contract's rights and count requirements lean on. Where those apply,
  this contract cites them rather than restating them.
- **Per-game content is out of scope.** A title's pillars, palette and shape
  rules are content and live in the title's own repository. Only the *schema*
  of the brief, the stage contract, the ledger format and the checks are
  general.
- **First fixture is a live title** that currently exhibits every failure class
  above, which makes the scanner's test suite real rather than synthetic.
