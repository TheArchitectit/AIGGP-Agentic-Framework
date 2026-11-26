# Tasks

## 1. Reproduce and scope the exact detector findings

- [x] 1.1 Record the nine exact PR-head findings: generated `.git` sample
  comments and marker examples in the canonical and archived spec files.
- [x] 1.2 Confirm current main's two QA sweep commits do not alter this gate.

## 2. Narrow detector corrections

- [x] 2.1 Exclude `.git` with `Path.parts`; retain `.github` as a positive
  control.
- [x] 2.2 Add only the canonical spec and archived delta to the explicit
  allowlist, each with a file-specific rationale; do not add Markdown parsing
  or broad globs.
- [x] 2.3 Verify escaped prose markers, fenced code, ordinary Markdown, and
  source outside those exact exemptions still fail, while zero-input remains
  non-green.

## 3. Verify the delivered gate

- [x] 3.1 Run focused gate tests and the direct evidence-claim scan. Windows
  focused tests passed 36/36; the tree scan reported 1,089 files and zero
  findings.
- [x] 3.2 Independently inspect the allowlist paths and positive controls.
- [x] 3.3 Run pinned strict OpenSpec and relevant CI checks after current main
  is incorporated. Both relevant hosted detector steps passed on the reviewed
  revision. [Evidence](evidence.md)

## Workflow follow-up

Archive only after the exact findings disappear, real markers remain detected,
and independent review accepts the evidence.
