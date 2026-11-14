# Design: Ledger First, Gate Second, Generator Third

## 0. What the tree actually contains

Three independent representations of spec state exist at `7d3ebc5`, and a design
that assumes one of them will be wrong:

1. **Closure tables** — 28 of 31 specs carry `## Requirement Closure` with
   per-requirement cells. `openspec/specs/add-runner-to-fleet/spec.md:54-58` is
   the canonical shape: a markdown table with `Requirement | Status |
   Implementation | Verification`, and 112 `**EXERCISED**` cells across the
   tree.
2. **Status lines** — `doc-truth`, `per-screen-tracking`, and
   `zig-opengl-engine` carry `Status: Closed` / `Status: Implemented` prose
   instead, with no closure table.
3. **`openspec/INDEX.md`** — claims `CLOSED 31 - PARTIAL 0 - OPEN 0 -
   UNKNOWN 0` and states in its own header that it is "Generated, not typed".

The ledger must bind (1) and (2) to commits without inventing a fourth
vocabulary, and the generator must make (3) true. The state vocabulary stays
exactly `EXERCISED | WIRED | ABSENT | NOT_RUN | DIFFERS` as already used.

## 1. One ledger, append-only, beside the specs

`openspec/state-ledger.jsonl` — one JSON object per line, one row per
requirement transition, committed in the same commit that edits the spec:

```
{"schema":"v1","spec":"add-runner-to-fleet","req":"fleet-add-01",
 "from":"OPEN","to":"EXERCISED",
 "opened_commit":"<sha>","landed_commit":"<sha>",
 "tests":["tests/test_template_supply_chain.py::test_n_plus_1_runner"],
 "evidence":"<bundle-dir-relative-path>",
 "evidence_digest":"sha256:<64 hex>","at":"2026-11-03T00:00:00Z"}
```

Rationale for a sibling JSONL over a fenced block inside `spec.md`: the ledger
is machine-appended and diff-reviews cleanly as one line per transition, it
cannot be reformatted away by a doc pass, and it lets a spec with no closure
table (`doc-truth`) join without restructuring its prose. The block-inside-spec
alternative keeps evidence physically adjacent but couples ledger writes to
markdown formatting and makes conflict resolution on concurrent edits worse.

`from` is `OPEN` or a prior cell value; `to` is one of the frozen five.
`at` is informational only and MUST NOT be trusted as ordering — commit
ancestry is the ordering source of truth. A clock that can be edited is not
evidence.

### 1.1 Frozen schema `v1` (Gate 0)

The row schema is frozen here; the gate rejects any row that departs from it
(unknown field, missing required field, wrong type, or a `to` outside the five).

| field | type | required | meaning |
|---|---|---|---|
| `schema` | string, exactly `"v1"` | yes | schema tag; a new shape is `v2`, never an edit of `v1` rows |
| `spec` | string, capability dir name | yes | `openspec/specs/<spec>/spec.md` |
| `req` | string matching `[A-Za-z0-9-]+` | yes | the `<!-- id: ... -->` marker value, exact case |
| `from` | `"OPEN"` or one of the five states | yes | prior state; `OPEN` = no prior cell |
| `to` | one of `EXERCISED`, `WIRED`, `ABSENT`, `NOT_RUN`, `DIFFERS` | yes | new state |
| `opened_commit` | 40-hex or abbreviated resolvable rev | yes | strict ancestor of `landed_commit` |
| `landed_commit` | 40-hex or abbreviated resolvable rev | yes | ancestor of `HEAD`; must differ from `opened_commit` |
| `tests` | list of non-empty strings | yes (may be empty only for non-terminal `to`) | test node IDs that exercise the requirement |
| `evidence` | non-empty string, repo-relative directory | yes for `to: EXERCISED`; optional otherwise | sealed bundle the validator accepts |
| `evidence_digest` | string, `sha256:` + 64 lowercase hex | yes when `evidence` is present | the bundle's `evidence-manifest` digest, pinned by the row |
| `at` | ISO-8601 string | yes | **informational only**; never used for ordering |

**Why the row pins the digest.** `scripts/evidence-validate.py` requires
`--expected` (`scripts/evidence-validate.py:80-82`), and the manifest cannot
vouch for itself: computing the expected value from the bundle and then handing
it back to the validator would make the manifest-tamper half of the check
vacuous, which is the self-certified-claim failure the tree already rejects
(`verification.py` refuses `VERIFIED` without independent verification). So the
row carries the anchor. A tampered bundle fails against it; a tampered row is a
new ledger line, never an edit, because the ledger is append-only.

