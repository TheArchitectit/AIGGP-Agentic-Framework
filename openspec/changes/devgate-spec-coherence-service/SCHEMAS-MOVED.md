# Schemas moved — pointer note

The 13 frozen contract schemas that used to live here were moved to
`hub/coherence/schemas/` by the `fix-coherence-container-contract` change
(2026-09-19 audit, finding F1):

- Runtime code (`hub/coherence/__main__.py`, `hub/coherence/schemacheck.py`)
  resolved them through this change package's path. Inside the pinned
  evaluation image only `hub/` is copied, so **every** in-container invocation
  failed at first schema load (exit 30 with a misleading "malformed request"
  reason) — and the only real-container test asserted that same exit code for
  a deliberately-invalid request, so it could not tell an honest rejection
  from a broken image.
- The S8 archive step (spec publication) would have moved this directory to
  `openspec/changes/archive/...`, breaking the host-side CLI the same way.

Runtime contracts belong to the service, not to a change package. They now
resolve relative to the service package and are carried into the image by the
existing `COPY hub/ ./hub/`. Their `$id` fields were updated in place; no
schema content changed. See `docs/ROADMAP-2026-09.md` F1 for the full
write-up, and the change package `fix-coherence-container-contract` for the
contract deltas (`coh-rt-08`, `coh-rt-09`).
