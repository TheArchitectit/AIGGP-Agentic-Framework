# Tasks

## 1. Implementation and verification

- [x] 1.1 Add a GitLab mirror bootstrap helper using the consumer-owned full SHA; verify a valid SHA provisions `.devgate/` and required scripts from a local bare fake-approved-source repository in a clean fixture with no `.gitmodules` or network access.
- [x] 1.2 Add hermetic failure tests for malformed SHA, failed/partial clone, missing scripts and rule/registry files, wrong root, tracked/dirty/untracked reuse, and shell-state leakage; verify no gate runs and no green result is emitted.
- [x] 1.3 Update all 10 invoking GitLab mirrors with the shared local bootstrap include and explicit required-file lists; correct the two regression-rule paths to the canonical `.guardrails` root. Document both upstream-project and copy-in adoption, preserve the 10:10 inventory, runner pins, and gate scope, and use protected variables only for private fetch credentials. Do not modify DG-10-owned image provenance/digest fields.
- [x] 1.4 Run hermetic parity and mirror checks with the documented runtime versions; record source revision and result, and keep live instance proof dormant until an operator adopts GitLab.
