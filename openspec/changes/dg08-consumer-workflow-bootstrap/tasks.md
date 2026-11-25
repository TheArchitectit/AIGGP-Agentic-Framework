# Tasks

## 1. Implementation and verification

- [ ] 1.1 Update reusable workflow/setup text to clone `.devgate/` at a consumer-owned full SHA; test copied setup against a local bare fake-approved-source repository at its fixture SHA with no `.gitmodules` and no network access.
- [ ] 1.2 Test malformed SHA, wrong checkout, missing scripts, and wrong root using hermetic fixture repos; verify each fails before any gate reports PASS and the tests make no upstream network request.
- [ ] 1.3 Reconcile wiring/onboarding docs; verify documented no-submodule path and pin ownership match the template.
