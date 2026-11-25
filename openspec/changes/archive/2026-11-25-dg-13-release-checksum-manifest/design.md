# Design

## Context

At the observed PR head, the CI release-checksum verifier failed because the
manifest did not include the newly tracked `scripts/spec_id_inventory.py` and
recorded an outdated digest for `scripts/check_exec_bits.py`. The verifier
already enumerates tracked script files under `scripts/` and `hub/`, checks
missing and extra records, and compares each digest. CI invokes that verifier
as a blocking step.

## Goals / Non-Goals

**Goals:** make the checked-in manifest match the final tracked script bytes,
and retain evidence that the existing CI check accepts it.

**Non-Goals:** change the checksum algorithm or its file-selection rules,
weaken the CI step, or claim a local result is a hosted CI result.

## Decisions

- Treat the observed failure as a stale delivered artifact, not a verifier
  defect: the failure identifies both a missing tracked script and a changed
  script digest.
- Generate the manifest only after all script edits in this branch are final.
- Verify exact file coverage and content digests using
  `python3 scripts/gen-checksums.py verify`, the same command used by CI.
- Keep hosted CI as the final verification of the committed candidate; a
  locally computed result does not substitute for the workflow run.

## Risks / Trade-offs

- [Later script edits stale the manifest again] -> regenerate after the final
  script change and require the blocking verifier to pass on the candidate.
- [Platform line-ending conversion changes local bytes] -> use the CI
  environment or otherwise verify hashes over the exact committed file bytes.

## Migration Plan

After the script inventory is stable, regenerate `CHECKSUMS.sha256`, run the
verifier, inspect the manifest diff for only the affected digest entries and
new script entry, then wait for hosted CI on the candidate revision. Archive
only after independent review of those results.
