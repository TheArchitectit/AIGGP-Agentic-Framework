# Design

## Context

The consumer GitHub templates use `ubuntu-latest` for several checks.
`templates/github-workflows/spec-coherence.yml` selects a configured runner
label and falls back to `devgate`. Existing template tests prove setup and
scanner behavior. They do not establish an end-to-end consumer release
approval and artifact identity across runner classes.

## Decisions

- Use a small reference repository with no protected data, private access, or
  production credentials. Use the existing pinned tooling bootstrap and
  evidence formats where practical.
- Treat missing, cancelled, or skipped required checks as an incomplete
  candidate. Document separately declared optional checks and label
  results from a different revision.
- Verify the candidate commit, immutable tooling version, check receipts,
  artifact digest, approval reference, and recovery reference at promotion.
  Record the selected evaluation environment in the evidence.
- The development fixture uses a disposable destination. Real deployment
  policy and administrator configuration remain consumer decisions and are
  independently verified in that environment.

## Dependencies

Use the pinned consumer bootstrap and account for existing DG-21 runner work
and DG-22 upstream release planning. The reference fixture can be exercised
before any optional runner or forge is adopted.
