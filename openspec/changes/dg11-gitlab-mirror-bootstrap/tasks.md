# Tasks

## 1. Implementation and verification

- [ ] 1.1 Add a GitLab mirror bootstrap helper using the consumer-owned full SHA; verify a valid SHA provisions `.devgate/` and required scripts from a local bare fake-approved-source repository in a clean fixture with no `.gitmodules` or network access.
- [ ] 1.2 Add failure tests for malformed SHA, failed/partial clone, missing scripts, and wrong root; verify no gate command runs and no green result is emitted.
- [ ] 1.3 Update all invoking GitLab mirrors and setup docs for checkout bootstrap; coordinate mirror edits with DG-10, which owns image provenance/digest fields. Verify each template passes the same bootstrap contract and uses protected variables only for private fetch credentials.
- [ ] 1.4 Run hermetic parity and mirror checks with the pinned toolchain; record source revision and result, and keep live instance proof dormant until an operator adopts GitLab.