**Unknown fields are rejected, not ignored.** A gate that ignores a field it does
not understand lets a producer believe it recorded something the gate never
checks. Adding a field is a `v2` schema change with its own gate update.

**The `to` vocabulary is closed.** `EXERCISED | WIRED | ABSENT | NOT_RUN |
DIFFERS` are the five values already used by the 112 existing `**EXERCISED**`
cells; this change adds no sixth state word. `OPEN` appears only in `from`.

**`at` never orders anything.** The gate reads it for display and schema
validity only. Ordering comes from `git merge-base --is-ancestor` between the
two bounding commits and `HEAD`: a row whose `at` says "later" but whose commits
are not in ancestry order is rejected, and a row whose `at` says "earlier" than
its ancestor's is still legal, because the clock is not evidence either way.


## 2. Transitions are derived from the diff, never from prose

The gate computes the set of requirements whose state changed by diffing the
spec tree between a base and `HEAD`, then reconciles that set against ledger
rows added in the same range. Two independent inputs must agree:

- **Changed** = requirements whose closure cell or `Status:` line differs
  between `base` and `HEAD`.
- **Ledgered** = rows present in `HEAD`'s ledger absent in `base`'s.

A requirement in *Changed* without a row in *Ledgered* is a transition without
authority. A row in *Ledgered* whose requirement is not in *Changed* is a
ledger entry with no corresponding state edit. Both fail, because either one
means the two records have diverged and neither can be trusted alone.

This is why a free-text edit is no longer sufficient: editing the cell and not
the ledger fails, and appending to the ledger without editing the cell fails.

A third divergence is checked when a closure cell exists on both sides of the
range: the row's `from` must equal the cell's prior value (`OPEN` when there was
none) and its `to` must equal the cell's new value. A row that names a different
transition than the one the spec records is a ledger entry about some other
edit — accepted, it would let a real transition ride on a fabricated label.
Specs whose state rides on a `Status:` line and carry no cell have nothing to
compare against, so this check is skipped there rather than guessed at.

## 3. Bounding commits must resolve, be ordered, and be distinct

For every transition to a terminal state (`EXERCISED`):

- `opened_commit` resolves to a commit object, is an ancestor of `landed_commit`,
  and is strictly earlier (`git merge-base --is-ancestor opened landed`).
- `landed_commit` resolves and is an ancestor of `HEAD`.
- `opened_commit != landed_commit`.

The distinctness rule is the enforceable form of "commit before and after". It
rejects the single-commit pattern where a spec cell is flipped in the same
commit as its implementation, which destroys the ability to distinguish
"planned then delivered" from "declared complete at the moment of writing".

Correction carried from review: a cited SHA in a spec is evidence only if it
resolves in reachable history. `zig-opengl-engine/spec.md:122` cites
`4b69262`, which does not resolve even in the full 581-commit clone — it is an
external fork head from the 2026-09-26 merge. The migration must therefore
reject unresolvable citations rather than promote them into ledger rows.

## 4. Work must land where the requirement says it lives

A resolved commit pair alone proves two commits exist, not that the second one
did anything relevant. The gate requires:

- `git diff --name-only opened_commit..landed_commit` touches at least one file
  that carries `// spec: <req-id>` (or `# spec: <req-id>`), reusing the marker
  contract `scripts/spec_traceability.py` already defines and
  `scripts/lib/spec_discovery.py` already parses.
- The touched file still exists at `HEAD`.

This is the "actual work was done" test, and it deliberately reuses the one
join the repo already trusts instead of introducing a parallel mapping.

Known limitation, stated rather than hidden: this proves a marked file changed
in the window, not that the change implements the requirement semantically. It
raises the floor from "prose assertion" to "code changed at the declared
location", and no static check can close the remaining gap. The evidence bundle
in section 5 is what has to carry the semantic claim.

## 5. Evidence must be exercised, not asserted

Terminal closure requires a sealed bundle that the existing validator accepts.
`scripts/evidence-validate.py` already verifies digest integrity and claim
consistency with frozen exit codes (`0` valid, `1` invalid, `30` usage,
`scripts/evidence-validate.py:37-39`). The gate invokes it and requires exit `0`
plus passing records for every test named in the row.

Reusing this validator rather than defining a new trust story is deliberate:
it is the only sealed-evidence machinery in the tree that has been reviewed,
and a spec-state gate must not become a weaker parallel authority.

### 5.1 Where the per-test records live (Gate 0/1, recorded 2026-11-13)

The sealed bundle is built from findings, not test results, so "a passing record
for every test named in the row" needs a defined shape or the gate would have to
invent one at check time. The shape is frozen with the schema:

