# Design: spec-audit-rollout

## The one decision that shapes everything: mechanical vs judgment

The MergeKingdom work order states the cut and a defect that proves it: a
first-pass inventory misreported `BuildingBase.production_ready` as "never
emitted" (it is, at `building_base.gd:30`) and `VFX.merge_sparkle` as
"claimed but absent" (wired at `grid_board.gd:149`). A generated claim that
was not verified against source is indistinguishable from a lie. So:

- **The scanner may assert only what it can point at.** Every capability
  row, every scaffold stub, every draft requirement carries `file:line`
  evidence into the code that was actually read.
- **The scanner may never assert what it could not point at.**
  CLAIMED-BUT-ABSENT is an output category, not a spec. A doc claim with no
  code stays a row in §C until a human moves it.
- **Generation proposes; review merges.** `--draft` output is born marked
  unreviewed and is excluded from every number that gates.

## Scanner (`scripts/spec_gap_scan.py`)

stdlib-only Python, dual-runnable, in the `scripts/` gate family.

Inventory side: `src/autoload/*.gd` (one candidate per manager),
`src/core/`, `src/models/`, `src/ui/`, `src/scenes/`, `data/*.json`, plus
doc-claim harvest from `CLAUDE.md` / `game-specs/**`. The inventory is
*game-shaped* because that is the fleet's dominant repo class; a non-game
repo simply yields a smaller inventory (the same `scripts/`, `workflows/`
sweep), and an empty inventory is reported as "looked, found no capability
anchors", never as "nothing to spec".

Coverage side: identical discovery to `spec_traceability.py` —
`openspec/specs/*/spec.md`, `openspec/changes/*/specs/**`, `<!-- id: … -->`
markers, `// spec:` / `# spec:` source markers. One discovery
implementation, imported or extracted to a shared module, so the two gates
can never disagree about what "covered" means — a disagreement there would
be the worst possible output, two confident numbers with one wrong.

Report: JSON (`--json`) + human table, ordered **worst-tracked first**.
Categories:
- capability with zero spec files (the scaffold set)
- requirement IDs present but unmarked (uncovered)
- behavior-bearing source with no markers
- `CLAIMED-BUT-ABSENT` (clearly separated; never unioned with the above)

Exits (secret-scan convention, documented contrast with
`game_session_start.py`'s inverted pair — do not unify):
`0` no gaps · `1` gaps found (`--fail-on-gaps`) · `2` scanner unusable /
config error (missing root, unreadable tree, no anchors at all).

`--scaffold` writes `openspec/specs/<capability>/spec.md` stubs: heading
skeleton + evidence pointers + empty requirement slots. A scaffolded
requirement with no `file:line` is a coverage fabrication, so `--scaffold`
emits none; `--draft` may, and then only marked `<!-- draft: unreviewed -->`.
Drafts are excluded from coverage floors, ratchet counts, and
`spec_traceability.py`'s numerator by the marker check — that exclusion is
the acceptance condition the work order names ("out of config-refusal into
real numbers" must happen via *reviewed* IDs, not by the generator inflating
the count).

## Intake gate (`spec-fleet.yml`)

Nightly, `17 4` offset from the secret sweep's `17 4` (use `47 4` to stagger
the clone load on the runner), walking `fleet-sweep-include.txt` /
`-exclude.txt` + generated owner-scope list. Classification per repo:

| State | Meaning | Red? |
|---|---|---|
| `spaced` | openspec present, `--strict` green, gap scan clean | no |
| `gaps` | openspec present, strict green, gap scan found gaps | no (informational) |
| `invalid` | openspec present, strict red | red only past the tier line |
| `unspaced` | no spec universe at all | **never red** |
| `unscannable` | could not clone / could not classify | counts, never reads as `spaced` |

The `unspaced`-is-informational rule is not a style preference — it is the
measured SGR-10 lesson. The first live secret sweep produced 128 false drift
entries because "not yet adopted" was classified as divergence; a spec gate
that reds on 126 unspaced repos nightly gets muted inside a week and then
misses the real ones. `unspaced[]` is a list in the report and a count in
the trend line, which is what an adoption backlog needs to be: visible,
ranked, not alarming.

`invalid` is gated only for repos listed in `spec-audit-tier.txt` (a small
allowlist, adoption-ladder style). Rationale: strict-red on a repo that was
never told it owed specs is the same unfair red; a repo that has opted in
by entering the tier has accepted the contract.

Report shape mirrors the secret sweep so one reader pattern works for both:
`declared/scanned/states`, `unspaced[]`, `invalid[]`, `gaps_top[]`
(worst-tracked first, capped — the 40-location cap that fixed the 422),
trend commit to `docs/qa/spec-sweeps/<date>.json` with the same
CAP-and-`omitted` discipline night one taught.

Alert via `hub_alert.py --key spec_fleet_sweep`, which now names repos
instead of merely counting them (the T-14 fix landed for exactly this
class).

## Template provenance (`spec-templates.lock.json` + refresh check)

```json
{
  "templates": {
    "openspec-spec-template": {
      "source": "https://github.com/Fission-AI/OpenSpec … <path>",
      "pinned_sha256": "…",
      "upstream_version": "…",
      "vendored_at": "2026-09-30",
      "adopted_by": "docs/qa/<date>-template-provenance.md"
    }
  }
}
```

A scheduled step fetches each source, hashes it, compares. Mismatch →
deduped issue naming template + both hashes + the version delta. Nothing is
written into any tree automatically: **detection automated, adoption
reviewed**. This is the gitleaks pin discipline (URL + sha256 + version
assert, verified locally before pinning) applied to content rather than a
binary, and the same rule the CI npx-resolved openspec CLI violates today
(a separate, smaller fix recorded as an assumption below).

## What does not change

- `spec_traceability.py`: exit-2 zero-spec refusal stands. The scanner is a
  discoverer beside it; softening the refusal would hide the exact wedge
  this package exists to fix.
- `secret-fleet.yml`: sibling, not merged. Different scan, different
  failure semantics, different reviewer reflex; one workflow doing both
  couples two release cadences for no gain.
- gameSessionStart: gains one advisory line ("worst-tracked gaps: N, see
  `spec_gap_scan.py`") fed by this scanner — one inventory source, no
  second.

## Stated assumptions (hard rule #5)

1. Official openspec template source is the Fission-AI/OpenSpec repo; if
   the canonical artifacts turn out to live elsewhere (site bundle, npm
   package), the lock file records that instead — provenance of *the file
   we actually vendored*, not of a guess.
2. Coverage discovery is shared with `spec_traceability.py` by extraction
   into `scripts/lib/spec_discovery.py` rather than duplication; if
   extraction proves invasive, the second-best option is the scanner
   shelling out to `spec_traceability.py --json` and reading its numbers —
   never re-implementing the regex a second time.
3. The fleet's dominant repo class is game repos, hence the game-shaped
   inventory; general-purpose repos get the reduced sweep and an empty
   anchor set is reported honestly rather than as a pass.
4. `gaps` is informational by default. If MergeKingdom's post-review
   numbers show gap-count red is actionable rather than noise, promoting it
   is a tier-file edit, not a redesign.
5. CI's `npx openspec validate` is unpinned today (audit noted it); this
   package does not fix it but records it as adjacent debt, because
   template provenance without CLI provenance is half a lock.
