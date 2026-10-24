# Fleet-manager package boundary — first cut (REPO-002)

Date: 2026-10-24 (UTC). Program package `devgate-product-tiers-fleet-manager`,
Sprint 1 box 1.1. Owner decisions OD-001 (BSD 3-Clause everywhere, no
commercial split in Phase 1) and OD-002 (boundary root `fleet-manager/`) were
taken 2026-09-29; this change implements only what they leave standing.

## What was created

- `fleet-manager/README.md` — license notice (BSD 3-Clause, root `LICENSE`, no
  separate grant) and the dependency rules in prose.
- `fleet-manager/manifest.json` — the machine-readable declaration: boundary
  root, license block (`separate_grant: false`), declared path patterns,
  `forbidden_roots`, `exempt_paths`.
- `scripts/check_boundary.py` — the gate (REPO-002 scenarios: undeclared file
  under the root, core importing the boundary, product-tiers code outside the
  root, unreadable manifest).
- `tests/test_check_boundary.py` — 12 tests.
- `openspec/changes/add-fleet-manager-boundary/` — proposal, design, spec
  (requirements `repo-002-01` .. `repo-002-04`), tasks.

## Gate runs (this tree)

```
$ python3 scripts/check_boundary.py --repo .
[boundary] OK: 2 file(s) under fleet-manager/, all declared; no open-core
reference to the boundary
rc=0

$ npx --no-install openspec validate --all --strict
Totals: 34 passed, 0 failed (34 items)      # 33 before; the new change is the 34th

$ python3 -m pytest tests/test_check_boundary.py -q
12 passed
```

## Mutation proofs

Each test in `tests/test_check_boundary.py` is a planted case, not a prose
claim:

| planted | expected | asserted |
|---|---|---|
| `hub/leaky.py` = `from fleet_manager.domain import pool` | exit 1 | file:line named |
| `scripts/loader.sh` naming `fleet-manager/tool.py` | exit 1 | file named |
| `fleet-manager/api/server.py` (no declared pattern) | exit 1 | path named |
| `fleet-manager/tests/test_pool.py` importing `hub.core` | exit 0 | allowed direction does not red |
| manifest `{not json` | exit 2 | "not JSON", not a clean boundary |
| `separate_grant: true` | exit 2 | OD-001 enforced |
| declared path `hub/everything/**` | exit 2 | pattern outside the root rejected |
| `docs/note.md` naming `fleet-manager/` | exit 0 | prose is not a dependency edge |
| changed `enterprise/billing.py` vs `main` | exit 1 | forbidden root named |
| the real manifest's `exempt_paths` | exactly the gate + its test | the one hole cannot grow quietly |

## Stated limits

1. The dependency scan is a static line scan over code files, not an import
   resolver. A dynamically computed module name (`importlib.import_module(x)`)
   is not detected. The gate is a tripwire on the common accident, not a
   sandbox.
2. Prose (`.md`) and data files are not scanned; documentation may name the
   boundary freely.
3. Comment lines (leading `#` / `//`) are skipped, so a commented-out import
   does not red. A gate that reds on prose gets muted.
4. The changed-path half needs history; CI's specs job now checks out with
   `fetch-depth: 0` and skips only that half (loudly) when `origin/main` is not
   resolvable.

## Not done here (deliberately)

- `contracts/v1/` is declared as a pattern and is empty: versioned contracts
  and bidirectional contract tests are box 1.2.
- No extraction rehearsal: box 1.3, and it needs the contracts to exist first.
- No entitlement/license enforcement: OD-001 descoped it for Phase 1.
