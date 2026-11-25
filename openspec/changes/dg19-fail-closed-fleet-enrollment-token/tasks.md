# Tasks

## 1. Trace and repair the authentication boundary

- [ ] 1.1 Inspect the two required configuration inputs, the exact pinned
  issuer transport, token selection, and reconciler handoff.
- [ ] 1.2 Refuse missing configuration or an empty mint result before any
  enrollment call. Remove the fallback identity and duplicate token output.
- [ ] 1.3 Verify the issuer's own transport against the existing file-handling
  requirement. Record any unresolved boundary in DG-05 and in this change.

## 2. Verify locally and record evidence

- [ ] 2.1 Exercise missing pair, empty token, and valid synthetic handoff
  cases through the actual workflow or process boundary. Verify that no raw
  values reach captured output or written artifacts.
- [ ] 2.2 Verify the input and trigger contract, run the focused enrollment
  suite and pinned repository gates, and obtain independent review.
