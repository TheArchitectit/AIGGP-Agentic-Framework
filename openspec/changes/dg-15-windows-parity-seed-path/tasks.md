# Tasks

## 1. Reproduce and fix seed materialization

- [x] 1.1 Reproduce `corpus-02-surface-divergence` on Windows and confirm the
  usage exit is caused by invalid JSON from native backslash substitution.
- [x] 1.2 Add tests that invoke real `_materialize`, decode the JSON, and
  assert generated paths remain absolute and under the fixture root for
  Windows paths and legal POSIX double-quoted paths.
- [x] 1.3 Normalize and JSON-escape `{root}` only in structured seed file
  content; leave subprocess argv substitution and seeded corpus definition
  unchanged.
- [x] 1.4 Verify the corpus pin remains unchanged and the Windows five-case
  parity drill passes with its pinned outcomes.

## 2. Cross-platform parity evidence

- [x] 2.1 Run the direct parity drill on Windows: five cases produced their
  pinned outcomes, including expected surface-case exit 1.
- [x] 2.2 Run the focused adapter/template/deployment tests and drill on Linux.
  Linux direct drill passed under a temp root containing a double quote; the
  LF-normalized candidate also passed the five-case drill and 23 focused tests.
  Windows focused tests passed 23 with one POSIX-only quote test skipped.
- [ ] 2.3 Independently review the diff and both host results; no live forge or
  external environment was contacted.

## Workflow follow-up

Archive after independent review accepts both host results, corpus lock, and
pinned strict OpenSpec evidence.
