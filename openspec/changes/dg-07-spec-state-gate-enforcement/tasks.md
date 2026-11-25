# Tasks

## 1. Local gate review

- [ ] 1.1 Verify `.github/workflows/spec-state.yml` trigger timing, range, and error messages against claims; cite exact line anchors and classify it as detection after push.
- [ ] 1.2 Verify `scripts/hooks/pre-commit` blocking behavior, `--no-verify` bypass, and named audit path; classify it as bypassable local prevention.

## 2. Owner policy evidence

- [ ] 2.1 Read the remote default-branch protection state using authorized read-only owner access; record source, branch, time, reviewer, and actual state, or mark UNKNOWN/NOT_RUN with missing access stated.
- [ ] 2.2 Publish the reviewed evidence disposition and reconcile docs to evidence; verify it does not claim prevention from the push workflow or infer remote policy.
- [ ] 2.3 Run strict OpenSpec validation and traceability; verify identity remains stable and no unsupported source binding is added.
