# Handoff: baseline-hygiene

## Traceability

| Audit finding | Spec requirement | Sprint |
|---|---|---|
| H3 foreign allowlist | base-own-01 | 2 |
| H8 foreign registry entries + write default | base-own-01, base-write-01 | 1, 3 |
| M8 bundled game specs | base-specs-01 | 4 |
| L6 .gitignore misfits | — | 4 |

## Executor notes

- Land rule-enforcement-gaps' overlay merge (its D4) before Sprint 2 ships,
  or consumers lose allowlist coverage with no replacement path.
- The export files under docs/registry-exports/ are archives, not enforced
  data; label them so baseline_check.py ignores them.
- Owner question Q1 (which project owns the 1,726 entries) goes back to
  Roger with this package; do not guess.
