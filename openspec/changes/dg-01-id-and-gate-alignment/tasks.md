# Tasks

## 1. Identity inventory

- [ ] 1.1 Enumerate every canonical heading and ID comment, including duplicate and malformed cases; verify the eight missing-ID headings and save the heading-to-ID mapping for review; baseline `scripts/spec_state_gate.py --base 479b609 --head fd2c11f` reports unsupported format for adapters-and-loops, reviewer-surfaces, and traceability-and-drift.
- [ ] 1.2 Search history, archives, code markers, tests, and docs for references before assigning the eight missing stable IDs; verify no existing valid ID changes.

## 2. Gate and repair

- [ ] 2.1 Repair the eight missing IDs; verify each of the 251 headings maps to exactly one supported ID.
- [ ] 2.2 Add the CLI-versus-marker inventory comparison and negative controls for missing, malformed, duplicate, and extra IDs; verify each control fails with the expected heading.
- [ ] 2.3 Run pinned `openspec validate --all --strict` and `python3 scripts/spec_traceability.py --report`; verify exact per-capability ID equality and no count inflation; rerun `scripts/spec_state_gate.py` and confirm those three unsupported-format findings are gone while reporting any unrelated findings separately.
