# Fleet Manager extraction rehearsal — evidence

Date: 2026-10-24 (UTC). Program package `devgate-product-tiers-fleet-manager`,
Sprint 1 box 1.3 (extraction rehearsal in CI; core gates green with the
boundary absent). Openspec change:
`add-fleet-manager-extraction-rehearsal` (`repo-005-01..03`).

## What landed

`fleet-manager/scripts/extraction_rehearsal.py`, run in CI:

- **Phase A** copies `fleet-manager/` into an empty workspace, copies in only
  the three declared build inputs (`hub/__init__.py`,
  `hub/coherence/__init__.py`, `hub/coherence/schemacheck.py`), asserts nothing
  else from open core is present, and runs the package's suite there.
- **Phase B** copies the repository without `fleet-manager/`, then collects the
  entire core suite and runs the pattern scan.

The real checkout is never modified; both workspaces are `tempfile` copies.

## Measured run (this checkout)

```
[rehearsal] manifest declares 6 path pattern(s)
[rehearsal] phase A: pytest in the extracted copy -> exit 0
[rehearsal] phase B: core suite collection -> exit 0
[rehearsal] phase B: 1743 core tests collect
[rehearsal] phase B: guardrails scan -> exit 0
[rehearsal] OK — boundary stands alone, core stands without it
```

~10 s wall clock.

## The gate caught CI before CI could catch anything

Adding the step `python3 -m pytest fleet-manager/tests -q` made
`check_boundary.py` red:

```
[boundary] FAIL: 1 violation(s)
  - .github/workflows/ci.yml:70: open-core code references the boundary
    ('fleet-manager/'); the allowed direction is boundary -> core only
```

That is the rule doing its job — and also a rule that cannot be left as it was,
because it made running the boundary's own tests illegal. Rather than exempt
the workflow wholesale (which would also permit a real import site to appear
there) the manifest gained `invocation_paths`: an explicit, reviewed list of
files that may **name** the boundary because they start its tests, kept
separate from `exempt_paths` so the reason each file is skipped is written
down. The list is pinned by a test.

## Planted cases

| case | expected | where |
| --- | --- | --- |
| a declared invocation site names `fleet-manager/tests` | gate exits 0 | `test_an_invocation_site_may_name_the_boundary_but_others_may_not` |
| the same string in a core module | gate exits 1 naming the file | same test |
| `invocation_paths` names a path inside the boundary | gate exits 2 ("inside the boundary") | `test_an_invocation_site_inside_the_boundary_is_a_manifest_error` |
| `exempt_paths` / `invocation_paths` in the real manifest | exactly the pinned sets | `test_exempt_list_is_pinned_to_the_gate_and_its_test` |
| the rehearsal's build-input list vs the package's pinned import surface | identical | `TestRehearsalDeclaresTheSameBuildInputs` |
| the rehearsal's declared build inputs | each exists on disk | same test |

## A second marker bug, one layer up from the first

`scripts/check_boundary.py` declared `# spec: repo-002-01 repo-002-02
repo-002-03 repo-002-04`. `spec_discovery` parses **comma**-separated IDs, so
only `repo-002-01` registered and the other three read UNCOVERED — including
`repo-002-03`, the dependency-direction rule this whole slice leans on. Fixed;
the tree now reports `repo-002-02/03/04` covered, and traceability moved
91 → 97 with three new requirements and three recovered ones.

Both marker bugs were found the same way: the number did not match the
arithmetic. That is the only reason they were found at all, which is worth
recording next to the fix.

## The first CI run failed — twice, on this slice's own files

Local gates were green and CI was not, which is the reason the run is read
rather than assumed. Two defects, both introduced by this slice, both caught by
gates that had never before been run against a `fleet-manager`-era tree (the
earlier runs on this branch were `cancelled` by the concurrency group, so 1.1's
files had never actually completed a CI run):

1. **`check_boundary.py` and its test were committed `100644` while carrying a
   shebang.** `scripts/check_exec_bits.py` — and the `DevGate gates on DevGate`
   job — refuse that, correctly. Fixed with `git update-index --chmod=+x` on
   both; `check-exec-bits: OK — 116 shebang'd file(s), all 100755`.
2. **`check_boundary.py` declared its own `SKIP_DIRS` set**, which
   `tests/test_scope_contract.py` forbids by grep (`fw-scope-01`: one scope list
   in `.guardrails/scope.json`, consumed by every gate). This gate had a private
   four-entry list — so "boundary tree clean" meant "clean under *this gate's*
   exclusions", which is exactly the drift the scope contract exists to stop.
   Fixed by consuming `gate_common.load_skip_dirs()`, the same loader
   `regression_sizes.py` uses.

Both are recorded because both are the same shape: a gate with a local
assumption passing its own tests. Neither would have been found by re-reading
the diff; they were found by a run that finally completed.

## Gate runs (all re-run in this window)

| gate | result |
| --- | --- |
| `npx --no-install openspec validate --all --strict` | **36/36 items** |
| `bash scripts/specs-validate-negative-control.sh` | exit 0 |
| `python3 tests/gen_floors.py --check` | OK — 125 suites, **1743** tests (floors regenerated: `test_check_boundary` 12 → 14) |
| `python3 scripts/check_manifest_join.py --repo .` | OK — 1 join, both directions |
| `node scripts/guardrails-scan.mjs` | pattern scan clean (32 non-blocking warnings) |
| `python3 scripts/spec_traceability.py --root . --ratchet` | **97/140**, ratchet raised 91 → 97 |
| `python3 scripts/regression_check.py --base origin/main --fail-if-empty --pre-commit` | rc 0, 0 over hard limit |
| `python3 scripts/artifact_hygiene.py --repo . --audit` | audit OK |
| `python3 scripts/check_boundary.py --repo .` | OK — 12 files under the root, all declared |
| `python3 scripts/check_exec_bits.py` | OK — 116 shebang'd files, all `100755` |
| `python3 -m pytest tests/test_scope_contract.py tests/test_check_boundary.py -q` | 20 passed |
| `python3 -m pytest fleet-manager/tests -q` | 24 passed |
| `python3 fleet-manager/scripts/extraction_rehearsal.py --source .` | OK, both phases |

## What phase B does and does not prove

- **Proves:** no core module, test module, fixture or script fails to import or
  collect without `fleet-manager/` present, and the pattern scan is unaffected
  by its absence.
- **Does not prove:** that the full core suite *runs* green without the
  boundary. Collection is the cheap half that catches dependency edges; the
  full run happens in its own step with the tree intact. The claim is written
  this way on purpose — "core gates proven green with commercial code absent"
  is satisfied for collection and the pattern scan, not for all 1743 tests in a
  boundary-free copy.
- **Does not authorize extraction.** REPO-005 says the rehearsal is evidence,
  not permission to create a second repository.

## Stated limits of the allowance

An `invocation_paths` entry is trusted not to import the boundary; the scanner
cannot tell "run its tests" from "import its internals". Today the list has one
entry, a YAML workflow, which cannot import anything. The pin means adding a
Python or shell file there is a reviewed diff with a reviewer looking at that
question.