- A terminal row names its tests in `tests` and points `evidence` at a bundle
  directory (repo-relative).
- That directory carries `tests.json`: `{"tests": {"<node id>": "<status>"}}`,
  status one of `passed`, `failed`, `skipped`, `error`.
- `tests.json` MUST itself be a sealed manifest object (listed in
  `evidence-manifest.json` with a digest that recomputes from its bytes); an
  unsealed record is a claim about a bundle, not part of one.
- For every id in `tests`, the gate requires a record whose status is exactly
  `passed`. Missing, unknown, skipped, or failed is a violation — a skipped
  test proves nothing about the requirement.

`evidence-validate.py` still runs first and must exit `0`; this check is
additional to it, never a replacement.

## 6. Closure applies to the whole spec

A spec is terminal only when **every** requirement in it is `EXERCISED`, not
when a majority or a named subset is. The gate rejects a `Status: CLOSED` on a
spec with any requirement still `WIRED`, `ABSENT`, `NOT_RUN`, or `DIFFERS`.

Requirement count is derived from `<!-- id: ... -->` markers via
`spec_discovery.collect_requirements`, not from counting table rows, so a
closure table that omits a requirement cannot hide it. A heading-only spec that
yields zero requirement IDs is reported as unsupported format — never as
"nothing to check".

## 7. The index is generated or it fails

`scripts/spec_index.py` renders `openspec/INDEX.md` from the ledger plus closure
tables. A drift check regenerates to a temp path and fails when the committed
file differs. Two properties make the existing claim true: status comes from
data rather than typing, and a hand-edited index is a red build rather than a
silent divergence.

The generator must reproduce the current `31 specs` counting and the
`CLOSED / PARTIAL / OPEN / UNKNOWN` rollup exactly, or the migration gate
cannot distinguish a real regression from a rendering change.

## 8. Enforcement placement — owner decision, and it changes what "blocked" means

The repository accepts direct pushes to `main` by standing preference, with no
pull-request gate. That constrains what enforcement can honestly claim:

| Placement | Blocks the bad commit? | Cost |
|---|---|---|
| `core.hooksPath` pre-commit | Yes, locally | Bypassable with `--no-verify`; per-clone setup |
| Push-time CI on `main` | No — detects after the ref moved | Auditable, unbypassable, but the bad commit is already history |
| Pre-receive (server-side) | Yes, before the ref moves | Needs a server hook; not available on hosted `main` here |

Recommendation: **pre-commit hook as the block, push-time CI as the audit
trail**, with the CI job treating a missing ledger row as a failure that must be
repaired by a follow-up commit rather than silently tolerated. Do not describe
push-time CI as "preventing" a transition; it reports one that already landed.

This is recorded as an open decision, not a settled design, because it decides
whether the gate can refuse or only report.

## 9. Migration: prove what is provable, mark the rest

Order matters, because backfilling wrongly is worse than leaving blank:

1. Run the generator in **report-only** mode across 31 specs and emit a
   candidate row per `EXERCISED` cell.
2. Accept a candidate only when all of: the cited implementation path exists at
   `HEAD`, a `// spec: <id>` marker exists in a file that changed within a
   resolvable commit window, and that window's commits resolve in reachable
   history.
3. `doc-truth` derives a real row from `0a26e37a`
   (`docs(openspec): closure bookkeeping per owner dispositions 2026-10-13`),
   which resolves. Treat as the worked example.
4. `zig-opengl-engine`'s `4b69262` citation does not resolve; the row lands as
   unproven and the spec cannot be terminal until re-evidenced in-repo.
5. Everything unprovable records an explicit `UNPROVEN` migration marker. It is
   visible in the index and cannot be promoted to proof by editing the spec.

A spec with a ledger row enters the ratchet: it cannot revert to a free-text
`Status:` line. Removing a row requires a new row that says so.

## 10. Failure modes this design refuses

- **Vacuous pass.** Zero specs evaluated is a failure (`nothing_scanned`),
  matching `gate_common.py`'s existing contract.
- **Skip-as-green.** An unresolvable commit, absent bundle, or missing test
  record is a failure, never a warning, for terminal transitions.
- **Consecutive-state laundering.** Editing `OPEN` to `EXERCISED` directly is
  allowed only with both bounding commits and evidence; there is no
  intermediate step that can be satisfied more cheaply.
- **Self-approving closure.** A transition whose `landed_commit` is the commit
  that also introduces the gate cannot be validated by that gate. Bootstrap is
  explicitly out of scope: the gate lands first, the spec-state rows land after,
  and no row may cite the gate's own introduction as its landing commit.
